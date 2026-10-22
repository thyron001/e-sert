import type { Tarifa } from './tipos';

// SINCRONIZAR con comun/tarifa.json (docs/CONTRATO.md, sección 5). Valores provisionales.
export const TARIFA: Tarifa = {
  valor_hora_usd: 0.5,
  bloque_minimo_min: 30,
  fraccion_min: 5,
  cobro_minimo_min: 10,
  saldo_negativo_max_usd: 0.5,
  aviso_saldo_min: 10,
  tiempo_maximo_min: 120,
  recarga_minima_usd: 5.0,
};

export function redondearCentavos(valor: number): number {
  return Math.round(valor * 100) / 100;
}

export function costoMinutos(minutos: number, tarifa: Tarifa = TARIFA): number {
  return redondearCentavos((minutos * tarifa.valor_hora_usd) / 60);
}

/** Monto que se retiene al confirmar la llegada (bloque mínimo). */
export function montoRetencion(tarifa: Tarifa = TARIFA): number {
  return costoMinutos(tarifa.bloque_minimo_min, tarifa);
}

/** Minutos que se cobran: fracciones de `fraccion_min` hacia arriba, con un mínimo de cobro. */
export function minutosCobrados(minutosReales: number, tarifa: Tarifa = TARIFA): number {
  const fracciones = Math.ceil(Math.max(0, minutosReales) / tarifa.fraccion_min - 1e-9);
  return Math.max(tarifa.cobro_minimo_min, fracciones * tarifa.fraccion_min);
}
