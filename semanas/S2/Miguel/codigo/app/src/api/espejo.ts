import { raizApi, TIEMPO_ESPERA_MS, URL_POR_DEFECTO } from './cliente';
import { CONTRATO_VERSION, ErrorApi, type CandidatoEspejo, type CuerpoError, type VehiculoId } from './tipos';

// Modo espejo (CONTRATO §7): GET /api/v1/espejo/candidatos y WS /ws/espejo/{veh_id}.
// EXPO_PUBLIC_ESPEJO_URL permite apuntar solo el espejo a otro servidor (p. ej. el mock local
// en el puerto 8001) sin mover el resto de la app; si no está, se usa la URL de Ajustes.
// MOCK: el WS lo sirve app/mock_espejo/ hasta que Freddy publique el espejo (S3-3).
export const URL_ESPEJO_POR_DEFECTO = process.env.EXPO_PUBLIC_ESPEJO_URL ?? null;

/** Base del espejo: la variable propia o la URL de la API elegida en Ajustes. */
export function baseEspejo(urlApi: string = URL_POR_DEFECTO): string {
  return URL_ESPEJO_POR_DEFECTO ?? urlApi;
}

/** Origen del servidor sin /api/v1 (el WS no lleva ese prefijo). */
export function origenServidor(urlBase: string): string {
  return raizApi(urlBase).replace(/\/api\/v\d+$/, '');
}

/** URL del WebSocket: https → wss y http → ws. */
export function urlWsEspejo(urlBase: string, vehId: VehiculoId): string {
  const origen = origenServidor(urlBase).replace(/^http(s?):\/\//, (_, s: string) => `ws${s}://`);
  return `${origen}/ws/espejo/${encodeURIComponent(vehId)}`;
}

/** URL de /salud para estimar el desfase de reloj (latencia.ts). */
export function urlSalud(urlBase: string): string {
  return `${raizApi(urlBase)}/salud`;
}

export async function getCandidatos(
  urlBase: string = baseEspejo(),
  esperaMs = TIEMPO_ESPERA_MS,
): Promise<CandidatoEspejo[]> {
  const raiz = raizApi(urlBase);
  const control = new AbortController();
  const temporizador = setTimeout(() => control.abort(), esperaMs);
  let respuesta: Response;
  let texto: string;
  try {
    respuesta = await fetch(`${raiz}/espejo/candidatos`, {
      headers: { Accept: 'application/json', 'X-Contrato-Version': CONTRATO_VERSION },
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
  try {
    datos = texto ? JSON.parse(texto) : null;
  } catch {
    datos = null;
  }
  if (!respuesta.ok) {
    const e = (datos as CuerpoError | null)?.error;
    if (typeof e?.codigo === 'string') throw new ErrorApi(respuesta.status, e.codigo, e.mensaje);
    throw new ErrorApi(respuesta.status, `HTTP_${respuesta.status}`, texto || respuesta.statusText);
  }
  if (!Array.isArray(datos)) throw new ErrorApi(respuesta.status, 'VALIDACION', 'La lista de candidatos no es válida');
  return (datos as CandidatoEspejo[]).map((c) => ({ ...c, estado: c.estado ?? null }));
}
