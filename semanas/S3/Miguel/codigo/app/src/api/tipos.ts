// Tipos de la app. Los del contrato vienen de src/contrato/esquemas.ts (copia de comun/):
// aquí solo se añade lo propio de la app (ErrorApi, ApiESert y los mensajes del espejo).
import type {
  Aviso,
  Billetera,
  BilleteraEspejo,
  CierreSesion,
  ConsultaGuia,
  Coordenada,
  Destino,
  EstadoSesion,
  EventoModo,
  EventoUbicacion,
  FechaISO,
  Guia,
  Modo,
  MotivoFinEspejo,
  NuevaSesion,
  Puesto,
  PuestoEspejo,
  Recarga,
  RecargaHecha,
  Recibo,
  Sesion,
  SesionCerrada,
  SesionCreada,
  SesionEspejo,
  SesionId,
  UsuarioId,
  VehiculoId,
} from '@/src/contrato/esquemas';

export * from '@/src/contrato/esquemas';

/** Códigos que solo genera el cliente: el backend nunca los envía (CONTRATO §4.2). */
export type CodigoCliente = 'SIN_CONEXION' | 'TIEMPO_AGOTADO';

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

// --- Modo espejo (CONTRATO §6b v0 = §7 de la propuesta v1) ---
// CandidatoEspejo y MensajeEspejo son versiones más estrictas de las de esquemas.ts: aquí los
// campos son obligatorios y nullables (así los trae siempre el JSON de §7), y validar.ts lo comprueba.

export const ESTADOS_SESION: readonly EstadoSesion[] = [
  'BUSCANDO',
  'GUIADO',
  'ESTACIONADO',
  'A_PIE',
  'REGRESANDO',
  'SALIENDO',
  'CERRADA',
];

export interface CandidatoEspejo {
  id: VehiculoId;
  destino_nombre: string;
  estado: EstadoSesion | null;
  t_sim: number;
}

export type ReciboEspejo = Recibo;

export interface MensajeEspejo {
  tipo: 'espejo';
  veh_id: VehiculoId;
  t_sim: number;
  ts: FechaISO;
  estado: EstadoSesion | null;
  lat: number;
  lon: number;
  modo: Modo | null;
  destino: Destino | null;
  puesto: PuestoEspejo | null;
  ruta: Coordenada[];
  sesion: SesionEspejo | null;
  billetera: BilleteraEspejo | null;
  avisos: Aviso[];
  recibo: ReciboEspejo | null;
}

export interface FinEspejo {
  tipo: 'espejo_fin';
  veh_id: VehiculoId;
  t_sim?: number | null; // v1
  ts?: FechaISO; // v1
  motivo?: MotivoFinEspejo; // v1
}

export type MensajeEspejoWS = MensajeEspejo | FinEspejo;

/** Interfaz común: la cumplen el cliente HTTP real (cliente.ts) y el mock (mock.ts). */
export interface ApiESert {
  listarPuestos(): Promise<Puesto[]>;
  /** Lanza ErrorApi SIN_PUESTOS_LIBRES (404) si no hay puesto libre. */
  pedirGuia(consulta: ConsultaGuia): Promise<Guia>;
  enviarUbicacion(evento: EventoUbicacion): Promise<void>;
  enviarModo(evento: EventoModo): Promise<void>;
  crearSesion(datos: NuevaSesion): Promise<SesionCreada>;
  cerrarSesion(sesionId: SesionId, datos: CierreSesion): Promise<SesionCerrada>;
  obtenerSesion(sesionId: SesionId): Promise<Sesion>;
  obtenerBilletera(usuarioId: UsuarioId): Promise<Billetera>;
  recargar(usuarioId: UsuarioId, datos: Recarga): Promise<RecargaHecha>;
}
