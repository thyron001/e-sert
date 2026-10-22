// SINCRONIZAR con comun/esquemas.ts
// Freddy todavía no publica proyecto/comun/esquemas.ts (ni en su rama freddy/s1), así que
// estos tipos se escribieron a mano desde docs/CONTRATO.md v0 (secciones 1, 2, 3, 4 y 5).
// Cuando exista esquemas.ts, este archivo se reemplaza por una copia de ese.

export const CONTRATO_VERSION = '1';

// --- Identificadores (sección 1) ---
export type PuestoId = string; // pa_<edgeId>_<n>
export type UsuarioId = string; // app_<uuid4> | sim_<vehId>
export type SesionId = string; // ses_<uuid4>
export type MovimientoId = string; // mov_<uuid4>
export type FechaISO = string; // ISO 8601 UTC

// --- Modos de movimiento (sección 2) ---
export type Modo = 'a_pie' | 'quieto' | 'vehiculo';
export type FuenteModo = 'rf' | 'umbral';

// --- Máquina de estados (sección 3) ---
export type EstadoSesion =
  | 'BUSCANDO'
  | 'GUIADO'
  | 'ESTACIONADO'
  | 'A_PIE'
  | 'REGRESANDO'
  | 'SALIENDO'
  | 'CERRADA';

// --- API REST (sección 4) ---
export interface Puesto {
  puesto_id: PuestoId;
  lat: number;
  lon: number;
  calle: string;
  capacidad: number;
  ocupados: number;
}

export interface ConsultaGuia {
  lat: number;
  lon: number;
  destino_lat: number;
  destino_lon: number;
}

export interface Guia {
  puesto_id: PuestoId;
  lat: number;
  lon: number;
  distancia_m: number;
}

export interface EventoUbicacion {
  usuario_id: UsuarioId;
  origen: 'sumo' | 'app';
  ts: FechaISO;
  t_sim?: number;
  lat: number;
  lon: number;
  velocidad_mps?: number;
  precision_m?: number;
}

export interface EventoModo {
  usuario_id: UsuarioId;
  ts: FechaISO;
  t_sim?: number;
  modo: Modo;
  confianza: number;
  fuente: FuenteModo;
}

export interface NuevaSesion {
  usuario_id: UsuarioId;
  placa: string;
  puesto_id: PuestoId;
}

export interface SesionCreada {
  sesion_id: SesionId;
  estado: 'ESTACIONADO';
  retenido: number;
}

export interface CierreSesion {
  ts: FechaISO;
  t_sim?: number;
  motivo: 'deteccion' | 'manual';
}

export interface SesionCerrada {
  sesion_id: SesionId;
  minutos_cobrados: number;
  debitado: number;
}

// El contrato solo dice "Sesión con su estado actual": estos campos son una propuesta.
export interface Sesion {
  sesion_id: SesionId;
  usuario_id: UsuarioId;
  placa: string;
  puesto_id: PuestoId;
  estado: EstadoSesion;
  inicio: FechaISO;
  fin: FechaISO | null;
  retenido: number;
  minutos_cobrados: number | null;
  debitado: number | null;
}

export type TipoMovimiento = 'recarga' | 'retencion' | 'debito' | 'liberacion';

// Tampoco está detallado en el contrato: propuesta mínima.
export interface Movimiento {
  movimiento_id: MovimientoId;
  tipo: TipoMovimiento;
  monto: number;
  ts: FechaISO;
  sesion_id?: SesionId;
  referencia_payphone?: string;
}

export interface Billetera {
  saldo: number;
  retenido: number;
  disponible: number;
  movimientos: Movimiento[];
}

export interface Recarga {
  monto: number;
  referencia_payphone?: string;
}

export interface RecargaHecha {
  movimiento_id: MovimientoId;
  saldo: number;
}

// --- Errores: {error: {codigo, mensaje}} ---
export interface CuerpoError {
  error: { codigo: string; mensaje: string };
}

export class ErrorApi extends Error {
  constructor(
    public readonly estado: number,
    public readonly codigo: string,
    mensaje: string,
  ) {
    super(mensaje);
    this.name = 'ErrorApi';
  }
}

// --- Tarifa (sección 5) ---
export interface Tarifa {
  valor_hora_usd: number;
  bloque_minimo_min: number;
  fraccion_min: number;
  cobro_minimo_min: number;
  saldo_negativo_max_usd: number;
  aviso_saldo_min: number;
  tiempo_maximo_min: number;
  recarga_minima_usd: number;
}

/** Interfaz común: la cumplen el cliente HTTP real (cliente.ts) y el mock (mock.ts). */
export interface ApiESert {
  listarPuestos(): Promise<Puesto[]>;
  /** Devuelve null si el backend responde 404 (no hay puesto libre). */
  pedirGuia(consulta: ConsultaGuia): Promise<Guia | null>;
  enviarUbicacion(evento: EventoUbicacion): Promise<void>;
  enviarModo(evento: EventoModo): Promise<void>;
  crearSesion(datos: NuevaSesion): Promise<SesionCreada>;
  cerrarSesion(sesionId: SesionId, datos: CierreSesion): Promise<SesionCerrada>;
  obtenerSesion(sesionId: SesionId): Promise<Sesion>;
  obtenerBilletera(usuarioId: UsuarioId): Promise<Billetera>;
  recargar(usuarioId: UsuarioId, datos: Recarga): Promise<RecargaHecha>;
}
