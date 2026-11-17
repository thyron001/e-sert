import { TARIFA } from '@/src/api/tarifa';
import type { Billetera, Tarifa } from '@/src/api/tipos';

// Avisos que la app programa al empezar una sesión (CONTEXTO, reglas de cobro 1, 4 y 5). Lógica
// pura: sin React ni expo-notifications, para probarla con Jest.

export type TipoAviso = 'saldo_bajo' | 'tiempo_maximo' | 'saldo_bajo_y_tiempo_maximo';

export interface AvisoProgramado {
  tipo: TipoAviso;
  cuando: Date;
  titulo: string;
  cuerpo: string;
}

/** Lo mínimo de la sesión que hace falta: el inicio (ISO) y su id. */
export interface SesionParaAvisos {
  sesion_id: string;
  inicio: string;
}

/** Dos avisos a menos de esto se combinan en uno. */
export const VENTANA_COMBINAR_MS = 60_000;

/**
 * Escala de tiempo de la demo: con EXPO_PUBLIC_ESCALA_TIEMPO=60, un minuto de la regla dura un
 * segundo. Sin la variable (o inválida), 1.
 */
export function escalaTiempo(valor: string | undefined = process.env.EXPO_PUBLIC_ESCALA_TIEMPO): number {
  const n = Number(valor);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

const minutos = (m: number) => `${Math.round(m)} min`;

/**
 * Avisos de una sesión que empieza en `sesion.inicio`:
 * - `saldo_bajo`: el disponible cubre `disponible / (valor_hora_usd / 60)` minutos; se avisa
 *   `aviso_saldo_min` antes de que se acaben;
 * - `tiempo_maximo`: `aviso_tiempo_min` antes de `tiempo_maximo_min` (ese parámetro ya existe en
 *   tarifa.json; es el `aviso_tope_antes_min` que pedía el prompt).
 * Dos avisos a menos de 1 min se combinan; los que caen en el pasado se disparan ya (`ahora`).
 * `escala` divide los minutos de la regla (modo demo).
 */
export function calcularAvisos(
  sesion: SesionParaAvisos,
  billetera: Pick<Billetera, 'disponible'>,
  tarifa: Tarifa = TARIFA,
  ahora: Date = new Date(),
  escala = 1,
): AvisoProgramado[] {
  const inicio = Date.parse(sesion.inicio);
  const enMs = (min: number) => new Date(inicio + (min * 60_000) / escala);

  const minutosCubiertos = Math.max(0, billetera.disponible) / (tarifa.valor_hora_usd / 60);
  const minSaldo = minutosCubiertos - tarifa.aviso_saldo_min;
  const minTope = tarifa.tiempo_maximo_min - tarifa.aviso_tiempo_min;

  const avisos: AvisoProgramado[] = [
    {
      tipo: 'saldo_bajo',
      cuando: enMs(minSaldo),
      titulo: 'Saldo bajo',
      cuerpo: `Tu saldo alcanza para unos ${minutos(Math.min(tarifa.aviso_saldo_min, minutosCubiertos))} más. Recarga para no quedarte sin saldo.`,
    },
    {
      tipo: 'tiempo_maximo',
      cuando: enMs(minTope),
      titulo: 'Tope SERT cerca',
      cuerpo: `En ${minutos(tarifa.aviso_tiempo_min)} llegas al máximo de ${minutos(tarifa.tiempo_maximo_min)} en el puesto.`,
    },
  ];

  const [a, b] = avisos;
  const ordenados =
    // La ventana es de 1 min de la regla: con la escala de demo también se acorta.
    Math.abs(a.cuando.getTime() - b.cuando.getTime()) < VENTANA_COMBINAR_MS / escala
      ? [
          {
            tipo: 'saldo_bajo_y_tiempo_maximo' as const,
            cuando: new Date(Math.min(a.cuando.getTime(), b.cuando.getTime())),
            titulo: 'Saldo bajo y tope SERT cerca',
            cuerpo: `${a.cuerpo} ${b.cuerpo}`,
          },
        ]
      : [...avisos].sort((x, y) => x.cuando.getTime() - y.cuando.getTime());

  // En el pasado: de inmediato.
  return ordenados.map((x) => (x.cuando.getTime() < ahora.getTime() ? { ...x, cuando: new Date(ahora) } : x));
}

export type MotivoBloqueo = 'saldo_negativo' | 'disponible_insuficiente';

export interface EstadoBloqueo {
  bloqueado: boolean;
  motivo: MotivoBloqueo | null;
  /** Deuda en USD (positiva) si el saldo es negativo; 0 si no. */
  deuda: number;
  /** Recarga que se sugiere: al menos la mínima y suficiente para cubrir la deuda y el bloque. */
  recargaSugerida: number;
}

/**
 * Regla 5: con saldo negativo no se abren sesiones hasta recargar. Regla 1: si el disponible no
 * alcanza para el bloque mínimo (la retención), hay que recargar al menos `recarga_minima_usd`.
 */
export function estadoBloqueo(
  billetera: Pick<Billetera, 'saldo' | 'disponible'> & { bloqueada?: boolean },
  tarifa: Tarifa = TARIFA,
): EstadoBloqueo {
  const bloque = Math.round((tarifa.bloque_minimo_min * tarifa.valor_hora_usd * 100) / 60) / 100;
  if (billetera.saldo < 0 || billetera.bloqueada) {
    const deuda = Math.round(Math.max(0, -billetera.saldo) * 100) / 100;
    return {
      bloqueado: true,
      motivo: 'saldo_negativo',
      deuda,
      recargaSugerida: Math.max(tarifa.recarga_minima_usd, Math.ceil((deuda + bloque) * 100) / 100),
    };
  }
  if (billetera.disponible < bloque) {
    return { bloqueado: true, motivo: 'disponible_insuficiente', deuda: 0, recargaSugerida: tarifa.recarga_minima_usd };
  }
  return { bloqueado: false, motivo: null, deuda: 0, recargaSugerida: 0 };
}
