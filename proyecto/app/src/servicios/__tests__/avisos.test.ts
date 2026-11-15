import { afterEach, beforeEach, describe, expect, jest, test } from '@jest/globals';

// Registro falso de lo programado en expo-notifications: se añade al programar y se borra al
// cancelar, para comprobar que tras cerrar no queda nada pendiente.
const mockRegistro = new Map<string, { trigger: { type: string; date: Date }; content: { data: { tipo: string } } }>();
let mockSiguienteId = 0;

jest.mock('expo-notifications', () => ({
  setNotificationHandler: jest.fn(),
  setNotificationChannelAsync: jest.fn(() => Promise.resolve()),
  requestPermissionsAsync: jest.fn(() => Promise.resolve({ granted: true, status: 'granted' })),
  scheduleNotificationAsync: jest.fn((req: any) => {
    const id = `notif_${++mockSiguienteId}`;
    mockRegistro.set(id, req);
    return Promise.resolve(id);
  }),
  cancelScheduledNotificationAsync: jest.fn((id: string) => {
    mockRegistro.delete(id);
    return Promise.resolve();
  }),
  AndroidImportance: { HIGH: 4 },
  SchedulableTriggerInputTypes: { DATE: 'date' },
}));

// AsyncStorage en memoria.
const mockAlmacen = new Map<string, string>();
jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: {
    getItem: jest.fn((k: string) => Promise.resolve(mockAlmacen.get(k) ?? null)),
    setItem: jest.fn((k: string, v: string) => {
      mockAlmacen.set(k, v);
      return Promise.resolve();
    }),
    removeItem: jest.fn((k: string) => {
      mockAlmacen.delete(k);
      return Promise.resolve();
    }),
  },
}));

import * as Notifications from 'expo-notifications';

import { TARIFA } from '@/src/api/tarifa';
import {
  CLAVE_PROGRAMADOS,
  avisarUnaVez,
  avisosVencidos,
  cancelarAvisos,
  dispararSiVencio,
  leerProgramados,
  olvidarAvisados,
  programarAvisos,
} from '@/src/servicios/avisos';

const INICIO = '2026-11-08T15:00:00.000Z';
const T0 = Date.parse(INICIO);
const MIN = 60_000;
const sesion = { sesion_id: 'ses_1', inicio: INICIO };

const fechasProgramadas = () => [...mockRegistro.values()].map((r) => r.trigger.date.getTime());
const fechaDe = (tipo: string) =>
  [...mockRegistro.values()].find((r) => r.content.data.tipo === tipo)!.trigger.date.getTime();

beforeEach(() => {
  jest.useFakeTimers();
  jest.setSystemTime(T0);
  jest.spyOn(console, 'log').mockImplementation(() => undefined);
  mockRegistro.clear();
  mockAlmacen.clear();
  mockSiguienteId = 0;
  olvidarAvisados();
  jest.clearAllMocks();
});

afterEach(() => {
  jest.useRealTimers();
});

