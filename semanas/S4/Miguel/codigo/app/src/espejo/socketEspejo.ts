import { AppState, type AppStateStatus } from 'react-native';

import type { FinEspejo, MensajeEspejo } from '@/src/api/tipos';
import { esFinEspejo, esMensajeEspejo } from './validar';

// WebSocket del modo espejo (CONTRATO §7) con reconexión, vigilancia de silencio y AppState.

export type EstadoConexion = 'en_vivo' | 'reconectando' | 'sin_conexion';

export interface ManejadoresEspejo {
  /** Mensaje válido; `recibidoEn` es Date.now() al llegar (para la latencia). */
  onMensaje(m: MensajeEspejo, recibidoEn: number): void;
  onFin(m: FinEspejo): void;
  onEstado(estado: EstadoConexion, intento: number): void;
}

export const ESPERAS_BASE_MS = 1_000;
export const ESPERA_MAXIMA_MS = 30_000;
export const JITTER = 0.2;
export const SILENCIO_MAXIMO_MS = 5_000;
/** A partir de este intento la espera ya está en el tope: el indicador pasa a "sin conexión". */
export const INTENTOS_HASTA_SIN_CONEXION = 6;

/** Lo mínimo de un WebSocket que se usa (permite inyectar uno falso en los tests). */
export interface SocketMinimo {
  onopen: ((ev?: unknown) => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: ((ev?: unknown) => void) | null;
  onerror: ((ev?: unknown) => void) | null;
  close(): void;
}

export interface Dependencias {
  crearSocket(url: string): SocketMinimo;
  /** Suscripción a primer plano / segundo plano; devuelve la función para quitarla. */
  escucharAppState(fn: (estado: AppStateStatus) => void): () => void;
  /** Número en [0, 1) para el jitter; en los tests, 0.5 lo anula. */
  aleatorio(): number;
  ahora(): number;
}

const DEPENDENCIAS_REALES: Dependencias = {
  crearSocket: (url) => new WebSocket(url) as unknown as SocketMinimo,
  escucharAppState: (fn) => {
    const sub = AppState.addEventListener('change', fn);
    return () => sub.remove();
  },
  aleatorio: Math.random,
  ahora: Date.now,
};

/** Espera antes del intento `intento` (1, 2, 3…): 1, 2, 4, 8, 16, 30, 30… s, con jitter ±20 %. */
export function esperaReconexion(intento: number, aleatorio: () => number = Math.random): number {
  const base = Math.min(ESPERAS_BASE_MS * 2 ** (intento - 1), ESPERA_MAXIMA_MS);
  return Math.round(base * (1 + JITTER * (2 * aleatorio() - 1)));
}

export class SocketEspejo {
  private socket: SocketMinimo | null = null;
  private manejadores: ManejadoresEspejo | null = null;
  private url = '';
  private intento = 0;
  private terminado = false; // cerrar() manual o espejo_fin: no se reconecta
  private enSegundoPlano = false;
  private enVivo = false;
  private temporizadorReconexion: ReturnType<typeof setTimeout> | null = null;
  private temporizadorSilencio: ReturnType<typeof setTimeout> | null = null;
  private quitarAppState: (() => void) | null = null;
  private readonly dep: Dependencias;

  constructor(private readonly urlDe: (vehId: string) => string, dependencias: Partial<Dependencias> = {}) {
    this.dep = { ...DEPENDENCIAS_REALES, ...dependencias };
  }

  conectar(vehId: string, manejadores: ManejadoresEspejo): void {
    this.cerrar();
    this.url = this.urlDe(vehId);
    this.manejadores = manejadores;
    this.terminado = false;
    this.enSegundoPlano = false;
    this.enVivo = false;
    this.intento = 0;
    this.quitarAppState = this.dep.escucharAppState((e) => this.cambioAppState(e));
    this.abrir();
  }

