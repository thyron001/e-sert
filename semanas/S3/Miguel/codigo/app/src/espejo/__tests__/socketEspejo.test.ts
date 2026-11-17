import { afterEach, beforeEach, describe, expect, jest, test } from '@jest/globals';
import type { AppStateStatus } from 'react-native';

import type { FinEspejo, MensajeEspejo } from '@/src/api/tipos';
import { generarRecorrido } from '../recorridoMock';
import {
  ESPERA_MAXIMA_MS,
  INTENTOS_HASTA_SIN_CONEXION,
  SILENCIO_MAXIMO_MS,
  SocketEspejo,
  esperaReconexion,
  type EstadoConexion,
  type ManejadoresEspejo,
  type SocketMinimo,
} from '../socketEspejo';

const recorrido = generarRecorrido('sim_veh42');
const espejos = recorrido.filter((m): m is MensajeEspejo => m.tipo === 'espejo');
const fin = recorrido[recorrido.length - 1] as FinEspejo;

/** WebSocket falso: guarda cada instancia y deja emitir open/message/close desde el test. */
class SocketFalso implements SocketMinimo {
  static instancias: SocketFalso[] = [];
  onopen: ((ev?: unknown) => void) | null = null;
  onmessage: ((ev: { data: unknown }) => void) | null = null;
  onclose: ((ev?: unknown) => void) | null = null;
  onerror: ((ev?: unknown) => void) | null = null;
  cerrado = false;
  constructor(readonly url: string) {
    SocketFalso.instancias.push(this);
  }
  close(): void {
    this.cerrado = true;
  }
  abrir(): void {
    this.onopen?.();
  }
  mensaje(datos: unknown): void {
    this.onmessage?.({ data: typeof datos === 'string' ? datos : JSON.stringify(datos) });
  }
  cerrarDesdeServidor(): void {
    this.onclose?.();
  }
}

const ultimo = () => SocketFalso.instancias[SocketFalso.instancias.length - 1];

interface Montaje {
  espejo: SocketEspejo;
  crearSocket: jest.Mock<(url: string) => SocketMinimo>;
  onMensaje: jest.Mock<ManejadoresEspejo['onMensaje']>;
  onFin: jest.Mock<ManejadoresEspejo['onFin']>;
  onEstado: jest.Mock<ManejadoresEspejo['onEstado']>;
  cambiarAppState: (e: AppStateStatus) => void;
  ahora: jest.Mock<() => number>;
}

function montar(): Montaje {
  let escuchaAppState: ((e: AppStateStatus) => void) | null = null;
  const crearSocket = jest.fn((url: string): SocketMinimo => new SocketFalso(url));
  const ahora = jest.fn(() => 123_456);
  const espejo = new SocketEspejo((v) => `ws://servidor/ws/espejo/${v}`, {
    crearSocket,
    escucharAppState: (fn) => {
      escuchaAppState = fn;
      return () => {
        escuchaAppState = null;
      };
    },
    aleatorio: () => 0.5,
    ahora,
  });
  const onMensaje = jest.fn<ManejadoresEspejo['onMensaje']>();
  const onFin = jest.fn<ManejadoresEspejo['onFin']>();
  const onEstado = jest.fn<ManejadoresEspejo['onEstado']>();
  espejo.conectar('sim_veh42', { onMensaje, onFin, onEstado });
  return {
    espejo,
    crearSocket,
    onMensaje,
    onFin,
    onEstado,
    ahora,
    cambiarAppState: (e) => escuchaAppState?.(e),
  };
}

beforeEach(() => {
  jest.useFakeTimers();
  SocketFalso.instancias = [];
});

afterEach(() => {
  jest.clearAllTimers();
  jest.useRealTimers();
  jest.restoreAllMocks();
});

describe('esperaReconexion', () => {
  test('backoff exponencial 1, 2, 4, 8, 16, 30, 30 s sin jitter', () => {
    const esperas = [1, 2, 3, 4, 5, 6, 7].map((i) => esperaReconexion(i, () => 0.5));
    expect(esperas).toEqual([1000, 2000, 4000, 8000, 16000, 30000, 30000]);
  });

  test('el jitter queda dentro de ±20 %', () => {
    for (let i = 1; i <= 8; i++) {
      const base = Math.min(1000 * 2 ** (i - 1), ESPERA_MAXIMA_MS);
      const bajo = esperaReconexion(i, () => 0);
      const alto = esperaReconexion(i, () => 0.999999);
      expect(bajo).toBe(Math.round(base * 0.8));
      expect(bajo).toBeGreaterThanOrEqual(base * 0.8 - 1);
      expect(alto).toBeLessThanOrEqual(base * 1.2);
      expect(alto).toBeGreaterThan(base);
    }
  });
});

