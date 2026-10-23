import { describe, expect, jest, test } from '@jest/globals';

import { costoMinutos, minutosCobrados, tarjetaSertUsd } from '@/src/api/tarifa';
import { ESTADOS_SESION, type MensajeEspejo } from '@/src/api/tipos';
import { MINUTOS_SESION, candidatosMock, generarRecorrido, suscribirMock } from '../recorridoMock';
import recorridoJson from '../recorrido_mock.json';
import { esFinEspejo, esMensajeEspejo } from '../validar';

const recorrido = generarRecorrido('sim_veh42');
const espejos = recorrido.filter((m): m is MensajeEspejo => m.tipo === 'espejo');

describe('recorrido mock del espejo (CONTRATO §6b)', () => {
  test('todos los mensajes cumplen el tipo y termina con espejo_fin', () => {
    const malos = espejos.filter((m) => !esMensajeEspejo(m));
    expect(malos).toEqual([]);
    expect(espejos.length).toBe(recorrido.length - 1);
    expect(esFinEspejo(recorrido[recorrido.length - 1])).toBe(true);
  });

  test('recorrido_mock.json está al día y cada mensaje cumple 6b', () => {
    expect(recorridoJson).toEqual(JSON.parse(JSON.stringify(recorrido)));
    const json = recorridoJson as unknown[];
    expect(json.slice(0, -1).every(esMensajeEspejo)).toBe(true);
    expect(esFinEspejo(json[json.length - 1])).toBe(true);
  });

  test('pasa por los 7 estados en orden y nunca retrocede', () => {
    const indices = espejos.map((m) => ESTADOS_SESION.indexOf(m.estado!));
    indices.slice(1).forEach((v, i) => expect(v).toBeGreaterThanOrEqual(indices[i]));
    expect(new Set(espejos.map((m) => m.estado))).toEqual(new Set(ESTADOS_SESION));
    expect(espejos[0].estado).toBe('BUSCANDO');
  });

  test('t_sim crece y la sesión dura 47 min simulados', () => {
    espejos.slice(1).forEach((m, i) => expect(m.t_sim).toBeGreaterThan(espejos[i].t_sim));
    const llegada = espejos.find((m) => m.estado === 'ESTACIONADO')!;
    const cierre = espejos.find((m) => m.estado === 'CERRADA')!;
    expect((cierre.t_sim - llegada.t_sim) / 60).toBeCloseTo(MINUTOS_SESION, 5);
  });

  test('el recibo cuadra con la tarifa (47 min -> 50 cobrados, $0,42; tarjeta $0,50; ahorro $0,08)', () => {
    const recibo = espejos.find((m) => m.recibo)!.recibo!;
    expect(recibo.minutos_reales).toBe(47);
    expect(recibo.minutos_cobrados).toBe(minutosCobrados(47));
    expect(recibo.minutos_cobrados).toBe(50);
    expect(recibo.cobrado_usd).toBe(costoMinutos(50));
    expect(recibo.cobrado_usd).toBe(0.42);
    expect(recibo.tarjeta_sert_usd).toBe(tarjetaSertUsd(47));
    expect(recibo.tarjeta_sert_usd).toBe(0.5);
    expect(recibo.ahorro_usd).toBe(0.08);
    // El recibo solo aparece al cerrar.
    expect(espejos.filter((m) => m.recibo).every((m) => m.estado === 'CERRADA')).toBe(true);
  });

  test('sesion_id con formato ses_<uuid4> (CONTRATO §1)', () => {
    const ids = new Set(espejos.filter((m) => m.sesion).map((m) => m.sesion!.sesion_id));
    expect(ids.size).toBe(1);
    expect([...ids][0]).toMatch(/^ses_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });

  test('hay aviso saldo_bajo en algún tramo de ESTACIONADO', () => {
    expect(espejos.some((m) => m.estado === 'ESTACIONADO' && m.avisos.includes('saldo_bajo'))).toBe(true);
  });

  test('GUIADO trae puesto y ruta; BUSCANDO no trae puesto', () => {
    espejos.filter((m) => m.estado === 'BUSCANDO').forEach((m) => expect(m.puesto).toBeNull());
    espejos.filter((m) => m.estado === 'GUIADO').forEach((m) => {
      expect(m.puesto).not.toBeNull();
      expect(m.ruta.length).toBeGreaterThan(0);
    });
  });

  test('a 1 mensaje por segundo, la duración total está entre 55 y 65 s', () => {
    const duracion = (Date.parse(recorrido[recorrido.length - 1].ts!) - Date.parse(recorrido[0].ts!)) / 1000 + 1;
    expect(duracion).toBeGreaterThanOrEqual(55);
    expect(duracion).toBeLessThanOrEqual(65);
  });

  test('suscribirMock emite todo el recorrido y se puede cancelar', () => {
    jest.useFakeTimers();
    const recibidos: unknown[] = [];
    const cancelar = suscribirMock('sim_veh42', (m) => recibidos.push(m));
    jest.advanceTimersByTime(30_000);
    expect(recibidos.length).toBe(31);
    jest.advanceTimersByTime(60_000);
    expect(recibidos.length).toBe(recorrido.length);
    cancelar();
    jest.useRealTimers();
  });

  test('candidatos: 3 a 5, y cada uno genera un recorrido válido', () => {
    const candidatos = candidatosMock();
    expect(candidatos.length).toBeGreaterThanOrEqual(3);
    expect(candidatos.length).toBeLessThanOrEqual(5);
    for (const c of candidatos) {
      const r = generarRecorrido(c.id);
      expect(r.slice(0, -1).every(esMensajeEspejo)).toBe(true);
      expect(r[0].veh_id).toBe(c.id);
    }
  });
});
