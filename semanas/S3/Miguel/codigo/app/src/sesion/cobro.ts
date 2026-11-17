import { TARIFA, costoMinutos, minutosCobrados } from '@/src/api/tarifa';
import type { Aviso, Tarifa } from '@/src/api/tipos';

export interface ResumenCobro {
  minutosReales: number;
  minutosCobrables: number;
  costo: number;
  /** Minutos que faltan para tiempo_maximo_min (negativo si ya se superó). */
  restanteMin: number;
  avisos: Aviso[];
}

/**
 * Lo que la pantalla activa muestra cada segundo, con las reglas de CONTRATO §5: fracciones de
 * 5 min con cobro mínimo, aviso del tope de tiempo y saldo_bajo = saldo − costo en curso.
 * `saldo` es opcional: sin billetera no se calcula el aviso de saldo.
 */
export function resumenCobro(minutosReales: number, saldo: number | null = null, tarifa: Tarifa = TARIFA): ResumenCobro {
  const minutosCobrables = minutosCobrados(minutosReales, tarifa);
  const costo = costoMinutos(minutosCobrables, tarifa);
  const restanteMin = tarifa.tiempo_maximo_min - minutosReales;
  const avisos: Aviso[] = [];
  if (restanteMin < 0) avisos.push('tiempo_maximo_superado');
  else if (restanteMin <= tarifa.aviso_tiempo_min) avisos.push('tiempo_maximo_cerca');
  if (saldo !== null) {
    const queda = saldo - costo;
    if (queda < -tarifa.saldo_negativo_max_usd + 1e-9) avisos.push('saldo_agotado');
    else if (queda < costoMinutos(tarifa.aviso_saldo_min, tarifa)) avisos.push('saldo_bajo');
  }
  return { minutosReales, minutosCobrables, costo, restanteMin, avisos };
}

/** Cronómetro h:mm:ss. */
export function cronometro(segundos: number): string {
  const s = Math.max(0, Math.floor(segundos));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  return `${h}:${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
}
