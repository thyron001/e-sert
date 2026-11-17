import { raizApi, URL_POR_DEFECTO } from './cliente';
import { CONTRATO_VERSION, ErrorApi, type CuerpoError } from './tipos';

// Asistente de entrada natural (backend/asistente, S3-3): POST /api/v1/asistente/interpretar.
// Mensaje nuevo, pedido a Freddy para el contrato. EXPO_PUBLIC_ASISTENTE_URL permite apuntarlo a
// app_dev.py (puerto 8002) mientras Freddy no lo monte en la app principal.

export const URL_ASISTENTE = process.env.EXPO_PUBLIC_ASISTENTE_URL ?? null;
export const TIEMPO_ESPERA_ASISTENTE_MS = 10_000; // el backend espera al LLM hasta 8 s

export interface Interpretacion {
  destino: { nombre: string; lat: number; lon: number } | null;
  duracion_min: number | null;
  fuente: 'llm' | 'reglas';
  confianza: number;
  avisos: string[];
}

export function baseAsistente(urlApi: string = URL_POR_DEFECTO): string {
  return URL_ASISTENTE ?? urlApi;
}

export async function interpretarTexto(texto: string, urlBase: string = baseAsistente()): Promise<Interpretacion> {
  const control = new AbortController();
  const temporizador = setTimeout(() => control.abort(), TIEMPO_ESPERA_ASISTENTE_MS);
  let respuesta: Response;
  let cuerpo: string;
  try {
    respuesta = await fetch(`${raizApi(urlBase)}/asistente/interpretar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-Contrato-Version': CONTRATO_VERSION },
      body: JSON.stringify({ texto }),
      signal: control.signal,
    });
    cuerpo = await respuesta.text();
  } catch (e) {
    const abortado = (e as Error)?.name === 'AbortError';
    throw new ErrorApi(0, abortado ? 'TIEMPO_AGOTADO' : 'SIN_CONEXION', 'El asistente no respondió');
  } finally {
    clearTimeout(temporizador);
  }
  let datos: unknown = null;
  try {
    datos = cuerpo ? JSON.parse(cuerpo) : null;
  } catch {
    datos = null;
  }
  if (!respuesta.ok) {
    const e = (datos as CuerpoError | null)?.error;
    throw new ErrorApi(respuesta.status, e?.codigo ?? `HTTP_${respuesta.status}`, e?.mensaje ?? 'Error del asistente');
  }
  return datos as Interpretacion;
}