describe('SocketEspejo: reconexión', () => {
  test('esperas de 1, 2, 4, 8, 16, 30, 30 s entre sockets y estados reconectando → sin_conexion', () => {
    const { crearSocket, onEstado } = montar();
    expect(crearSocket).toHaveBeenCalledTimes(1);
    expect(crearSocket).toHaveBeenCalledWith('ws://servidor/ws/espejo/sim_veh42');

    const esperasMs = [1000, 2000, 4000, 8000, 16000, 30000, 30000];
    esperasMs.forEach((espera, k) => {
      const creados = crearSocket.mock.calls.length;
      ultimo().cerrarDesdeServidor(); // cierra enseguida, sin mensajes
      jest.advanceTimersByTime(espera - 1);
      expect(crearSocket).toHaveBeenCalledTimes(creados); // todavía no
      jest.advanceTimersByTime(1);
      expect(crearSocket).toHaveBeenCalledTimes(creados + 1);
      expect(k + 2).toBe(creados + 1);
    });

    const estados = onEstado.mock.calls.map(([e, i]) => [e, i] as [EstadoConexion, number]);
    expect(estados).toEqual([
      ['reconectando', 1],
      ['reconectando', 2],
      ['reconectando', 3],
      ['reconectando', 4],
      ['reconectando', 5],
      ['sin_conexion', 6],
      ['sin_conexion', 7],
    ]);
    expect(INTENTOS_HASTA_SIN_CONEXION).toBe(6);
  });

  test('onerror también dispara la reconexión (una sola vez si llegan error y close)', () => {
    const { crearSocket, onEstado } = montar();
    const s = ultimo();
    s.onerror?.();
    s.onclose?.(); // ya se soltaron los manejadores: no hace nada
    expect(onEstado).toHaveBeenCalledTimes(1);
    jest.advanceTimersByTime(1000);
    expect(crearSocket).toHaveBeenCalledTimes(2);
  });

  test('el primer mensaje válido reinicia la cuenta: la siguiente caída espera 1 s', () => {
    const { crearSocket, onEstado } = montar();
    ultimo().cerrarDesdeServidor(); // intento 1 → 1 s
    jest.advanceTimersByTime(1000);
    ultimo().cerrarDesdeServidor(); // intento 2 → 2 s
    jest.advanceTimersByTime(2000);
    ultimo().cerrarDesdeServidor(); // intento 3 → 4 s
    jest.advanceTimersByTime(4000);
    expect(crearSocket).toHaveBeenCalledTimes(4);

    ultimo().abrir();
    ultimo().mensaje(espejos[0]);
    expect(onEstado).toHaveBeenLastCalledWith('en_vivo', 0);

    ultimo().cerrarDesdeServidor();
    expect(onEstado).toHaveBeenLastCalledWith('reconectando', 1);
    jest.advanceTimersByTime(999);
    expect(crearSocket).toHaveBeenCalledTimes(4);
    jest.advanceTimersByTime(1);
    expect(crearSocket).toHaveBeenCalledTimes(5);
  });

  test('en_vivo se emite solo con el primer mensaje, no a cada mensaje a 1 Hz', () => {
    const { onEstado } = montar();
    ultimo().abrir();
    espejos.slice(0, 5).forEach((m) => {
      ultimo().mensaje(m);
      jest.advanceTimersByTime(1000);
    });
    expect(onEstado.mock.calls.filter(([e]) => e === 'en_vivo')).toHaveLength(1);
  });
});

describe('SocketEspejo: silencio', () => {
  test('5 s sin mensajes cierran el socket y se reconecta a 1 s', () => {
    const { crearSocket, onEstado } = montar();
    const s = ultimo();
    s.abrir();
    s.mensaje(espejos[0]);
    jest.advanceTimersByTime(SILENCIO_MAXIMO_MS - 1);
    expect(s.cerrado).toBe(false);
    jest.advanceTimersByTime(1);
    expect(s.cerrado).toBe(true);
    expect(onEstado).toHaveBeenLastCalledWith('reconectando', 1);
    expect(crearSocket).toHaveBeenCalledTimes(1);
    jest.advanceTimersByTime(1000);
    expect(crearSocket).toHaveBeenCalledTimes(2);
  });

  test('un socket abierto que nunca envía nada también cuenta como silencio', () => {
    const { crearSocket } = montar();
    const s = ultimo();
    s.abrir();
    jest.advanceTimersByTime(SILENCIO_MAXIMO_MS);
    expect(s.cerrado).toBe(true);
    jest.advanceTimersByTime(1000);
    expect(crearSocket).toHaveBeenCalledTimes(2);
  });

  test('los mensajes a 1 Hz mantienen vivo el socket', () => {
    const { crearSocket } = montar();
    const s = ultimo();
    s.abrir();
    espejos.slice(0, 20).forEach((m) => {
      s.mensaje(m);
      jest.advanceTimersByTime(1000);
    });
    expect(s.cerrado).toBe(false);
    expect(crearSocket).toHaveBeenCalledTimes(1);
  });
});