describe('programarAvisos', () => {
  test('programa una notificación por aviso con disparador de fecha y guarda los ids', async () => {
    const prog = await programarAvisos(sesion, { disponible: 0.25 }, TARIFA, new Date(T0), 1);

    expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledTimes(2);
    expect(Notifications.requestPermissionsAsync).toHaveBeenCalled();
    const triggers = (Notifications.scheduleNotificationAsync as jest.Mock).mock.calls.map(
      ([req]: any) => req.trigger,
    );
    // En iOS prepararAvisos devuelve true, así que también va channelId (iOS lo ignora).
    expect(triggers[0]).toEqual(expect.objectContaining({ type: 'date', date: new Date(T0 + 20 * MIN) }));
    expect(triggers[1]).toEqual(expect.objectContaining({ type: 'date', date: new Date(T0 + 110 * MIN) }));

    expect(prog.sesion_id).toBe('ses_1');
    expect(prog.ids).toEqual(['notif_1', 'notif_2']);
    expect(prog.avisos.map((a) => a.tipo)).toEqual(['saldo_bajo', 'tiempo_maximo']);
    expect(prog.avisos[0].cuando).toBe(new Date(T0 + 20 * MIN).toISOString());

    expect(mockAlmacen.has(CLAVE_PROGRAMADOS)).toBe(true);
    expect(await leerProgramados()).toEqual(prog);
  });

  test('un aviso ya vencido se programa al menos 1 s en el futuro', async () => {
    const ahora = new Date(T0 + 25 * MIN);
    jest.setSystemTime(ahora);
    await programarAvisos(sesion, { disponible: 0.25 }, TARIFA, ahora, 1);
    expect(fechaDe('saldo_bajo')).toBe(ahora.getTime() + 1000);
  });

  test('tras cerrar (cancelarAvisos) no queda ninguna notificación programada', async () => {
    await programarAvisos(sesion, { disponible: 0.25 }, TARIFA, new Date(T0), 1);
    expect(mockRegistro.size).toBe(2);

    const canceladas = await cancelarAvisos();

    expect(canceladas).toBe(2);
    expect(mockRegistro.size).toBe(0);
    expect(Notifications.cancelScheduledNotificationAsync).toHaveBeenCalledWith('notif_1');
    expect(Notifications.cancelScheduledNotificationAsync).toHaveBeenCalledWith('notif_2');
    expect(mockAlmacen.has(CLAVE_PROGRAMADOS)).toBe(false);
    expect(await leerProgramados()).toBeNull();
    expect(await cancelarAvisos()).toBe(0); // nada que cancelar la segunda vez
  });

  test('reprogramar tras una recarga cancela los ids anteriores y mueve saldo_bajo más tarde', async () => {
    const primero = await programarAvisos(sesion, { disponible: 0.25 }, TARIFA, new Date(T0), 1);
    const saldoAntes = fechaDe('saldo_bajo');
    expect(saldoAntes).toBe(T0 + 20 * MIN);

    const ahora = new Date(T0 + 5 * MIN);
    jest.setSystemTime(ahora);
    const segundo = await programarAvisos(sesion, { disponible: 5.25 }, TARIFA, ahora, 1);

    for (const id of primero.ids) {
      expect(Notifications.cancelScheduledNotificationAsync).toHaveBeenCalledWith(id);
      expect(mockRegistro.has(id)).toBe(false);
    }
    expect([...mockRegistro.keys()].sort()).toEqual([...segundo.ids].sort());
    expect(segundo.ids).toEqual(['notif_3', 'notif_4']);
    expect(fechaDe('saldo_bajo')).toBe(T0 + 620 * MIN);
    expect(fechaDe('saldo_bajo')).toBeGreaterThan(saldoAntes);
    expect(fechasProgramadas()).toHaveLength(2);
    expect(await leerProgramados()).toEqual(segundo);
  });
});

describe('avisosVencidos', () => {
  test('devuelve solo los avisos con cuando ≤ ahora', async () => {
    const prog = await programarAvisos(sesion, { disponible: 0.25 }, TARIFA, new Date(T0), 1);
    expect(avisosVencidos(prog, T0 + 10 * MIN)).toEqual([]);
    expect(avisosVencidos(prog, T0 + 20 * MIN).map((a) => a.tipo)).toEqual(['saldo_bajo']);
    expect(avisosVencidos(prog, T0 + 200 * MIN).map((a) => a.tipo)).toEqual(['saldo_bajo', 'tiempo_maximo']);
    expect(avisosVencidos(null, T0)).toEqual([]);
    jest.setSystemTime(T0 + 30 * MIN);
    expect(avisosVencidos(prog).map((a) => a.tipo)).toEqual(['saldo_bajo']); // ahora por defecto
  });
});

