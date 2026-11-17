import { afterEach, beforeEach, describe, expect, jest, test } from '@jest/globals';

import { TARIFA } from '@/src/api/tarifa';
import {
  VENTANA_COMBINAR_MS,
  calcularAvisos,
  escalaTiempo,
  estadoBloqueo,
} from '@/src/logica/calcularAvisos';

// Con TARIFA: $0.50/h → 1 min = $0.5/60. Aviso de saldo 10 min antes; tope 120 min, aviso a 110.
const INICIO = '2026-11-08T15:00:00.000Z';
const T0 = Date.parse(INICIO);
const sesion = { sesion_id: 'ses_1', inicio: INICIO };
const MIN = 60_000;

/** Disponible que cubre exactamente `m` minutos. */
const disponiblePara = (m: number) => (m * TARIFA.valor_hora_usd) / 60;

beforeEach(() => {
  jest.useFakeTimers();
  jest.setSystemTime(T0);
});

afterEach(() => {
  jest.useRealTimers();
});

describe('calcularAvisos', () => {
  test('$0.25 (30 min): saldo_bajo a +20 min y tiempo_maximo a +110 min, separados y ordenados', () => {
    const avisos = calcularAvisos(sesion, { disponible: 0.25 }, TARIFA, new Date(T0));
    expect(avisos.map((a) => a.tipo)).toEqual(['saldo_bajo', 'tiempo_maximo']);
    expect(avisos[0].cuando.getTime()).toBe(T0 + 20 * MIN);
    expect(avisos[1].cuando.getTime()).toBe(T0 + 110 * MIN);
    expect(avisos[0].cuando.getTime()).toBeLessThan(avisos[1].cuando.getTime());
    expect(avisos[0].cuerpo).toContain('10 min');
    expect(avisos[1].cuerpo).toContain('120 min');
  });

  test('$1.00 (120 min) con tope 120: ambos a +110 min → un solo aviso combinado', () => {
    const avisos = calcularAvisos(sesion, { disponible: 1.0 }, TARIFA, new Date(T0));
    expect(avisos).toHaveLength(1);
    const [a] = avisos;
    expect(a.tipo).toBe('saldo_bajo_y_tiempo_maximo');
    expect(a.cuando.getTime()).toBe(T0 + 110 * MIN);
    expect(a.cuerpo).toContain('Tu saldo alcanza para unos 10 min más');
    expect(a.cuerpo).toContain('llegas al máximo de 120 min');
  });

  test('ventana de combinación: a 59 s se combinan, a 61 s no', () => {
    expect(VENTANA_COMBINAR_MS).toBe(60_000);
    // El aviso de saldo cae a 110 min + 59 s (el de tope está a 110 min).
    const a59 = calcularAvisos(sesion, { disponible: disponiblePara(120 + 59 / 60) }, TARIFA, new Date(T0));
    expect(a59).toHaveLength(1);
    expect(a59[0].tipo).toBe('saldo_bajo_y_tiempo_maximo');
    expect(a59[0].cuando.getTime()).toBe(T0 + 110 * MIN); // el más temprano

    const a61 = calcularAvisos(sesion, { disponible: disponiblePara(120 + 61 / 60) }, TARIFA, new Date(T0));
    expect(a61.map((a) => a.tipo)).toEqual(['tiempo_maximo', 'saldo_bajo']);
    expect(a61[1].cuando.getTime() - a61[0].cuando.getTime()).toBeGreaterThan(VENTANA_COMBINAR_MS);

    // También 59 s antes del tope.
    const antes = calcularAvisos(sesion, { disponible: disponiblePara(120 - 59 / 60) }, TARIFA, new Date(T0));
    expect(antes).toHaveLength(1);
    expect(antes[0].cuando.getTime()).toBeCloseTo(T0 + 110 * MIN - 59_000, -1);
  });

  test('los avisos en el pasado se disparan ya (cuando === ahora)', () => {
    const ahora = new Date(T0 + 25 * MIN); // después del saldo_bajo (+20 min)
    jest.setSystemTime(ahora);
    const avisos = calcularAvisos(sesion, { disponible: 0.25 }, TARIFA, ahora);
    const saldo = avisos.find((a) => a.tipo === 'saldo_bajo')!;
    expect(saldo.cuando.getTime()).toBe(ahora.getTime());
    expect(saldo.cuando).not.toBe(ahora); // copia, no la misma referencia
    const tope = avisos.find((a) => a.tipo === 'tiempo_maximo')!;
    expect(tope.cuando.getTime()).toBe(T0 + 110 * MIN);
  });

  test('disponible 0 o negativo: saldo_bajo de inmediato', () => {
    const avisos = calcularAvisos(sesion, { disponible: -0.3 }, TARIFA, new Date(T0));
    expect(avisos[0].tipo).toBe('saldo_bajo');
    expect(avisos[0].cuando.getTime()).toBe(T0);
    expect(avisos[0].cuerpo).toContain('0 min');
  });

  test('escala 60 (demo): saldo_bajo a +20 s con $0.25', () => {
    const avisos = calcularAvisos(sesion, { disponible: 0.25 }, TARIFA, new Date(T0), 60);
    expect(avisos[0].tipo).toBe('saldo_bajo');
    expect(avisos[0].cuando.getTime()).toBe(T0 + 20_000);
    expect(avisos[1].cuando.getTime()).toBe(T0 + 110_000);
  });

  test('una recarga a mitad de sesión mueve saldo_bajo más tarde', () => {
    const ahora = new Date(T0 + 5 * MIN);
    jest.setSystemTime(ahora);
    const antes = calcularAvisos(sesion, { disponible: 0.25 }, TARIFA, ahora);
    const despues = calcularAvisos(sesion, { disponible: 5.25 }, TARIFA, ahora);
    const saldoAntes = antes.find((a) => a.tipo === 'saldo_bajo')!;
    const saldoDespues = despues.find((a) => a.tipo === 'saldo_bajo')!;
    expect(saldoAntes.cuando.getTime()).toBe(T0 + 20 * MIN);
    expect(saldoDespues.cuando.getTime()).toBe(T0 + 620 * MIN);
    expect(saldoDespues.cuando.getTime()).toBeGreaterThan(saldoAntes.cuando.getTime());
    // Ahora el tope va primero.
    expect(antes.map((a) => a.tipo)).toEqual(['saldo_bajo', 'tiempo_maximo']);
    expect(despues.map((a) => a.tipo)).toEqual(['tiempo_maximo', 'saldo_bajo']);
  });
});