  cerrar(): void {
    this.terminado = true;
    this.limpiarTemporizadores();
    this.soltarSocket();
    this.quitarAppState?.();
    this.quitarAppState = null;
  }

  private abrir(): void {
    if (this.terminado || this.enSegundoPlano) return;
    this.soltarSocket();
    const s = this.dep.crearSocket(this.url);
    this.socket = s;
    s.onopen = () => this.vigilar();
    s.onmessage = (ev) => this.recibir(ev.data);
    s.onclose = () => this.perdida();
    s.onerror = () => this.perdida();
  }

  private recibir(datos: unknown): void {
    const recibidoEn = this.dep.ahora();
    let m: unknown;
    try {
      m = typeof datos === 'string' ? JSON.parse(datos) : datos;
    } catch {
      console.warn('[espejo] mensaje que no es JSON, se descarta');
      return;
    }
    if (esFinEspejo(m)) {
      this.terminado = true;
      this.limpiarTemporizadores();
      this.soltarSocket();
      this.quitarAppState?.();
      this.quitarAppState = null;
      this.manejadores?.onFin(m);
      return;
    }
    if (!esMensajeEspejo(m)) {
      console.warn('[espejo] mensaje inválido, se descarta', m);
      return;
    }
    if (this.intento !== 0 || !this.enVivo) {
      this.intento = 0; // el primer mensaje reinicia la cuenta de reconexión
      this.enVivo = true;
      this.manejadores?.onEstado('en_vivo', 0);
    }
    this.vigilar();
    this.manejadores?.onMensaje(m, recibidoEn);
  }

  /** Si pasan SILENCIO_MAXIMO_MS sin mensajes (se esperan a 1 Hz), se cierra y se reconecta. */
  private vigilar(): void {
    if (this.temporizadorSilencio) clearTimeout(this.temporizadorSilencio);
    this.temporizadorSilencio = setTimeout(() => this.perdida(), SILENCIO_MAXIMO_MS);
  }

  private perdida(): void {
    if (this.terminado || this.enSegundoPlano) return;
    this.soltarSocket();
    if (this.temporizadorSilencio) clearTimeout(this.temporizadorSilencio);
    this.temporizadorSilencio = null;
    if (this.temporizadorReconexion) return; // ya hay un reintento en curso
    this.enVivo = false;
    this.intento += 1;
    const estado = this.intento >= INTENTOS_HASTA_SIN_CONEXION ? 'sin_conexion' : 'reconectando';
    this.manejadores?.onEstado(estado, this.intento);
    this.temporizadorReconexion = setTimeout(() => {
      this.temporizadorReconexion = null;
      this.abrir();
    }, esperaReconexion(this.intento, this.dep.aleatorio));
  }

  private cambioAppState(estado: AppStateStatus): void {
    if (this.terminado) return;
    if (estado === 'background') {
      this.enSegundoPlano = true;
      this.enVivo = false;
      this.limpiarTemporizadores();
      this.soltarSocket();
      this.manejadores?.onEstado('sin_conexion', this.intento);
    } else if (estado === 'active' && this.enSegundoPlano) {
      this.enSegundoPlano = false;
      this.intento = 0;
      this.manejadores?.onEstado('reconectando', 0);
      this.abrir(); // al volver a primer plano, enseguida
    }
  }

  private soltarSocket(): void {
    const s = this.socket;
    this.socket = null;
    if (!s) return;
    // Se quitan los manejadores antes de cerrar para que el onclose no dispare otra reconexión.
    s.onopen = s.onmessage = s.onclose = s.onerror = null;
    try {
      s.close();
    } catch {
      // ya estaba cerrado
    }
  }

  private limpiarTemporizadores(): void {
    if (this.temporizadorReconexion) clearTimeout(this.temporizadorReconexion);
    if (this.temporizadorSilencio) clearTimeout(this.temporizadorSilencio);
    this.temporizadorReconexion = null;
    this.temporizadorSilencio = null;
  }
}
