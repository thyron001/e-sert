import { crearClienteMock } from './mock';
import { TARIFA } from './tarifa';
import {
  CONTRATO_VERSION,
  ErrorApi,
  type ApiESert,
  type Billetera,
  type CierreSesion,
  type ConsultaGuia,
  type CuerpoError,
  type Guia,
  type NuevaSesion,
  type Sesion,
  type SesionCerrada,
  type SesionCreada,
  type SesionId,
  type UsuarioId,
} from './tipos';

// EXPO_PUBLIC_API_URL: con o sin /api/v1 (p. ej. http://192.168.1.20:8000/api/v1). En el
// teléfono nunca localhost: es el propio teléfono. Sin variable, la demo del VPS.
export const URL_POR_DEFECTO =
  process.env.EXPO_PUBLIC_API_URL ?? 'https://demo.e-sert.tesisucuenca.com/api/v1';

/** Solo EXPO_PUBLIC_USE_MOCK=1 arranca con el cliente mock; sin variable, backend real (se cambia en Ajustes). */
export const MOCK_POR_DEFECTO = process.env.EXPO_PUBLIC_USE_MOCK === '1';

export const TIEMPO_ESPERA_MS = 8_000;

/** Raíz de la API: acepta la URL del servidor o la URL ya terminada en /api/v1. */
export function raizApi(urlBase: string): string {
  const limpia = urlBase.trim().replace(/\/+$/, '');
  return /\/api\/v\d+$/.test(limpia) ? limpia : `${limpia}/api/v1`;
}

function esCuerpoError(cuerpo: unknown): cuerpo is CuerpoError {
  const e = (cuerpo as CuerpoError | null)?.error;
  return typeof e?.codigo === 'string' && typeof e?.mensaje === 'string';
}

const recarga = `$${TARIFA.recarga_minima_usd.toFixed(0)}`;

// Lo que ve el usuario para cada código (CONTRATO §4.2 y los dos códigos propios del cliente).
const MENSAJES: Record<string, string> = {
  SALDO_INSUFICIENTE: `Recarga al menos ${recarga} para buscar puesto`,
  SESIONES_BLOQUEADAS: `Tu saldo es negativo: recarga al menos ${recarga} para volver a parquear`,
  SIN_PUESTOS_LIBRES: 'No hay puestos libres cerca de ese destino. Prueba con otro.',
  PUESTO_LLENO: 'Ese puesto acaba de ocuparse. Busca otro.',
  PUESTO_NO_EXISTE: 'Ese puesto no existe. Revisa el código del puesto.',
  SESION_ACTIVA: 'Ya tienes una sesión abierta. Termínala antes de iniciar otra.',
  SESION_NO_EXISTE: 'No se encontró la sesión.',
  VEHICULO_NO_EXISTE: 'Ese vehículo simulado ya no está en la simulación.',
  SESION_YA_CERRADA: 'Esta sesión ya estaba cerrada.',
  TRANSICION_INVALIDA: 'La sesión no puede pasar a ese estado ahora.',
  RECARGA_MINIMA: `La recarga mínima es ${recarga}.`,
  VALIDACION: 'Algún dato no es válido. Revisa la placa y el puesto.',
  CONTRATO_INCOMPATIBLE: 'La app y el servidor usan versiones distintas del contrato. Actualiza la app.',
  TOKEN_SIM_INVALIDO: 'Operación reservada al simulador.',
  ERROR_INTERNO: 'El servidor tuvo un problema. Inténtalo de nuevo.',
  SIN_CONEXION: 'No hay conexión con el servidor. Revisa la red o la URL en Ajustes.',
  TIEMPO_AGOTADO: 'El servidor no respondió a tiempo. Inténtalo de nuevo.',
};

/** Mensaje en español para el usuario; si el código no se conoce, el mensaje del servidor. */
export function mensajeUsuario(error: unknown): string {
  if (error instanceof ErrorApi) {
    // Errores sin cuerpo del contrato (p. ej. un 502 del proxy): no se muestra el HTML crudo.
    if (error.codigo.startsWith('HTTP_')) return `El servidor respondió con un error (${error.estado}). Inténtalo de nuevo.`;
    return MENSAJES[error.codigo] ?? error.message;
  }
  return (error as Error)?.message ?? String(error);
}

