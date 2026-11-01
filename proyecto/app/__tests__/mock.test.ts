import { describe, expect, it } from '@jest/globals';

import { crearClienteMock } from '@/src/api/mock';
import { montoRetencion } from '@/src/api/tarifa';
import { ErrorApi, type ApiESert } from '@/src/api/tipos';

const T0 = Date.parse('2026-10-27T15:00:00Z');
const minutos = (m: number) => new Date(T0 + m * 60_000).toISOString();

async function error(promesa: Promise<unknown>): Promise<ErrorApi> {
  try {
    await promesa;
  } catch (e) {
    return e as ErrorApi;
  }
  throw new Error('se esperaba un rechazo');
}

async function primerPuestoLibre(api: ApiESert): Promise<string> {
  const puestos = await api.listarPuestos();
  return puestos.find((p) => p.ocupados < p.capacidad)!.puesto_id;
}

/**
 * Deja al usuario con disponible < retención. El contrato dice que una billetera nueva tiene
 * saldo 0, pero el mock arranca con $5 de demo: si es así, se gasta con una sesión larga
 * (600 min = $5.00) y el saldo queda exactamente en 0, sin bloquear.
 */
async function dejarSinSaldo(api: ApiESert, usuario: string, puesto: string): Promise<void> {
  const b = await api.obtenerBilletera(usuario);
  if (b.disponible < montoRetencion()) return;
  const minutosParaVaciar = (b.saldo / 0.5) * 60;
  const s = await api.crearSesion({ usuario_id: usuario, placa: 'ABC-123', puesto_id: puesto, ts: minutos(0) });
  await api.cerrarSesion(s.sesion_id, { ts: minutos(minutosParaVaciar), motivo: 'manual' });
  const vacia = await api.obtenerBilletera(usuario);
  expect(vacia.saldo).toBe(0);
}

describe('cliente mock (mismas reglas que el backend)', () => {
  it('sin saldo → SALDO_INSUFICIENTE; recarga $5 → sesión; segunda sesión → SESION_ACTIVA', async () => {
    const api = crearClienteMock({ latenciaMs: 0 });
    const puesto = await primerPuestoLibre(api);
    await dejarSinSaldo(api, 'u_nuevo', puesto);

    const sinSaldo = await error(api.crearSesion({ usuario_id: 'u_nuevo', placa: 'ABC-1234', puesto_id: puesto }));
    expect(sinSaldo).toBeInstanceOf(ErrorApi);
    expect(sinSaldo.estado).toBe(402);
    expect(sinSaldo.codigo).toBe('SALDO_INSUFICIENTE');

    const recarga = await api.recargar('u_nuevo', { monto: 5 });
    expect(recarga.saldo).toBe(5);

    const creada = await api.crearSesion({
      usuario_id: 'u_nuevo',
      placa: 'abc-1234',
      puesto_id: puesto,
      ts: minutos(1000),
    });
    expect(creada.estado).toBe('ESTACIONADO');
    expect(creada.retenido).toBe(0.25);
    const b = await api.obtenerBilletera('u_nuevo');
    expect(b).toMatchObject({ saldo: 5, retenido: 0.25, disponible: 4.75, bloqueada: false });

    const otra = await error(api.crearSesion({ usuario_id: 'u_nuevo', placa: 'ABC-1234', puesto_id: puesto }));
    expect(otra.estado).toBe(409);
    expect(otra.codigo).toBe('SESION_ACTIVA');
  });

  it('cerrar cobra por fracciones y libera la retención; cerrar dos veces → SESION_YA_CERRADA', async () => {
    const api = crearClienteMock({ latenciaMs: 0 });
    const puesto = await primerPuestoLibre(api);
    await dejarSinSaldo(api, 'u2', puesto);
    await api.recargar('u2', { monto: 5 });
    const s = await api.crearSesion({ usuario_id: 'u2', placa: 'ABC123', puesto_id: puesto, ts: minutos(2000) });

    const cierre = await api.cerrarSesion(s.sesion_id, { ts: minutos(2012), motivo: 'manual' });
    expect(cierre).toEqual({
      sesion_id: s.sesion_id,
      minutos_reales: 12,
      minutos_cobrados: 15,
      debitado: 0.13,
      saldo: 4.87,
    });
    const b = await api.obtenerBilletera('u2');
    expect(b).toMatchObject({ saldo: 4.87, retenido: 0, disponible: 4.87 });
    const sesion = await api.obtenerSesion(s.sesion_id);
    expect(sesion.estado).toBe('CERRADA');

    const repetido = await error(api.cerrarSesion(s.sesion_id, { ts: minutos(2020), motivo: 'manual' }));
    expect(repetido.estado).toBe(409);
    expect(repetido.codigo).toBe('SESION_YA_CERRADA');
  });

  it('recarga menor a la mínima → RECARGA_MINIMA', async () => {
    const api = crearClienteMock({ latenciaMs: 0 });
    const e = await error(api.recargar('u3', { monto: 4.99 }));
    expect(e.estado).toBe(422);
    expect(e.codigo).toBe('RECARGA_MINIMA');
  });
});