describe('SocketEspejo: fin y cierre manual', () => {
  test('espejo_fin llama a onFin una vez, cierra el socket y no reconecta', () => {
    const { crearSocket, onFin, onMensaje } = montar();
    const s = ultimo();
    s.abrir();
    s.mensaje(espejos[0]);
    s.mensaje(fin);
    expect(onFin).toHaveBeenCalledTimes(1);
    expect(onFin).toHaveBeenCalledWith(fin);
    expect(onMensaje).toHaveBeenCalledTimes(1);
    expect(s.cerrado).toBe(true);
    s.cerrarDesdeServidor(); // manejadores ya quitados
    jest.advanceTimersByTime(60_000);
    expect(crearSocket).toHaveBeenCalledTimes(1);
    expect(onFin).toHaveBeenCalledTimes(1);
  });

  test('cerrar() manual detiene la reconexión pendiente', () => {
    const { espejo, crearSocket, onEstado } = montar();
    ultimo().cerrarDesdeServidor(); // queda un reintento a 1 s
    espejo.cerrar();
    jest.advanceTimersByTime(60_000);
    expect(crearSocket).toHaveBeenCalledTimes(1);
    expect(onEstado).toHaveBeenCalledTimes(1);
  });

  test('cerrar() con el socket abierto lo cierra y no reconecta', () => {
    const { espejo, crearSocket } = montar();
    const s = ultimo();
    s.abrir();
    s.mensaje(espejos[0]);
    espejo.cerrar();
    expect(s.cerrado).toBe(true);
    jest.advanceTimersByTime(60_000);
    expect(crearSocket).toHaveBeenCalledTimes(1);
  });
});

describe('SocketEspejo: mensajes inválidos', () => {
  test('JSON roto y objetos que no cumplen 6b se descartan con console.warn', () => {
    const aviso = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const { onMensaje, onFin, onEstado } = montar();
    const s = ultimo();
    s.abrir();
    s.mensaje('{esto no es json');
    s.mensaje({ ...espejos[0], lat: 'norte' });
    s.mensaje({ tipo: 'espejo', veh_id: 'sim_veh42' });
    s.mensaje({ ...espejos[0], veh_id: 'veh42' }); // sin prefijo sim_
    expect(onMensaje).not.toHaveBeenCalled();
    expect(onFin).not.toHaveBeenCalled();
    expect(onEstado).not.toHaveBeenCalledWith('en_vivo', 0);
    expect(aviso).toHaveBeenCalledTimes(4);
  });
});

describe('SocketEspejo: AppState', () => {
  test('background cierra, emite sin_conexion y no reconecta; active reconecta enseguida', () => {
    const { crearSocket, onEstado, cambiarAppState } = montar();
    const s = ultimo();
    s.abrir();
    s.mensaje(espejos[0]);

    cambiarAppState('background');
    expect(s.cerrado).toBe(true);
    expect(onEstado).toHaveBeenLastCalledWith('sin_conexion', 0);
    jest.advanceTimersByTime(60_000);
    expect(crearSocket).toHaveBeenCalledTimes(1);

    cambiarAppState('active');
    expect(crearSocket).toHaveBeenCalledTimes(2); // sin avanzar temporizadores
    expect(onEstado).toHaveBeenLastCalledWith('reconectando', 0);
  });

  test('background con un reintento pendiente lo cancela', () => {
    const { crearSocket, cambiarAppState } = montar();
    ultimo().cerrarDesdeServidor();
    cambiarAppState('background');
    jest.advanceTimersByTime(60_000);
    expect(crearSocket).toHaveBeenCalledTimes(1);
    cambiarAppState('active');
    expect(crearSocket).toHaveBeenCalledTimes(2);
  });

  test('active sin haber pasado por background no abre otro socket', () => {
    const { crearSocket, cambiarAppState } = montar();
    cambiarAppState('active');
    expect(crearSocket).toHaveBeenCalledTimes(1);
  });
});

describe('SocketEspejo: onMensaje', () => {
  test('recibe el mensaje parseado y recibidoEn del reloj inyectado', () => {
    const { onMensaje, ahora } = montar();
    const s = ultimo();
    s.abrir();
    ahora.mockReturnValueOnce(1_000_000);
    s.mensaje(espejos[3]);
    ahora.mockReturnValueOnce(1_001_000);
    s.onmessage?.({ data: espejos[4] }); // un objeto ya parseado también vale
    expect(onMensaje).toHaveBeenNthCalledWith(1, espejos[3], 1_000_000);
    expect(onMensaje).toHaveBeenNthCalledWith(2, espejos[4], 1_001_000);
  });
});
