import { beforeEach, describe, expect, jest, test } from '@jest/globals';

import type { MensajeEspejo } from '@/src/api/tipos';
import { NotificadorEspejo, textoTransicion, type Aviso } from '../notificaciones';
import { generarRecorrido } from '../recorridoMock';
import { olvidarAvisados } from '@/src/servicios/avisos';

// El registro tipo + sesion_id (S3-2) es global: cada test empieza limpio.
beforeEach(() => olvidarAvisados());

jest.mock('expo-notifications', () => ({
  setNotificationHandler: jest.fn(),
  setNotificationChannelAsync: jest.fn(() => Promise.resolve()),
  requestPermissionsAsync: jest.fn(() => Promise.resolve({ granted: true })),
  scheduleNotificationAsync: jest.fn(() => Promise.resolve('id')),
  AndroidImportance: { HIGH: 4 },
}));

const espejos = generarRecorrido('sim_veh42').filter((m): m is MensajeEspejo => m.tipo === 'espejo');

function nuevo() {
  const enviar = jest.fn<(a: Aviso) => void>();
  return { enviar, notificador: new NotificadorEspejo(enviar) };
}

describe('NotificadorEspejo', () => {
  test('el recorrido completo dos veces (1 Hz + reconexión) da 5 notificaciones únicas', () => {
    const { enviar, notificador } = nuevo();
    // Cada mensaje repetido (como a 1 Hz) y luego el recorrido otra vez (como tras reconectar).
    for (const m of espejos) {
      notificador.procesar(m);
      notificador.procesar(m);
    }
    espejos.forEach((m) => notificador.procesar(m));

    expect(enviar).toHaveBeenCalledTimes(5);
    const avisos = enviar.mock.calls.map(([a]) => a);
    const titulos = avisos.map((a) => a.titulo);
    expect(new Set(titulos)).toEqual(
      new Set(['Puesto asignado', 'Sesión iniciada', 'Saliendo del puesto', 'Sesión cerrada', 'Saldo bajo']),
    );
    titulos.forEach((t) => expect(titulos.filter((x) => x === t)).toHaveLength(1));

    const cuerpo = (titulo: string) => avisos.find((a) => a.titulo === titulo)!.cuerpo;
    expect(cuerpo('Puesto asignado')).toMatch(/Puesto asignado a \d+ m/);
    expect(cuerpo('Sesión iniciada')).toContain('retenido $');
    expect(cuerpo('Sesión cerrada')).toContain('Cobrado $');
    expect(cuerpo('Sesión cerrada')).toContain('ahorraste $');
    expect(cuerpo('Saldo bajo')).toMatch(/Disponible \$\d+,\d\d/);
  });

  test('el orden de los avisos sigue las transiciones del recorrido', () => {
    const { enviar, notificador } = nuevo();
    espejos.forEach((m) => notificador.procesar(m));
    const orden = enviar.mock.calls.map(([a]) => a.titulo);
    expect(orden.indexOf('Puesto asignado')).toBeLessThan(orden.indexOf('Sesión iniciada'));
    expect(orden.indexOf('Sesión iniciada')).toBeLessThan(orden.indexOf('Saliendo del puesto'));
    expect(orden.indexOf('Saliendo del puesto')).toBeLessThan(orden.indexOf('Sesión cerrada'));
  });

  test('otro veh_id vuelve a notificar', () => {
    const { enviar, notificador } = nuevo();
    espejos.forEach((m) => notificador.procesar(m));
    generarRecorrido('sim_veh7')
      .filter((m): m is MensajeEspejo => m.tipo === 'espejo')
      .forEach((m) => notificador.procesar(m));
    expect(enviar).toHaveBeenCalledTimes(10);
  });

  test('reiniciar() permite notificar de nuevo', () => {
    const { enviar, notificador } = nuevo();
    espejos.forEach((m) => notificador.procesar(m));
    notificador.reiniciar();
    espejos.forEach((m) => notificador.procesar(m));
    expect(enviar).toHaveBeenCalledTimes(10);
  });

  test('procesar() devuelve los avisos nuevos de ese mensaje', () => {
    const { notificador } = nuevo();
    const guiado = espejos.find((m) => m.estado === 'GUIADO')!;
    expect(notificador.procesar(guiado).map((a) => a.titulo)).toContain('Puesto asignado');
    expect(notificador.procesar(guiado)).toEqual([]);
  });
});

describe('textoTransicion', () => {
  test('los estados sin notificación devuelven null', () => {
    for (const estado of ['BUSCANDO', 'A_PIE', 'REGRESANDO'] as const) {
      const m = espejos.find((x) => x.estado === estado)!;
      expect(textoTransicion(m)).toBeNull();
    }
  });

  test('textos con cifras del mensaje', () => {
    const guiado = espejos.find((m) => m.estado === 'GUIADO')!;
    expect(textoTransicion(guiado)!.cuerpo).toBe(`Puesto asignado a ${Math.round(guiado.puesto!.distancia_m)} m`);
    const cerrada = espejos.find((m) => m.estado === 'CERRADA')!;
    expect(textoTransicion(cerrada)!.cuerpo).toBe(
      `Cobrado $${cerrada.recibo!.cobrado_usd.toFixed(2).replace('.', ',')}, ahorraste $${cerrada.recibo!.ahorro_usd.toFixed(2).replace('.', ',')}`,
    );
    expect(textoTransicion({ ...guiado, puesto: null })!.cuerpo).toBe('Puesto asignado');
  });
});
