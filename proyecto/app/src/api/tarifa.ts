import tarifaContrato from '@/src/contrato/tarifa.json';
import type { Tarifa } from './tipos';

// Valores de comun/tarifa.json (copia en src/contrato/, verificada con npm run verificar-contrato).
// docs/sert_reglas.md confirma que coinciden con la tarifa real del SERT.
export const TARIFA: Tarifa = tarifaContrato;

export function redondearCentavos(valor: number): number {
  return Math.round(valor * 100) / 100;
}

/** costo_usd(m) del contrato: al centavo, mitad hacia arriba (como Decimal ROUND_HALF_UP en tarifa.py). */
export function costoMinutos(minutos: number, tarifa: Tarifa = TARIFA): number {
  return Math.round((minutos * tarifa.valor_hora_usd * 100) / 60 + 1e-9) / 100;
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

/** Lo que costaría con tarjetas SERT de papel: bloques completos de tarjeta_bloque_min, al menos uno. */
export function tarjetaSertUsd(minutosReales: number, tarifa: Tarifa = TARIFA): number {
  const bloques = Math.max(1, Math.ceil(Math.max(0, minutosReales) / tarifa.tarjeta_bloque_min - 1e-9));
  return redondearCentavos(bloques * costoMinutos(tarifa.tarjeta_bloque_min, tarifa));
}