/** Cliente HTTP real contra el backend FastAPI de Freddy. */
export function crearClienteHttp(urlBase: string = URL_POR_DEFECTO, esperaMs = TIEMPO_ESPERA_MS): ApiESert {
  const raiz = raizApi(urlBase);

  async function pedir<T>(metodo: 'GET' | 'POST', ruta: string, cuerpo?: unknown): Promise<T> {
    const control = new AbortController();
    const temporizador = setTimeout(() => control.abort(), esperaMs);
    let respuesta: Response;
    let texto: string;
    try {
      respuesta = await fetch(`${raiz}${ruta}`, {
        method: metodo,
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-Contrato-Version': CONTRATO_VERSION,
        },
        body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
        signal: control.signal,
      });
      texto = await respuesta.text();
    } catch (e) {
      const abortado = (e as Error)?.name === 'AbortError';
      throw new ErrorApi(
        0,
        abortado ? 'TIEMPO_AGOTADO' : 'SIN_CONEXION',
        abortado ? `Sin respuesta de ${raiz} en ${esperaMs / 1000} s` : `No se pudo conectar con ${raiz}`,
      );
    } finally {
      clearTimeout(temporizador);
    }

    let datos: unknown = null;
    if (texto) {
      try {
        datos = JSON.parse(texto);
      } catch {
        datos = null;
      }
    }

    if (!respuesta.ok) {
      if (esCuerpoError(datos)) {
        throw new ErrorApi(respuesta.status, datos.error.codigo, datos.error.mensaje);
      }
      throw new ErrorApi(respuesta.status, `HTTP_${respuesta.status}`, texto || respuesta.statusText);
    }
    return datos as T;
  }

  const id = (valor: SesionId | UsuarioId) => encodeURIComponent(valor);

  return {
    listarPuestos: () => pedir('GET', '/puestos'),
    pedirGuia: (c) => {
      const q = new URLSearchParams({
        lat: String(c.lat),
        lon: String(c.lon),
        destino_lat: String(c.destino_lat),
        destino_lon: String(c.destino_lon),
      });
      return pedir('GET', `/guia?${q.toString()}`);
    },
    enviarUbicacion: async (evento) => {
      await pedir('POST', '/eventos/ubicacion', evento);
    },
    enviarModo: async (evento) => {
      await pedir('POST', '/eventos/modo', evento);
    },
    crearSesion: (datos) => pedir('POST', '/sesiones', datos),
    cerrarSesion: (sesionId, datos) => pedir('POST', `/sesiones/${id(sesionId)}/cerrar`, datos),
    obtenerSesion: (sesionId) => pedir('GET', `/sesiones/${id(sesionId)}`),
    obtenerBilletera: (usuarioId) => pedir('GET', `/billetera/${id(usuarioId)}`),
    recargar: (usuarioId, datos) => pedir('POST', `/billetera/${id(usuarioId)}/recarga`, datos),
  };
}

// Funciones tipadas del flujo de sesión. Las pantallas pasan el cliente de Ajustes (real o
// mock); sin cliente se usa el que indican las variables EXPO_PUBLIC_*.
// MOCK: crearClienteMock() se usa mientras EXPO_PUBLIC_USE_MOCK=1 o el backend no responda.
let clientePorDefecto: ApiESert | null = null;
function porDefecto(): ApiESert {
  clientePorDefecto ??= MOCK_POR_DEFECTO ? crearClienteMock() : crearClienteHttp();
  return clientePorDefecto;
}

export const getGuia = (c: ConsultaGuia, api: ApiESert = porDefecto()): Promise<Guia> => api.pedirGuia(c);
export const crearSesion = (d: NuevaSesion, api: ApiESert = porDefecto()): Promise<SesionCreada> =>
  api.crearSesion(d);
export const getSesion = (s: SesionId, api: ApiESert = porDefecto()): Promise<Sesion> => api.obtenerSesion(s);
export const cerrarSesion = (s: SesionId, d: CierreSesion, api: ApiESert = porDefecto()): Promise<SesionCerrada> =>
  api.cerrarSesion(s, d);
export const getBilletera = (u: UsuarioId, api: ApiESert = porDefecto()): Promise<Billetera> =>
  api.obtenerBilletera(u);
