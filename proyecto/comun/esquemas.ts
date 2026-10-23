// Esquemas del contrato v1 de e-sert (TypeScript, escritos a mano).
//
// SINCRONIZAR con comun/esquemas.py: mismos nombres de interfaz y de campo, mismos valores de
// los enums. El test comun/tests/test_esquemas.py compara ambos archivos y falla si se
// desalinean. Si cambias algo aquí, cámbialo también en esquemas.py (y en CONTRATO.propuesto.md).
//
// Convenciones: un campo `x?: T | null` es opcional/nullable en Python (default None).
// No se usan objetos en línea: cada objeto anidado tiene su propia interfaz.

export const CONTRATO_VERSION = '1';

// --- Identificadores y tipos básicos (§1) ---
export type PuestoId = string; // pa_<edgeId>_<n>
export type VehiculoId = string; // sim_<vehId>
export type PeatonId = string; // ped_<vehId>
export type UsuarioId = string; // sim_<vehId> | app_<uuid4>
export type SesionId = string; // ses_<uuid4>
export type MovimientoId = string; // mov_<uuid4>
export type Placa = string; // ABC-1234 o SIM-0042
export type FechaISO = string; // ISO 8601 con zona, emitida en UTC con Z
export type Coordenada = [number, number]; // [lat, lon]

// --- Enums (§2, §3, §5, §7) ---
export type Modo = 'a_pie' | 'quieto' | 'vehiculo';
export type FuenteModo = 'rf' | 'umbral';
export type EstadoSesion =
  | 'BUSCANDO'
  | 'GUIADO'
  | 'ESTACIONADO'
  | 'A_PIE'
  | 'REGRESANDO'
  | 'SALIENDO'
  | 'CERRADA';
export type OrigenUbicacion = 'sumo' | 'app';
export type MotivoCierre = 'deteccion' | 'manual';
export type TipoMovimiento = 'recarga' | 'retencion' | 'debito' | 'liberacion';
export type Aviso =
  | 'saldo_bajo'
  | 'saldo_agotado'
  | 'tiempo_maximo_cerca'
  | 'tiempo_maximo_superado'
  | 'sesiones_bloqueadas';
export type MotivoFinEspejo = 'salio_simulacion' | 'fin_simulacion' | 'no_existe';
export type CodigoError =
  | 'VALIDACION'
  | 'CONTRATO_INCOMPATIBLE'
  | 'TOKEN_SIM_INVALIDO'
  | 'SALDO_INSUFICIENTE'
  | 'SESIONES_BLOQUEADAS'
  | 'PUESTO_NO_EXISTE'
  | 'SESION_NO_EXISTE'
  | 'VEHICULO_NO_EXISTE'
  | 'SIN_PUESTOS_LIBRES'
  | 'PUESTO_LLENO'
  | 'SESION_ACTIVA'
  | 'SESION_YA_CERRADA'
  | 'TRANSICION_INVALIDA'
  | 'RECARGA_MINIMA'
  | 'ERROR_INTERNO';

// --- IA (§2) ---
export interface PuntoGPS {
  t: number;
  lat: number;
  lon: number;
  precision_m?: number | null;
}

export interface ResultadoModo {
  modo: Modo;
  confianza: number; // 0..1
  fuente: FuenteModo;
}

// --- API REST (§4) ---
export interface DetalleError {
  codigo: CodigoError;
  mensaje: string;
  detalle?: Record<string, unknown> | null;
}

export interface CuerpoError {
  error: DetalleError;
}

export interface Aceptado {
  aceptado: true;
}

export interface Salud {
  ok: boolean;
  contrato: number;
  t_sim?: number | null;
}

export interface Tarifa {
  valor_hora_usd: number;
  bloque_minimo_min: number;
  fraccion_min: number;
  cobro_minimo_min: number;
  saldo_negativo_max_usd: number;
  aviso_saldo_min: number;
  tiempo_maximo_min: number;
  aviso_tiempo_min: number;
  recarga_minima_usd: number;
  tarjeta_bloque_min: number;
}

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
  origen: OrigenUbicacion;
  ts: FechaISO;
  t_sim?: number | null;
  lat: number;
  lon: number;
  velocidad_mps?: number | null;
  precision_m?: number | null;
}

export interface EventoModo {
  usuario_id: UsuarioId;
  ts: FechaISO;
  t_sim?: number | null;
  modo: Modo;
  confianza: number;
  fuente: FuenteModo;
}

export interface NuevaSesion {
  usuario_id: UsuarioId;
  placa: Placa;
  puesto_id: PuestoId;
  ts?: FechaISO | null;
  t_sim?: number | null;
}

export interface SesionCreada {
  sesion_id: SesionId;
  estado: 'ESTACIONADO';
  retenido: number;
}

export interface TransicionSesion {
  estado: EstadoSesion;
  ts: FechaISO;
  t_sim?: number | null;
}

export interface EstadoActualSesion {
  sesion_id: SesionId;
  estado: EstadoSesion;
}

export interface CierreSesion {
  ts: FechaISO;
  t_sim?: number | null;
  motivo: MotivoCierre;
}

