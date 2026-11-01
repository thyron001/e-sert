import type { Aviso, EstadoSesion } from '@/src/api/tipos';

/** t_sim en mm:ss (los minutos pueden pasar de 59). */
export function mmss(segundos: number): string {
  const s = Math.max(0, Math.round(segundos));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

export const usd = (v: number) => `$${v.toFixed(2)}`;

export const NOMBRE_ESTADO: Record<EstadoSesion, string> = {
  BUSCANDO: 'Buscando',
  GUIADO: 'Guiado',
  ESTACIONADO: 'Estacionado',
  A_PIE: 'A pie',
  REGRESANDO: 'Regresando',
  SALIENDO: 'Saliendo',
  CERRADA: 'Cerrada',
};

export const TEXTO_AVISO: Record<Aviso, string> = {
  saldo_bajo: 'Saldo bajo: alcanza para menos de 10 minutos',
  saldo_agotado: 'Saldo agotado: sal o recarga',
  tiempo_maximo_cerca: 'Te acercas al tiempo máximo SERT',
  tiempo_maximo_superado: 'Superaste el tiempo máximo SERT',
  sesiones_bloqueadas: 'Saldo negativo: recarga para nuevas sesiones',
};

/** Rumbo en grados (0 = norte, sentido horario) de a hacia b. */
export function rumbo(a: [number, number], b: [number, number]): number {
  const rad = Math.PI / 180;
  const y = Math.sin((b[1] - a[1]) * rad) * Math.cos(b[0] * rad);
  const x =
    Math.cos(a[0] * rad) * Math.sin(b[0] * rad) -
    Math.sin(a[0] * rad) * Math.cos(b[0] * rad) * Math.cos((b[1] - a[1]) * rad);
  return (Math.atan2(y, x) / rad + 360) % 360;
}