describe('escalaTiempo', () => {
  test('lee números positivos y cae a 1 si no es válido', () => {
    expect(escalaTiempo('60')).toBe(60);
    expect(escalaTiempo(undefined)).toBe(1);
    expect(escalaTiempo('abc')).toBe(1);
    expect(escalaTiempo('0')).toBe(1);
    expect(escalaTiempo('-5')).toBe(1);
  });
});

describe('estadoBloqueo', () => {
  test('saldo −0.20: bloqueado por saldo negativo, deuda 0.20, recarga ≥ 5', () => {
    const e = estadoBloqueo({ saldo: -0.2, disponible: -0.2 });
    expect(e.bloqueado).toBe(true);
    expect(e.motivo).toBe('saldo_negativo');
    expect(e.deuda).toBeCloseTo(0.2, 10);
    expect(e.recargaSugerida).toBeGreaterThanOrEqual(TARIFA.recarga_minima_usd);
    expect(e.recargaSugerida).toBeGreaterThanOrEqual(e.deuda + 0.25);
  });

  test('tras recargar $5 (saldo 4.80) ya no está bloqueado', () => {
    const e = estadoBloqueo({ saldo: -0.2 + 5, disponible: 4.8 });
    expect(e).toEqual({ bloqueado: false, motivo: null, deuda: 0, recargaSugerida: 0 });
  });

  test('disponible 0.10 con saldo ≥ 0: bloqueado por disponible insuficiente, recarga 5', () => {
    const e = estadoBloqueo({ saldo: 0.1, disponible: 0.1 });
    expect(e.bloqueado).toBe(true);
    expect(e.motivo).toBe('disponible_insuficiente');
    expect(e.deuda).toBe(0);
    expect(e.recargaSugerida).toBe(5);
  });

  test('disponible justo el bloque ($0.25) no bloquea', () => {
    expect(estadoBloqueo({ saldo: 0.25, disponible: 0.25 }).bloqueado).toBe(false);
  });

  test('con la bandera bloqueada: true está bloqueado aunque haya saldo', () => {
    const e = estadoBloqueo({ saldo: 10, disponible: 10, bloqueada: true });
    expect(e.bloqueado).toBe(true);
    expect(e.motivo).toBe('saldo_negativo');
    expect(e.deuda).toBe(0);
    expect(e.recargaSugerida).toBe(5);
  });

  test('deuda grande: la recarga sugerida cubre deuda + bloque', () => {
    const e = estadoBloqueo({ saldo: -4.9, disponible: -4.9 }, { ...TARIFA, saldo_negativo_max_usd: 10 });
    expect(e.recargaSugerida).toBe(5.15);
  });
});

describe('ventana de combinación con la escala de demo (regresión S3-2)', () => {
  test('con escala 60, avisos a 59 min de la regla (59 s reales) NO se combinan', () => {
    // disponible $0.51 → 61.2 min cubiertos → saldo_bajo a 51.2 min; tope a 110 min: 58.8 min de diferencia.
    const avisos = calcularAvisos({ sesion_id: 'ses_x', inicio: '2026-11-09T01:04:15Z' }, { disponible: 0.51 }, undefined, new Date('2026-11-09T01:04:15Z'), 60);
    expect(avisos.map((a) => a.tipo)).toEqual(['saldo_bajo', 'tiempo_maximo']);
  });

  test('con escala 60, avisos a menos de 1 min de la regla (< 1 s real) sí se combinan', () => {
    // disponible $1.00 → 120 min → saldo_bajo a 110 min, igual que el tope.
    const avisos = calcularAvisos({ sesion_id: 'ses_x', inicio: '2026-11-09T01:04:15Z' }, { disponible: 1 }, undefined, new Date('2026-11-09T01:04:15Z'), 60);
    expect(avisos).toHaveLength(1);
    expect(avisos[0].tipo).toBe('saldo_bajo_y_tiempo_maximo');
  });
});
