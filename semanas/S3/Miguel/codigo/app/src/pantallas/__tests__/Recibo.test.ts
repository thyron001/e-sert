import { describe, expect, it, jest } from '@jest/globals';

jest.mock('@react-native-async-storage/async-storage', () => ({ getItem: jest.fn(), setItem: jest.fn() }));

import { comparacionTarjeta, horaGuayaquil } from '@/src/pantallas/Recibo';
import type { DatosRecibo } from '@/src/servicios/seguimientoSesion';

const base: DatosRecibo = {
  origen: 'propia',
  motivo: 'manual',
  sesion_id: 'ses_1',
  veh_id: null,
  usuario_id: 'app_x',
  placa: 'ABC-1234',
  puesto_id: 'pa_1',
  inicio: null,
  fin: null,
  minutos_reales: 47,
  minutos_cobrados: 50,
  cobrado_usd: 0.42,
  tarjeta_sert_usd: null,
  ahorro_usd: null,
  saldo: 4.58,
};

describe('Recibo', () => {
  it('hora en America/Guayaquil (UTC−5)', () => {
    expect(horaGuayaquil('2026-11-08T17:05:00Z')).toBe('08/11 12:05');
    expect(horaGuayaquil('2026-11-08T03:30:00.000Z')).toBe('07/11 22:30');
    expect(horaGuayaquil(null)).toBe('—');
  });

  it('sesión propia: la tarjeta se calcula con tarifa.ts (2 bloques, $0.50, ahorro $0.08)', () => {
    expect(comparacionTarjeta(base)).toEqual({ tarjeta: 0.5, ahorro: 0.08, bloques: 2, delServidor: false });
  });

  it('espejo: manda el recibo del servidor', () => {
    const r = comparacionTarjeta({ ...base, origen: 'espejo', tarjeta_sert_usd: 0.75, ahorro_usd: 0.33 });
    expect(r).toMatchObject({ tarjeta: 0.75, ahorro: 0.33, delServidor: true });
  });

  it('120 min: sin ahorro', () => {
    expect(comparacionTarjeta({ ...base, minutos_reales: 120, minutos_cobrados: 120, cobrado_usd: 1 }).ahorro).toBe(0);
  });
});
