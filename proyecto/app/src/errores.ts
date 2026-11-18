import { TARIFA } from '@/src/api/tarifa';
import { ErrorApi, type CodigoError } from '@/src/api/tipos';

// Traducción de los errores a mensajes en español con una acción. Ningún error técnico crudo
// (texto del servidor, HTML de un proxy, TypeError…) llega a la pantalla: lo desconocido se
// muestra con un mensaje genérico y el detalle va solo al registro (console.warn).

export type Accion = 'recargar' | 'buscar_otro' | 'reintentar' | 'ajustes' | 'volver';

export interface ErrorUsuario {
  mensaje: string;
  accion: Accion | null;
  /** Texto del botón de la acción. */
  etiqueta: string | null;
}

/** Códigos propios del cliente (no vienen del servidor). */
export type CodigoCliente = 'SIN_CONEXION' | 'TIEMPO_AGOTADO';

const ETIQUETAS: Record<Accion, string> = {
  recargar: 'Recargar',
  buscar_otro: 'Buscar otro puesto',
  reintentar: 'Reintentar',
  ajustes: 'Revisar conexión',
  volver: 'Volver al inicio',
};

const recarga = `$${TARIFA.recarga_minima_usd.toFixed(0)}`;

/** Cada código del contrato (§4.2) y los dos del cliente, con su mensaje y su acción. */
export const ERRORES: Record<CodigoError | CodigoCliente, { mensaje: string; accion: Accion | null }> = {
  SALDO_INSUFICIENTE: { mensaje: `Te falta saldo: recarga al menos ${recarga} para buscar puesto.`, accion: 'recargar' },
  SESIONES_BLOQUEADAS: { mensaje: `Tu saldo es negativo: recarga al menos ${recarga} para volver a parquear.`, accion: 'recargar' },
  RECARGA_MINIMA: { mensaje: `La recarga mínima es ${recarga}.`, accion: 'recargar' },
  SIN_PUESTOS_LIBRES: { mensaje: 'No hay puestos libres cerca de ese destino. Prueba con otro.', accion: 'buscar_otro' },
  PUESTO_LLENO: { mensaje: 'Ese puesto acaba de ocuparse.', accion: 'buscar_otro' },
  PUESTO_NO_EXISTE: { mensaje: 'Ese puesto no existe. Revisa el código o busca otro.', accion: 'buscar_otro' },
  SESION_ACTIVA: { mensaje: 'Ya tienes una sesión abierta. Termínala antes de iniciar otra.', accion: 'volver' },
  SESION_NO_EXISTE: { mensaje: 'No encontramos esa sesión: puede que ya no exista en el servidor.', accion: 'volver' },
  SESION_YA_CERRADA: { mensaje: 'Esta sesión ya estaba cerrada.', accion: 'volver' },
  TRANSICION_INVALIDA: { mensaje: 'La sesión no puede pasar a ese estado ahora.', accion: 'reintentar' },
  VEHICULO_NO_EXISTE: { mensaje: 'Ese auto simulado ya no está en la simulación. Elige otro.', accion: 'volver' },
  VALIDACION: { mensaje: 'Algún dato no es válido. Revisa la placa y el puesto.', accion: null },
  CONTRATO_INCOMPATIBLE: { mensaje: 'La app y el servidor no son compatibles. Actualiza la app.', accion: null },
  TOKEN_SIM_INVALIDO: { mensaje: 'Esa operación solo la puede hacer el simulador.', accion: null },
  CLAVE_DEMO_INVALIDA: { mensaje: 'La clave de la demo no es correcta.', accion: null },
  DEMO_EN_CURSO: { mensaje: 'Ya hay una simulación en curso.', accion: null },
  DEMO_NO_DISPONIBLE: { mensaje: 'La simulación no está disponible en este servidor.', accion: null },
  ERROR_INTERNO: { mensaje: 'El servidor tuvo un problema.', accion: 'reintentar' },
  SIN_CONEXION: { mensaje: 'No hay conexión con el servidor. Revisa la red.', accion: 'ajustes' },
  TIEMPO_AGOTADO: { mensaje: 'El servidor tardó demasiado en responder.', accion: 'reintentar' },
};

const GENERICO: ErrorUsuario = { mensaje: 'Algo salió mal. Inténtalo de nuevo.', accion: 'reintentar', etiqueta: ETIQUETAS.reintentar };

function conEtiqueta(e: { mensaje: string; accion: Accion | null }): ErrorUsuario {
  return { ...e, etiqueta: e.accion ? ETIQUETAS[e.accion] : null };
}

/** Error cuyo texto ya está escrito para el usuario (p. ej. "Sin permiso de ubicación…"). */
export class ErrorParaUsuario extends Error {
  constructor(
    mensaje: string,
    readonly accion: Accion | null = null,
  ) {
    super(mensaje);
    this.name = 'ErrorParaUsuario';
  }
}

/** Error (de la API, de la red o cualquier otro) → mensaje para el usuario y acción sugerida. */
export function describirError(error: unknown): ErrorUsuario {
  if (error instanceof ErrorParaUsuario) return conEtiqueta({ mensaje: error.message, accion: error.accion });
  if (error instanceof ErrorApi) {
    const conocido = ERRORES[error.codigo as CodigoError | CodigoCliente];
    if (conocido) return conEtiqueta(conocido);
    if (error.codigo.startsWith('HTTP_')) {
      // Sin cuerpo del contrato (p. ej. un 502 del proxy): no se muestra el HTML crudo.
      return conEtiqueta({ mensaje: `El servidor respondió con un error (${error.estado}).`, accion: 'reintentar' });
    }
  }
  console.warn('[errores] error sin traducir:', error);
  return GENERICO;
}

/** Solo el texto (para los lugares que no muestran botón). */
export const mensajeDeError = (error: unknown): string => describirError(error).mensaje;
