import { useEffect, useRef } from 'react';
import { AppState } from 'react-native';

import { getSesion } from '@/src/api/cliente';
import { TARIFA } from '@/src/api/tarifa';
import { ErrorApi, type ApiESert, FinEspejo, MensajeEspejo, MotivoCierre, Sesion, SesionCerrada } from '@/src/api/tipos';
import type { Conexion } from '@/src/espejo/useEspejo';

// Seguimiento de la sesión hasta su cierre. Todo es simulado: el cierre automático lo decide la
// simulación (SALIENDO → CERRADA) y llega por WS /ws/espejo/{veh_id} con `recibo` (CONTRATO §7);
// para las sesiones propias de la app, por GET /sesiones/{id}. El cierre se procesa UNA sola vez,
// llegue por donde llegue.

export const SONDEO_MS = 10_000;

/** Lo que necesita la pantalla del recibo. Los montos son siempre los del servidor. */
export interface DatosRecibo {
  origen: 'propia' | 'espejo';
  /** null = el servidor no lo dice (GET /sesiones no trae motivo; el recibo del espejo tampoco). */
  motivo: MotivoCierre | null;
  sesion_id: string | null;
  veh_id: string | null;
  usuario_id: string | null;
  placa: string | null;
  puesto_id: string | null;
  inicio: string | null; // ISO: llegada
  fin: string | null; // ISO: salida
  minutos_reales: number;
  minutos_cobrados: number;
  cobrado_usd: number;
  /** Del recibo del espejo; en la sesión propia el backend no lo envía (lo calcula tarifa.ts). */
  tarjeta_sert_usd: number | null;
  ahorro_usd: number | null;
  saldo: number | null;
}

/**
 * El contrato no envía el motivo en GET /sesiones ni en el recibo del espejo. Se deduce:
 * si llegó al tiempo máximo, timeout_sin_senal; si se vio SALIENDO antes, deteccion.
 */
export function motivoDeducido(
  minutosReales: number,
  ultimoEstado: string | null,
  origen: DatosRecibo['origen'] = 'propia',
): MotivoCierre | null {
  if (minutosReales >= TARIFA.tiempo_maximo_min) return 'timeout_sin_senal';
  // Un auto simulado no tiene "Ya me voy": su cierre siempre es de la simulación. A ritmo
  // acelerado el espejo puede saltar de A_PIE/REGRESANDO a CERRADA sin mostrar SALIENDO.
  if (ultimoEstado === 'SALIENDO' || origen === 'espejo') return 'deteccion';
  return null;
}

export type Evento = { tipo: 'cierre'; datos: DatosRecibo } | { tipo: 'salio' } | null;

/**
 * Detector puro (sin React): recibe mensajes del espejo, respuestas de GET /sesiones o el cierre
 * manual, y devuelve el evento a procesar. Tras el primer cierre, todo lo demás se ignora.
 */
export class DetectorCierre {
  private procesado = false;
  private ultimoEstado: string | null = null;
  private llegada: string | null = null;
  private sesionId: string | null = null;
  private puestoId: string | null = null;
  private saldo: number | null = null;

  constructor(private readonly base: { origen: DatosRecibo['origen']; veh_id?: string | null; usuario_id?: string | null; placa?: string | null }) {}

  get cerrado(): boolean {
    return this.procesado;
  }

  get sesionConocida(): string | null {
    return this.sesionId;
  }

  conocerSesion(sesionId: string, extra: { puesto_id?: string | null; inicio?: string | null } = {}): void {
    this.sesionId = sesionId;
    this.puestoId = extra.puesto_id ?? this.puestoId;
    this.llegada = extra.inicio ?? this.llegada;
  }

  private emitir(datos: Omit<DatosRecibo, 'origen' | 'veh_id' | 'usuario_id' | 'placa'>): Evento {
    if (this.procesado) return null;
    this.procesado = true;
    return {
      tipo: 'cierre',
      datos: {
        origen: this.base.origen,
        veh_id: this.base.veh_id ?? null,
        usuario_id: this.base.usuario_id ?? null,
        placa: this.base.placa ?? null,
        ...datos,
      },
    };
  }

  /** Mensaje `espejo`: el cierre es estado CERRADA con `recibo` (llega en un solo mensaje). */
  mensaje(m: MensajeEspejo): Evento {
    if (this.procesado) return null;
    if (m.sesion?.sesion_id) this.sesionId = m.sesion.sesion_id;
    if (m.puesto?.puesto_id) this.puestoId = m.puesto.puesto_id;
    if (m.billetera) this.saldo = m.billetera.saldo;
    if (m.estado === 'ESTACIONADO' && !this.llegada) this.llegada = m.ts;
    if (m.estado === 'CERRADA' && m.recibo) {
      const r = m.recibo;
      return this.emitir({
        motivo: motivoDeducido(r.minutos_reales, this.ultimoEstado, this.base.origen),
        sesion_id: this.sesionId,
        puesto_id: this.puestoId,
        inicio: this.llegada,
        fin: m.ts,
        minutos_reales: r.minutos_reales,
        minutos_cobrados: r.minutos_cobrados,
        cobrado_usd: r.cobrado_usd,
        tarjeta_sert_usd: r.tarjeta_sert_usd,
        ahorro_usd: r.ahorro_usd,
        saldo: m.billetera?.saldo ?? this.saldo,
      });
    }
    if (m.estado && m.estado !== 'CERRADA') this.ultimoEstado = m.estado;
    return null;
  }