describe('avisarUnaVez', () => {
  test('la primera vez true y la segunda false', () => {
    expect(avisarUnaVez('saldo_bajo', 'ses_1')).toBe(true);
    expect(avisarUnaVez('saldo_bajo', 'ses_1')).toBe(false);
    expect(avisarUnaVez('saldo_bajo', 'ses_otra')).toBe(true);
  });

  test("el tipo del espejo 'tiempo_maximo_cerca' equivale a 'tiempo_maximo'", () => {
    expect(avisarUnaVez('tiempo_maximo_cerca', 'ses_1')).toBe(true);
    expect(avisarUnaVez('tiempo_maximo', 'ses_1')).toBe(false);
    expect(avisarUnaVez('tiempo_maximo_cerca', 'ses_1')).toBe(false);
  });

  test('tras programarAvisos de ses_2, el espejo ya no repite saldo_bajo', async () => {
    await programarAvisos({ sesion_id: 'ses_2', inicio: INICIO }, { disponible: 0.25 }, TARIFA, new Date(T0), 1);
    expect(avisarUnaVez('saldo_bajo', 'ses_2')).toBe(false);
    expect(avisarUnaVez('tiempo_maximo_cerca', 'ses_2')).toBe(false);
  });

  test('un aviso combinado marca los dos tipos', async () => {
    const prog = await programarAvisos({ sesion_id: 'ses_3', inicio: INICIO }, { disponible: 1.0 }, TARIFA, new Date(T0), 1);
    expect(prog.avisos.map((a) => a.tipo)).toEqual(['saldo_bajo_y_tiempo_maximo']);
    expect(avisarUnaVez('saldo_bajo', 'ses_3')).toBe(false);
    expect(avisarUnaVez('tiempo_maximo_cerca', 'ses_3')).toBe(false);

    olvidarAvisados();
    expect(avisarUnaVez('saldo_bajo_y_tiempo_maximo', 'ses_4')).toBe(true);
    expect(avisarUnaVez('saldo_bajo', 'ses_4')).toBe(false);
    expect(avisarUnaVez('tiempo_maximo', 'ses_4')).toBe(false);
  });
});

describe('dispararSiVencio (app en primer plano)', () => {
  beforeEach(() => {
    mockRegistro.clear();
    mockAlmacen.clear();
    olvidarAvisados();
  });

  test('cuando el aviso vence, cancela el programado y lo notifica ya, una sola vez', async () => {
    await programarAvisos(sesion, { disponible: 0.25 }, TARIFA, new Date(T0));
    const prog = (await leerProgramados())!;
    const idSaldo = prog.ids[prog.avisos.findIndex((a) => a.tipo === 'saldo_bajo')];
    expect(await dispararSiVencio('saldo_bajo', T0 + 19 * MIN)).toBe(false); // aún no vence
    expect(await dispararSiVencio('saldo_bajo', T0 + 20 * MIN)).toBe(true);
    expect(mockRegistro.has(idSaldo)).toBe(false); // la programada inexacta ya no está
    const inmediata = [...mockRegistro.values()].find((r) => (r as { trigger: unknown }).trigger === null);
    expect(inmediata?.content.data.tipo).toBe('saldo_bajo');
    expect(await dispararSiVencio('saldo_bajo', T0 + 21 * MIN)).toBe(false); // no se repite
    // Cerrar después no intenta cancelar la que ya se disparó y no deja nada del tope pendiente.
    await cancelarAvisos();
    expect([...mockRegistro.values()].filter((r) => (r as { trigger: unknown }).trigger !== null)).toHaveLength(0);
  });
});

describe('reprogramar no repite lo ya avisado (defecto del verificador S3-2)', () => {
  beforeEach(() => {
    mockRegistro.clear();
    mockAlmacen.clear();
    olvidarAvisados();
  });

  test('una recarga después de que venció el tope no vuelve a programar el tope', async () => {
    await programarAvisos(sesion, { disponible: 5 }, TARIFA, new Date(T0));
    // Minuto 115: el tope (110) ya venció; se recarga y se reprograma.
    const prog = await programarAvisos(sesion, { disponible: 9.5 }, TARIFA, new Date(T0 + 115 * MIN));
    expect(prog.avisos.map((a) => a.tipo)).toEqual(['saldo_bajo']);
  });

  test('otra sesión sí recibe todos sus avisos', async () => {
    await programarAvisos(sesion, { disponible: 5 }, TARIFA, new Date(T0));
    const otra = await programarAvisos({ sesion_id: 'ses_2', inicio: INICIO }, { disponible: 5 }, TARIFA, new Date(T0 + 115 * MIN));
    expect(otra.avisos.map((a) => a.tipo).sort()).toEqual(['saldo_bajo', 'tiempo_maximo']);
  });
});
