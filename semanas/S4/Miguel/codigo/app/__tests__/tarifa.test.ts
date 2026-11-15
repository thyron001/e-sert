import { describe, expect, it } from '@jest/globals';

import { TARIFA, costoMinutos, minutosCobrados, montoRetencion } from '@/src/api/tarifa';
import tarifaJson from '@/src/contrato/tarifa.json';

describe('tarifa del contrato (§5)', () => {
  it('TARIFA es exactamente src/contrato/tarifa.json', () => {
    expect(TARIFA).toEqual(tarifaJson);
  });

  it.each([
    [12, 15],
    [3, 10],
    [0, 10],
    [10, 10],
    [10.01, 15],
    [47, 50],
  ])('%p min reales → %p min cobrados', (reales, cobrados) => {
    expect(minutosCobrados(reales)).toBe(cobrados);
  });

  it('costo al centavo, mitad hacia arriba', () => {
    expect(costoMinutos(50)).toBe(0.42);
    // 15 min = 0.125 USD → 0.13 (ROUND_HALF_UP, no el redondeo bancario).
    expect(costoMinutos(15)).toBe(0.13);
  });

  it('la retención es el bloque mínimo de 30 min = $0.25', () => {
    expect(montoRetencion()).toBe(0.25);
  });

  // Valores de referencia de proyecto/comun/tarifa.py (Freddy). Se obtuvieron ejecutando, desde
  // proyecto/ y con pydantic instalado:
  //   python3 -c "from comun.tarifa import *; t = cargar_tarifa();
  //     [print(m, minutos_cobrados(m, t), costo_usd(minutos_cobrados(m, t), t)) for m in [...]]"
  // Si cambia tarifa.json o tarifa.py, hay que volver a generarlos.
  const PYTHON: [number, number, number][] = [
    // [minutos_reales, minutos_cobrados, costo_usd]
    [0, 10, 0.08],
    [3, 10, 0.08],
    [5, 10, 0.08],
    [9.99, 10, 0.08],
    [10, 10, 0.08],
    [12, 15, 0.13],
    [29, 30, 0.25],
    [30, 30, 0.25],
    [31, 35, 0.29],
    [47, 50, 0.42],
    [59, 60, 0.5],
    [60, 60, 0.5],
    [61, 65, 0.54],
    [119, 120, 1.0],
    [120, 120, 1.0],
    [121, 125, 1.04],
  ];

  it.each(PYTHON)('igual que tarifa.py: %p min → %p cobrados, $%p', (reales, cobrados, costo) => {
    expect(minutosCobrados(reales)).toBe(cobrados);
    expect(costoMinutos(minutosCobrados(reales))).toBe(costo);
  });
});
