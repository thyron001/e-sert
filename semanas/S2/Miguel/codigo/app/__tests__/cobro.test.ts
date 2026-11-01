import { describe, expect, it } from '@jest/globals';

import { cronometro, resumenCobro } from '@/src/sesion/cobro';
import { haversineM, simularAvance } from '@/src/sesion/geo';

describe('resumenCobro (pantalla activa)', () => {
  it('cobra fracciones de 5 min con mínimo de 10', () => {
    expect(resumenCobro(3)).toMatchObject({ minutosCobrables: 10, costo: 0.08, avisos: [] });
    expect(resumenCobro(12)).toMatchObject({ minutosCobrables: 15, costo: 0.13 });
  });

  it('avisa del tope de tiempo de 120 min', () => {
    expect(resumenCobro(109).avisos).toEqual([]);
    expect(resumenCobro(111).avisos).toEqual(['tiempo_maximo_cerca']);
    expect(resumenCobro(121).avisos).toEqual(['tiempo_maximo_superado']);
  });

  it('saldo_bajo cuando saldo − costo no cubre 10 min ($0.08)', () => {
    expect(resumenCobro(12, 5).avisos).toEqual([]);
    expect(resumenCobro(12, 0.2).avisos).toEqual(['saldo_bajo']);
    expect(resumenCobro(60, 0).avisos).toEqual(['saldo_agotado']);
  });

  it('formatea el cronómetro', () => {
    expect(cronometro(0)).toBe('0:00:00');
    expect(cronometro(3725)).toBe('1:02:05');
  });
});

describe('guiado simulado', () => {
  const a = { lat: -2.895833, lon: -79.004625 };
  const b = { lat: -2.8968, lon: -79.0047 };

  it('avanza 8 m por paso sin pasarse del puesto', () => {
    const d0 = haversineM(a, b);
    const p = simularAvance(a, b, 8);
    expect(d0 - haversineM(p, b)).toBeCloseTo(8, 0);
    expect(simularAvance(p, b, 1e6)).toEqual(b);
  });
});
