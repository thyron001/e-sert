// Formato de las grabaciones caseras (CONTRATO §7 v0 / §8 de la propuesta v1 de Freddy).
// Sin dependencias nativas: se prueba en la computadora con `npm run prueba:grabador`.

import type { Modo } from '@/src/api/tipos';

// SINCRONIZAR con COLUMNAS_TRAZA de comun/esquemas.ts: estas 7 van primero y en este orden.
export const COLUMNAS_CONTRATO = [
  'usuario_id',
  't',
  'lat',
  'lon',
  'precision_m',
  'velocidad_mps',
  'modo_real',
] as const;

// Columnas extra, siempre después de las 7 del contrato.
export const COLUMNAS_EXTRA = ['escenario', 'telefono', 'persona'] as const;
export const COLUMNAS_GPS = [...COLUMNAS_CONTRATO, ...COLUMNAS_EXTRA];
export const COLUMNAS_ACEL = ['t', 'ax', 'ay', 'az'] as const;

export const PERSONAS = ['Tyrone', 'Freddy', 'Pablo', 'Miguel'] as const;
export type Persona = (typeof PERSONAS)[number];
export type Telefono = 'ios' | 'android';

/** Etiqueta que elige quien graba. `vehiculo_lento` es auto en tráfico lento a velocidad de peatón. */
export const ETIQUETAS = ['a_pie', 'quieto', 'vehiculo', 'vehiculo_lento'] as const;
export type Etiqueta = (typeof ETIQUETAS)[number];

export const esEtiquetaVehiculo = (e: Etiqueta) => e === 'vehiculo' || e === 'vehiculo_lento';

/** Cómo se escribe cada etiqueta en el CSV: `vehiculo_lento` → modo vehiculo + escenario trafico_lento. */
export function etiquetaAContrato(e: Etiqueta): { modo_real: Modo; escenario: string } {
  if (e === 'vehiculo_lento') return { modo_real: 'vehiculo', escenario: 'trafico_lento' };
  return { modo_real: e, escenario: '' };
}

export interface MuestraGPS {
  t: number; // segundos Unix UTC
  lat: number;
  lon: number;
  precision_m: number | null;
  velocidad_mps: number | null;
  etiqueta: Etiqueta;
}

export interface MuestraAcel {
  t: number;
  ax: number;
  ay: number;
  az: number;
}

export interface ContextoGrabacion {
  usuario_id: string; // casa_<persona>_<n>
  persona: Persona;
  telefono: Telefono;
}

/** El GPS da `speed` nulo o −1 cuando no la conoce: entonces el campo queda vacío. */
export function limpiarVelocidad(speed: number | null | undefined): number | null {
  return speed == null || !Number.isFinite(speed) || speed < 0 ? null : speed;
}

export function limpiarPrecision(accuracy: number | null | undefined): number | null {
  return accuracy == null || !Number.isFinite(accuracy) || accuracy < 0 ? null : accuracy;
}

const num = (v: number | null, decimales: number) => (v == null ? '' : v.toFixed(decimales));

export const encabezadoGPS = () => COLUMNAS_GPS.join(',') + '\n';
export const encabezadoAcel = () => COLUMNAS_ACEL.join(',') + '\n';

export function filaGPS(m: MuestraGPS, ctx: ContextoGrabacion): string {
  const { modo_real, escenario } = etiquetaAContrato(m.etiqueta);
  return [
    ctx.usuario_id,
    m.t.toFixed(3),
    m.lat.toFixed(7),
    m.lon.toFixed(7),
    num(m.precision_m, 1),
    num(m.velocidad_mps, 2),
    modo_real,
    escenario,
    ctx.telefono,
    ctx.persona,
  ].join(',');
}

export const filaAcel = (m: MuestraAcel) =>
  [m.t.toFixed(3), m.ax.toFixed(4), m.ay.toFixed(4), m.az.toFixed(4)].join(',');

/** `<fecha>_<persona>_<telefono>`, con la fecha local sin dos puntos (válido en Windows). */
export function nombreBase(fecha: Date, persona: Persona, telefono: Telefono): string {
  const d2 = (n: number) => String(n).padStart(2, '0');
  const f =
    `${fecha.getFullYear()}-${d2(fecha.getMonth() + 1)}-${d2(fecha.getDate())}` +
    `T${d2(fecha.getHours())}-${d2(fecha.getMinutes())}-${d2(fecha.getSeconds())}`;
  return `${f}_${persona.toLowerCase()}_${telefono}`;
}

export const usuarioCasa = (persona: Persona, n: number) => `casa_${persona.toLowerCase()}_${n}`;
