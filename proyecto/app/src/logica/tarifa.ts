/**
 * Port a TypeScript de la tarifa del núcleo (`proyecto/backend/nucleo/tarifa.py`, que es una
 * capa fina sobre `proyecto/comun/tarifa.py`).
 *
 * La app muestra siempre los montos que manda el servidor; estas funciones sirven para
 * explicar el cobro (simulaciones, comparativa con la tarjeta SERT) y para comprobar que el
 * recibo del servidor cuadra con la regla 3 de `docs/CONTEXTO.md`.
 *
 * Para no tener dos fórmulas en la app, se reutilizan `costoMinutos` y `minutosCobrados` de
 * `src/api/tarifa.ts` (que ya replican `costo_usd` y `minutos_cobrados` de `comun/tarifa.py`).
 */
import {
  TARIFA,
  costoMinutos,
  minutosCobrados,
  montoRetencion,
  redondearCentavos,
} from '@/src/api/tarifa';
import type { Tarifa } from '@/src/api/tipos';

export { TARIFA };

/** Tolerancia para comparar montos con el servidor (USD). */
export const TOLERANCIA_USD = 0.01;

/** Margen numérico para absorber errores de coma flotante (el mismo 1e-9 que usa Python). */
const EPS = 1e-9;

/**
 * Port de `nucleo.tarifa.minutos_cobrables` → `comun.tarifa.minutos_cobrados`:
 *
 *     fracciones = math.ceil(max(0.0, minutos_reales) / tarifa.fraccion_min - 1e-9)
 *     return max(tarifa.cobro_minimo_min, fracciones * tarifa.fraccion_min)
 *
 * Redondea hacia arriba a `fraccion_min` (5) y aplica `cobro_minimo_min` (10).
 */
export function minutosCobrables(minutosReales: number, t: Tarifa = TARIFA): number {
  return minutosCobrados(minutosReales, t);
}

/**
 * Port de `nucleo.tarifa.costo` → `comun.tarifa.monto_debito`:
 * `costo_usd(minutos_cobrados(m))`, es decir, minutos cobrables × valor_hora / 60, al centavo
 * con mitad hacia arriba (`Decimal.quantize(..., ROUND_HALF_UP)` en Python).
 */
export function costo(minutosReales: number, t: Tarifa = TARIFA): number {
  return costoMinutos(minutosCobrables(minutosReales, t), t);
}

/**
 * Port de `nucleo.tarifa.costo_en_curso`: `costo_usd(max(0.0, m))`, proporcional, sin
 * fracciones ni mínimo (lo que ve el espejo minuto a minuto).
 */
export function costoEnCurso(minutosReales: number, t: Tarifa = TARIFA): number {
  return costoMinutos(Math.max(0, minutosReales), t);
}

/**
 * Bloques de tarjeta SERT que hay que comprar por adelantado. Es la parte entera de
 * `comun.tarifa.tarjeta_sert_usd`:
 *
 *     bloques = max(1, math.ceil(max(0.0, minutos_reales) / tarifa.tarjeta_bloque_min - 1e-9))
 */
export function bloquesTarjetaSert(minutosReales: number, t: Tarifa = TARIFA): number {
  return Math.max(1, Math.ceil(Math.max(0, minutosReales) / t.tarjeta_bloque_min - EPS));
}

/**
 * Port de `nucleo.tarifa.costo_tarjeta_sert` → `comun.tarifa.tarjeta_sert_usd`:
 *
 *     return round(bloques * costo_usd(tarifa.tarjeta_bloque_min, tarifa), 2)
 *
 * Bloques completos de `tarjeta_bloque_min` (30 min) pagados por adelantado, al menos uno.
 */
export function costoTarjetaSert(minutosReales: number, t: Tarifa = TARIFA): number {
  return redondearCentavos(bloquesTarjetaSert(minutosReales, t) * costoMinutos(t.tarjeta_bloque_min, t));
}

/**
 * Ahorro frente a la tarjeta SERT (tarjeta − app). Replica `nucleo.sesiones.recibo`:
 *
 *     ahorro_usd=round(tarjeta - ses.debitado, 2)
 *
 * donde `ses.debitado` es `costo(minutos_reales)`.
 */
export function ahorro(minutosReales: number, t: Tarifa = TARIFA): number {
  return redondearCentavos(costoTarjetaSert(minutosReales, t) - costo(minutosReales, t));
}

/** Port de `nucleo.tarifa.retencion`: monto retenido al iniciar (bloque mínimo). */
export function retencion(t: Tarifa = TARIFA): number {
  return montoRetencion(t);
}

/**
 * Port de `nucleo.tarifa.centavos` → `comun.tarifa.a_centavos`: USD → centavos enteros con
 * mitad hacia arriba (`ROUND_HALF_UP` de Decimal, que aleja del cero los negativos).
 * Python parte de `Decimal(str(usd))`; el `EPS` cubre casos como 1.005 → 101.
 */
export function centavos(usd: number): number {
  const signo = usd < 0 ? -1 : 1;
  const r = Math.round(Math.abs(usd) * 100 + EPS);
  return r === 0 ? 0 : signo * r;
}

/** Port de `nucleo.tarifa.usd`: centavos enteros → USD. */
export function usd(cent: number): number {
  return cent / 100;
}

/** Campos del `Recibo` del contrato (§5) que se comprueban. */
export interface ReciboComparable {
  minutos_reales: number;
  minutos_cobrados: number;
  cobrado_usd: number;
  tarjeta_sert_usd: number;
  ahorro_usd: number;
}

export interface ResultadoComparacion {
  ok: boolean;
  diferencias: string[];
}

/**
 * Recalcula el recibo con la tarifa local y lo compara con el del servidor. Los minutos
 * cobrados deben coincidir exactamente; los montos pueden diferir hasta `TOLERANCIA_USD`.
 * Solo es una comprobación: la app sigue mostrando los montos del servidor.
 */
export function compararConServidor(recibo: ReciboComparable, t: Tarifa = TARIFA): ResultadoComparacion {
  const m = recibo.minutos_reales;
  const diferencias: string[] = [];

  const minutos = minutosCobrables(m, t);
  if (minutos !== recibo.minutos_cobrados) {
    diferencias.push(`minutos_cobrados: servidor ${recibo.minutos_cobrados}, local ${minutos}`);
  }

  const montos: [keyof ReciboComparable, number][] = [
    ['cobrado_usd', costo(m, t)],
    ['tarjeta_sert_usd', costoTarjetaSert(m, t)],
    ['ahorro_usd', ahorro(m, t)],
  ];
  for (const [campo, local] of montos) {
    const servidor = recibo[campo];
    if (Math.abs(servidor - local) > TOLERANCIA_USD + EPS) {
      diferencias.push(`${campo}: servidor ${servidor.toFixed(2)}, local ${local.toFixed(2)}`);
    }
  }

  return { ok: diferencias.length === 0, diferencias };
}
