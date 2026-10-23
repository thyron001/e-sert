import {
  CONTRATO_VERSION,
  ErrorApi,
  type ApiESert,
  type CuerpoError,
  type SesionId,
  type UsuarioId,
} from './tipos';

export const URL_POR_DEFECTO =
  process.env.EXPO_PUBLIC_API_URL ?? 'https://demo.e-sert.tesisucuenca.com';

const TIEMPO_ESPERA_MS = 10_000;

function esCuerpoError(cuerpo: unknown): cuerpo is CuerpoError {
  const e = (cuerpo as CuerpoError | null)?.error;
  return typeof e?.codigo === 'string' && typeof e?.mensaje === 'string';
}

/** Cliente HTTP real contra el backend FastAPI (prefijo /api/v1). */
export function crearClienteHttp(urlBase: string = URL_POR_DEFECTO): ApiESert {
  const raiz = `${urlBase.replace(/\/+$/, '')}/api/v1`;

  async function pedir<T>(
    metodo: 'GET' | 'POST',
    ruta: string,
    cuerpo?: unknown,
    permitir404 = false,
  ): Promise<T | null> {
    const control = new AbortController();
    const temporizador = setTimeout(() => control.abort(), TIEMPO_ESPERA_MS);
    let respuesta: Response;
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
    } catch (e) {
      const abortado = (e as Error)?.name === 'AbortError';
      throw new ErrorApi(
        0,
        abortado ? 'TIEMPO_AGOTADO' : 'SIN_CONEXION',
        abortado ? `Sin respuesta de ${raiz} en ${TIEMPO_ESPERA_MS / 1000} s` : `No se pudo conectar con ${raiz}`,
      );
    } finally {
      clearTimeout(temporizador);
    }

    if (permitir404 && respuesta.status === 404) return null;

    const texto = await respuesta.text();
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
    listarPuestos: async () => (await pedir('GET', '/puestos'))!,
    pedirGuia: (c) => {
      const q = new URLSearchParams({
        lat: String(c.lat),
        lon: String(c.lon),
        destino_lat: String(c.destino_lat),
        destino_lon: String(c.destino_lon),
      });
      return pedir('GET', `/guia?${q.toString()}`, undefined, true);
    },
    enviarUbicacion: async (evento) => {
      await pedir('POST', '/eventos/ubicacion', evento);
    },
    enviarModo: async (evento) => {
      await pedir('POST', '/eventos/modo', evento);
    },
    crearSesion: async (datos) => (await pedir('POST', '/sesiones', datos))!,
    cerrarSesion: async (sesionId, datos) =>
      (await pedir('POST', `/sesiones/${id(sesionId)}/cerrar`, datos))!,
    obtenerSesion: async (sesionId) => (await pedir('GET', `/sesiones/${id(sesionId)}`))!,
    obtenerBilletera: async (usuarioId) => (await pedir('GET', `/billetera/${id(usuarioId)}`))!,
    recargar: async (usuarioId, datos) =>
      (await pedir('POST', `/billetera/${id(usuarioId)}/recarga`, datos))!,
  };
}
