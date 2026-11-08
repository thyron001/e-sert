import { describe, expect, it } from '@jest/globals';

import type { Tarifa } from '@/src/api/tipos';
import {
  TARIFA,
  ahorro,
  bloquesTarjetaSert,
  centavos,
  compararConServidor,
  costo,
  costoEnCurso,
  costoTarjetaSert,
  minutosCobrables,
  retencion,
  usd,
} from '@/src/logica/tarifa';

// Cifras de proyecto/backend/tests/test_tarifa.py y test_sesiones.py (Freddy).

describe('minutosCobrables (minutos_cobrables)', () => {
  it.each([
    // test_minutos_cobrables
    [12, 15],
    [3, 10],
    [0, 10],
    [10, 10],
    [30, 30],
    [47, 50],
    [120, 120],
    // bordes
    [10.01, 15],
    [15, 15],
    [15.0000000001, 15],
    [60, 60],
    [121, 125],
    [-5, 10],
  ])('%p min reales → %p min cobrados', (reales, cobrados) => {
    expect(minutosCobrables(reales)).toBe(cobrados);
  });
});

describe('costo (costo / monto_debito)', () => {
  it.each([
    [12, 0.13], // 15 min · 0,50/60 = 0,125 → 0,13 (mitad hacia arriba)
    [3, 0.08], // mínimo 10 min
    [0, 0.08],
    [10, 0.08],
    [30, 0.25],
    [47, 0.42],
    [60, 0.5],
    [120, 1.0],
    [121, 1.04], // 125 min; el núcleo no corta en tiempo_maximo_min
  ])('%p min reales → $%p', (reales, monto) => {
    expect(costo(reales)).toBe(monto);
  });

  it('retención = bloque mínimo = $0,25 y costo en curso de 12,5 min = $0,10', () => {
    expect(retencion()).toBe(0.25);
    expect(costoEnCurso(12.5)).toBe(0.1);
    expect(costoEnCurso(-3)).toBe(0);
  });
});

describe('tarjeta SERT (costo_tarjeta_sert, bloques de 30 min por adelantado)', () => {
  it.each([
    // test_tarjeta_sert_bloques_30
    [1, 1, 0.25],
    [30, 1, 0.25],
    [31, 2, 0.5],
    [60, 2, 0.5],
    [61, 3, 0.75],
    [120, 4, 1.0],
    // bordes
    [0, 1, 0.25],
    [47, 2, 0.5],
    [121, 5, 1.25],
  ])('%p min → %p bloques = $%p', (reales, bloques, monto) => {
    expect(bloquesTarjetaSert(reales)).toBe(bloques);
    expect(costoTarjetaSert(reales)).toBe(monto);
  });

  it('nunca cobra menos que la app (0,1 a 120 min en décimas)', () => {
    for (let decimas = 10; decimas <= 1200; decimas++) {
      const m = decimas / 10;
      expect(costoTarjetaSert(m)).toBeGreaterThanOrEqual(costo(m));
    }
  });
});

describe('ahorro (tarjeta − app)', () => {
  it.each([
    [47, 0.08], // test_regla3_recargar_iniciar_cerrar_47_min: (0.50, 0.08)
    [12, 0.12], // 1 bloque $0,25 − $0,13
    [42.3, 0.12], // RECIBO de test_espejo: 45 min, $0,38, tarjeta $0,50
    [3, 0.17],
    [30, 0],
    [60, 0],
    [120, 0], // mismo costo con ambos métodos
    [121, 0.21],
  ])('%p min → ahorro $%p', (reales, monto) => {
    expect(ahorro(reales)).toBe(monto);
  });

  it('caso del prompt: 47 min → 50 cobrados, $0,42 app, 2 bloques $0,50, ahorro $0,08', () => {
    expect(minutosCobrables(47)).toBe(50);
    expect(costo(47)).toBe(0.42);
    expect(bloquesTarjetaSert(47)).toBe(2);
    expect(costoTarjetaSert(47)).toBe(0.5);
    expect(ahorro(47)).toBe(0.08);
  });

  it('caso del prompt: 120 min cuesta lo mismo con ambos métodos', () => {
    expect(costo(120)).toBe(costoTarjetaSert(120));
    expect(ahorro(120)).toBe(0);
  });
});

describe('centavos / usd (a_centavos, mitad hacia arriba)', () => {
  it('ida y vuelta como test_centavos_ida_y_vuelta', () => {
    expect(centavos(0.125)).toBe(13);
    expect(usd(centavos(4.58))).toBe(4.58);
    expect(centavos(1.005)).toBe(101); // Decimal(str(1.005)) → 101
    expect(centavos(-0.125)).toBe(-13); // ROUND_HALF_UP aleja del cero
    expect(centavos(0)).toBe(0);
  });
});

describe('parámetros de tarifa', () => {
  it('usa la tarifa que se le pasa', () => {
    const doble: Tarifa = { ...TARIFA, valor_hora_usd: 1.0 };
    expect(costo(47, doble)).toBe(0.83); // 50 min · 1/60 = 0,8333
    expect(costoTarjetaSert(47, doble)).toBe(1.0);
    expect(ahorro(47, doble)).toBe(0.17);
  });
});

describe('compararConServidor', () => {
  const recibo47 = {
    minutos_reales: 47,
    minutos_cobrados: 50,
    cobrado_usd: 0.42,
    tarjeta_sert_usd: 0.5,
    ahorro_usd: 0.08,
  };

  it('ok cuando el recibo coincide', () => {
    expect(compararConServidor(recibo47)).toEqual({ ok: true, diferencias: [] });
  });

  it('ok dentro de $0,01 de tolerancia', () => {
    const r = compararConServidor({ ...recibo47, cobrado_usd: 0.43, tarjeta_sert_usd: 0.49, ahorro_usd: 0.07 });
    expect(r.ok).toBe(true);
    expect(r.diferencias).toEqual([]);
  });

  it('marca diferencias mayores a $0,01', () => {
    const r = compararConServidor({ ...recibo47, cobrado_usd: 0.44, ahorro_usd: 0.06 });
    expect(r.ok).toBe(false);
    expect(r.diferencias).toHaveLength(2);
    expect(r.diferencias[0]).toMatch(/^cobrado_usd/);
    expect(r.diferencias[1]).toMatch(/^ahorro_usd/);
  });

  it('marca minutos cobrados distintos', () => {
    const r = compararConServidor({ ...recibo47, minutos_cobrados: 45 });
    expect(r.ok).toBe(false);
    expect(r.diferencias).toEqual(['minutos_cobrados: servidor 45, local 50']);
  });

  it('RECIBO de test_espejo (42,3 min) cuadra', () => {
    const r = compararConServidor({
      minutos_reales: 42.3,
      minutos_cobrados: 45,
      cobrado_usd: 0.38,
      tarjeta_sert_usd: 0.5,
      ahorro_usd: 0.12,
    });
    expect(r).toEqual({ ok: true, diferencias: [] });
  });
});