export interface SesionCerrada {
  sesion_id: SesionId;
  minutos_reales: number;
  minutos_cobrados: number;
  debitado: number;
  saldo: number;
}

export interface Sesion {
  sesion_id: SesionId;
  usuario_id: UsuarioId;
  placa: Placa;
  puesto_id: PuestoId;
  estado: EstadoSesion;
  inicio: FechaISO;
  fin?: FechaISO | null;
  t_sim_inicio?: number | null;
  t_sim_fin?: number | null;
  retenido: number;
  minutos_reales?: number | null;
  minutos_cobrados?: number | null;
  debitado?: number | null;
}

export interface Movimiento {
  movimiento_id: MovimientoId;
  tipo: TipoMovimiento;
  monto: number; // siempre positivo
  ts: FechaISO;
  sesion_id?: SesionId | null;
  referencia_payphone?: string | null;
}

export interface Billetera {
  saldo: number;
  retenido: number;
  disponible: number;
  bloqueada: boolean;
  movimientos: Movimiento[];
}

export interface Recarga {
  monto: number;
  referencia_payphone?: string | null;
}

export interface RecargaHecha {
  movimiento_id: MovimientoId;
  saldo: number;
}

export interface CandidatoEspejo {
  id: VehiculoId;
  destino_nombre: string;
  estado?: EstadoSesion | null;
  t_sim: number;
}

// --- Piezas compartidas por /sim/paso y los mensajes WS (§4.4, §6, §7) ---
export interface Destino {
  nombre: string;
  lat: number;
  lon: number;
}

export interface VehiculoSnapshot {
  id: VehiculoId;
  lat: number;
  lon: number;
  estado?: EstadoSesion | null;
  con_app: boolean;
}

export interface VehiculoSim extends VehiculoSnapshot {
  modo?: Modo | null;
  destino?: Destino | null;
  puesto_id?: PuestoId | null;
  ruta?: Coordenada[];
}

export interface Peaton {
  id: PeatonId;
  lat: number;
  lon: number;
}

export interface OcupacionPuesto {
  puesto_id: PuestoId;
  ocupados: number;
  capacidad: number;
}

export interface DatosVerdad {
  puestos: OcupacionPuesto[];
  estacionados?: VehiculoId[];
  falsas_liberaciones?: SesionId[];
}

export interface PasoSimulacion {
  t_sim: number;
  ts: FechaISO;
  vehiculos: VehiculoSim[];
  peatones: Peaton[];
  verdad: DatosVerdad;
}

export interface PuestoEspejo {
  puesto_id: PuestoId;
  lat: number;
  lon: number;
  distancia_m: number;
}

export interface SesionEspejo {
  sesion_id: SesionId;
  minutos: number;
  costo_usd: number;
  retenido_usd: number;
}

export interface BilleteraEspejo {
  saldo: number;
  disponible: number;
}

export interface Recibo {
  minutos_reales: number;
  minutos_cobrados: number;
  cobrado_usd: number;
  tarjeta_sert_usd: number;
  ahorro_usd: number;
}

// --- Mensajes WebSocket (§6, §7): unión discriminada por `tipo` ---
export interface MensajeSnapshot {
  tipo: 'snapshot';
  t_sim: number;
  ts: FechaISO;
  vehiculos: VehiculoSnapshot[];
  peatones: Peaton[];
  puestos: OcupacionPuesto[];
  espejos?: VehiculoId[];
}

export interface MensajeKpi {
  tipo: 'kpi';
  t_sim: number;
  ts: FechaISO;
  valores: Record<string, number>;
}

export interface MensajeVerdad {
  tipo: 'verdad';
  t_sim: number;
  ts: FechaISO;
  puestos: OcupacionPuesto[];
  estacionados?: VehiculoId[];
  falsas_liberaciones?: SesionId[];
}

export interface MensajeEspejo {
  tipo: 'espejo';
  veh_id: VehiculoId;
  t_sim: number;
  ts: FechaISO;
  estado?: EstadoSesion | null;
  lat: number;
  lon: number;
  modo?: Modo | null;
  destino?: Destino | null;
  puesto?: PuestoEspejo | null;
  ruta?: Coordenada[];
  sesion?: SesionEspejo | null;
  billetera?: BilleteraEspejo | null;
  avisos?: Aviso[];
  recibo?: Recibo | null;
}

export interface MensajeEspejoFin {
  tipo: 'espejo_fin';
  veh_id: VehiculoId;
  t_sim?: number | null;
  ts: FechaISO;
  motivo: MotivoFinEspejo;
}

export type MensajeWS =
  | MensajeSnapshot
  | MensajeKpi
  | MensajeVerdad
  | MensajeEspejo
  | MensajeEspejoFin;

// --- Trazas GPS (§8) ---
export const COLUMNAS_TRAZA = [
  'usuario_id',
  't',
  'lat',
  'lon',
  'precision_m',
  'velocidad_mps',
  'modo_real',
] as const;

export interface FilaTraza {
  usuario_id: string;
  t: number;
  lat: number;
  lon: number;
  precision_m?: number | null;
  velocidad_mps?: number | null;
  modo_real?: Modo | null;
}
