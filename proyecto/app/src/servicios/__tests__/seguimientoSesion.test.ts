import { describe, expect, it, jest } from '@jest/globals';

import type { MensajeEspejo, Sesion } from '@/src/api/tipos';
import { compararConServidor } from '@/src/logica/tarifa';
import { generarRecorridoCierre, SEGUNDOS_HASTA_CIERRE, suscribirCierreMock } from '@/src/mocks/cierreMock';
import { DetectorCierre, motivoDeducido } from '@/src/servicios/seguimientoSesion';

const espejos = (vehId = 'sim_veh42') =>
  generarRecorridoCierre(vehId).filter((m): m is MensajeEspejo => m.tipo === 'espejo');

const sesionCerrada: Sesion = {
  sesion_id: 'ses_00000000-0000-4000-8000-000000000001',
  usuario_id: 'app_x',
  placa: 'ABC-1234',
  puesto_id: 'pa_1',
  estado: 'CERRADA',
  inicio: '2026-11-08T15:00:00Z',
  fin: '2026-11-08T15:47:00Z',
  retenido: 0.25,
  minutos_reales: 47,
  minutos_cobrados: 50,
  debitado: 0.42,
};

describe('cierreMock (modo mock de S3-1)', () => {
  it(`emite CERRADA con recibo ${SEGUNDOS_HASTA_CIERRE} s después del primer ESTACIONADO`, () => {
    const ms = espejos();
    const llegada = ms.findIndex((m) => m.estado === 'ESTACIONADO');
    const cierre = ms.findIndex((m) => m.estado === 'CERRADA');
    expect(cierre - llegada).toBe(SEGUNDOS_HASTA_CIERRE);
    expect(ms[cierre].recibo).not.toBeNull();
  });

  it('conserva todos los estados de la sesión y termina con espejo_fin', () => {
    const recorrido = generarRecorridoCierre();
    const estados = new Set(espejos().map((m) => m.estado));
    for (const e of ['BUSCANDO', 'GUIADO', 'ESTACIONADO', 'A_PIE', 'REGRESANDO', 'SALIENDO', 'CERRADA']) {
      expect(estados.has(e as MensajeEspejo['estado'])).toBe(true);
    }
    expect(recorrido[recorrido.length - 1].tipo).toBe('espejo_fin');
  });

  it('el recibo cuadra con tarifa.ts (47 min → 50 min, $0.42; tarjeta $0.50; ahorro $0.08)', () => {
    const r = espejos().find((m) => m.recibo)!.recibo!;
    expect(r).toMatchObject({ minutos_cobrados: 50, cobrado_usd: 0.42, tarjeta_sert_usd: 0.5, ahorro_usd: 0.08 });
    expect(compararConServidor(r).ok).toBe(true);
  });

  it('suscribirCierreMock entrega CERRADA a los 20 s de estacionar, con reloj falso', () => {
    jest.useFakeTimers();
    const recibidos: { estado: unknown; t: number }[] = [];
    let t = 0;
    const quitar = suscribirCierreMock('sim_veh42', (m) => recibidos.push({ estado: (m as MensajeEspejo).estado, t }));
    for (let i = 0; i < 70; i++) {
      t += 1000;
      jest.advanceTimersByTime(1000);
    }
    quitar();
    jest.useRealTimers();
    const llegada = recibidos.find((x) => x.estado === 'ESTACIONADO')!.t;
    const cierre = recibidos.find((x) => x.estado === 'CERRADA')!.t;
    expect(cierre - llegada).toBe(SEGUNDOS_HASTA_CIERRE * 1000);
  });
});

describe('DetectorCierre (el cierre se procesa una sola vez)', () => {
  it('modo espejo: CERRADA con recibo da un solo cierre con los montos del servidor', () => {
    const d = new DetectorCierre({ origen: 'espejo', veh_id: 'sim_veh42' });
    const eventos = [...espejos(), ...espejos()].map((m) => d.mensaje(m)).filter(Boolean);
    expect(eventos).toHaveLength(1);
    const ev = eventos[0]!;
    expect(ev.tipo).toBe('cierre');
    if (ev.tipo !== 'cierre') return;
    expect(ev.datos).toMatchObject({
      origen: 'espejo',
      veh_id: 'sim_veh42',
      motivo: 'deteccion', // se vio SALIENDO antes de CERRADA
      cobrado_usd: 0.42,
      tarjeta_sert_usd: 0.5,
      ahorro_usd: 0.08,
      puesto_id: 'pa_337277973#1_0',
    });
    expect(ev.datos.sesion_id).toMatch(/^ses_/);
    expect(ev.datos.inicio).not.toBeNull();
  });

  it('tras el cierre por WS, el respaldo REST y el espejo_fin ya no generan nada', () => {
    const d = new DetectorCierre({ origen: 'espejo' });
    espejos().forEach((m) => d.mensaje(m));
    expect(d.cerrado).toBe(true);
    expect(d.sesion(sesionCerrada)).toBeNull();
    expect(d.fin({ tipo: 'espejo_fin', veh_id: 'sim_veh42' })).toBeNull();
  });

  it('espejo_fin sin recibo: "salió de la simulación"', () => {
    const d = new DetectorCierre({ origen: 'espejo' });
    espejos().filter((m) => m.estado !== 'CERRADA').forEach((m) => d.mensaje(m));
    expect(d.fin({ tipo: 'espejo_fin', veh_id: 'sim_veh42', motivo: 'salio_simulacion' })).toEqual({ tipo: 'salio' });
  });

  it('sesión propia: GET /sesiones abierta no cierra; CERRADA cierra una vez', () => {
    const d = new DetectorCierre({ origen: 'propia', usuario_id: 'app_x', placa: 'ABC-1234' });
    expect(d.sesion({ ...sesionCerrada, estado: 'ESTACIONADO', fin: null, debitado: null })).toBeNull();
    const ev = d.sesion(sesionCerrada, 4.58);
    expect(ev).toMatchObject({
      tipo: 'cierre',
      datos: { origen: 'propia', placa: 'ABC-1234', cobrado_usd: 0.42, minutos_cobrados: 50, saldo: 4.58, tarjeta_sert_usd: null },
    });
    expect(d.sesion(sesionCerrada)).toBeNull();
  });

  it('cierre manual: motivo manual y luego el sondeo ya no repite', () => {
    const d = new DetectorCierre({ origen: 'propia' });
    const ev = d.cierreManual({ sesion_id: sesionCerrada.sesion_id, minutos_reales: 12, minutos_cobrados: 15, debitado: 0.13, saldo: 4.87 });
    expect(ev).toMatchObject({ tipo: 'cierre', datos: { motivo: 'manual', cobrado_usd: 0.13, saldo: 4.87 } });
    expect(d.sesion(sesionCerrada)).toBeNull();
    expect(d.cierreManual({ sesion_id: 'x', minutos_reales: 1, minutos_cobrados: 10, debitado: 0.08, saldo: 0 })).toBeNull();
  });

  it('motivo deducido: tope de tiempo → timeout_sin_senal; SALIENDO → deteccion; si no, desconocido', () => {
    expect(motivoDeducido(120, 'A_PIE')).toBe('timeout_sin_senal');
    expect(motivoDeducido(47, 'SALIENDO')).toBe('deteccion');
    expect(motivoDeducido(47, 'A_PIE')).toBeNull();
    // espejo: sin SALIENDO visible (ritmo acelerado), el cierre igual es de la simulación
    expect(motivoDeducido(4.15, 'A_PIE', 'espejo')).toBe('deteccion');
  });
});