  /** espejo_fin: si no hubo recibo, el auto salió de la simulación sin cierre visible. */
  fin(_f: FinEspejo): Evento {
    return this.procesado ? null : { tipo: 'salio' };
  }

  /** GET /sesiones/{id} (respaldo o sesión propia): CERRADA trae minutos y débito. */
  sesion(s: Sesion, saldo: number | null = null): Evento {
    if (this.procesado || s.estado !== 'CERRADA') return null;
    const minutos = s.minutos_reales ?? 0;
    return this.emitir({
      motivo: motivoDeducido(minutos, this.ultimoEstado, this.base.origen),
      sesion_id: s.sesion_id,
      puesto_id: s.puesto_id,
      inicio: s.inicio,
      fin: s.fin ?? null,
      minutos_reales: minutos,
      minutos_cobrados: s.minutos_cobrados ?? 0,
      cobrado_usd: s.debitado ?? 0,
      tarjeta_sert_usd: null,
      ahorro_usd: null,
      saldo: saldo ?? this.saldo,
    });
  }

  /** Respuesta de POST /sesiones/{id}/cerrar (cierre manual con "Ya me voy"). */
  cierreManual(c: SesionCerrada, extra: { puesto_id?: string | null; inicio?: string | null } = {}): Evento {
    return this.emitir({
      motivo: 'manual',
      sesion_id: c.sesion_id,
      puesto_id: extra.puesto_id ?? this.puestoId,
      inicio: extra.inicio ?? this.llegada,
      fin: new Date().toISOString(),
      minutos_reales: c.minutos_reales,
      minutos_cobrados: c.minutos_cobrados,
      cobrado_usd: c.debitado,
      tarjeta_sert_usd: null,
      ahorro_usd: null,
      saldo: c.saldo,
    });
  }
}

/** Consulta GET /sesiones/{id} cada SONDEO_MS mientras `activo`, y enseguida al volver a primer plano. */
function useSondeo(
  sesionId: string | null,
  activo: boolean,
  api: ApiESert,
  alResponder: (s: Sesion) => void,
  alNoExistir?: () => void,
) {
  const alResponderRef = useRef(alResponder);
  alResponderRef.current = alResponder;
  const alNoExistirRef = useRef(alNoExistir);
  alNoExistirRef.current = alNoExistir;
  useEffect(() => {
    if (!sesionId || !activo) return;
    let vivo = true;
    const consultar = () =>
      getSesion(sesionId, api)
        .then((s) => vivo && alResponderRef.current(s))
        .catch((e) => {
          // 404: el servidor no conoce la sesión (p. ej. una sesión guardada de otro backend).
          // Sin red u otro error: se reintenta en el siguiente sondeo.
          if (vivo && e instanceof ErrorApi && e.estado === 404) alNoExistirRef.current?.();
        });
    consultar();
    const id = setInterval(consultar, SONDEO_MS);
    const sub = AppState.addEventListener('change', (e) => e === 'active' && consultar());
    return () => {
      vivo = false;
      clearInterval(id);
      sub.remove();
    };
  }, [sesionId, activo, api]);
}

/**
 * Sesión propia (buscar → activa): no hay WS para ella, así que se sondea GET /sesiones/{id}.
 * Detecta un cierre hecho fuera de la app (la simulación o un `curl .../cerrar`).
 */
export function useSeguimientoPropio(
  detector: DetectorCierre,
  sesionId: string | null,
  api: ApiESert,
  alCerrar: (d: DatosRecibo) => void,
  alNoExistir?: () => void,
) {
  useSondeo(
    sesionId,
    !detector.cerrado,
    api,
    (s) => {
      const ev = detector.sesion(s);
      if (ev?.tipo === 'cierre') alCerrar(ev.datos);
    },
    alNoExistir,
  );
}

/**
 * Modo espejo: los mensajes vienen del SocketEspejo de S2-3 (useEspejo, con su reconexión).
 * Respaldo: si el WS no está en vivo y se conoce el sesion_id, GET /sesiones/{id} cada 10 s.
 */
export function useSeguimientoEspejo(
  detector: DetectorCierre,
  entrada: { mensaje: MensajeEspejo | null; mensajeCierre?: MensajeEspejo | null; fin: FinEspejo | null; conexion: Conexion },
  api: ApiESert,
  alCerrar: (d: DatosRecibo) => void,
  alSalir: () => void,
) {
  const { mensaje, mensajeCierre, fin, conexion } = entrada;
  useEffect(() => {
    if (!mensaje) return;
    const ev = detector.mensaje(mensaje);
    if (ev?.tipo === 'cierre') alCerrar(ev.datos);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mensaje]);
  // Respaldo: el mensaje con recibo retenido por useEspejo (por si no llegó a verse como `mensaje`).
  useEffect(() => {
    if (!mensajeCierre) return;
    const ev = detector.mensaje(mensajeCierre);
    if (ev?.tipo === 'cierre') alCerrar(ev.datos);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mensajeCierre]);
  useEffect(() => {
    if (!fin) return;
    const ev = detector.fin(fin);
    if (ev?.tipo === 'salio') alSalir();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fin]);
  const caido = conexion.estado === 'reconectando' || conexion.estado === 'sin_conexion';
  useSondeo(detector.sesionConocida, caido && !detector.cerrado, api, (s) => {
    const ev = detector.sesion(s);
    if (ev?.tipo === 'cierre') alCerrar(ev.datos);
  });
}
