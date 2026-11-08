import { raizApi, TIEMPO_ESPERA_MS } from './cliente';
import { TARIFA } from './tarifa';
import { CONTRATO_VERSION, ErrorApi, type CuerpoError, type UsuarioId } from './tipos';

// Rutas /pagos/* de backend/pagos (Miguel). No están en el contrato v1: van como pedido a
// Freddy para CONTRATO.propuesto.md (S2-2).

export type EstadoIntencion = 'pendiente' | 'aprobado' | 'rechazado';

export interface PagoPreparado {
  client_transaction_id: string;
  payment_id: string;
  pay_url: string;
  modo: 'mock' | 'pruebas';
}

export interface IntencionPago {
  client_transaction_id: string;
  usuario_id: UsuarioId;
  monto: number;
  estado: EstadoIntencion;
  referencia_payphone: string | null;
  creada: string;
  actualizada: string;
}

export const MONTOS_RAPIDOS = [5, 10, 20] as const;
export const INTENTOS_CONSULTA = 10;
export const ESPERA_CONSULTA_MS = 2_000;

/** Valida el monto libre (texto del teclado, con coma o punto). Devuelve el número o un error. */
export function leerMonto(texto: string): { monto: number } | { error: string } {
  const limpio = texto.trim().replace(',', '.').replace(/^\$/, '');
  if (!/^\d+(\.\d{1,2})?$/.test(limpio)) return { error: 'Escribe un monto como 7.50' };
  const monto = Number(limpio);
  if (monto < TARIFA.recarga_minima_usd) {
    return { error: `La recarga mínima es $${TARIFA.recarga_minima_usd.toFixed(2)}` };
  }
  if (monto > 1000) return { error: 'El monto máximo por recarga es $1000' };
  return { monto };
}

async function pedir<T>(urlApi: string, metodo: 'GET' | 'POST', ruta: string, cuerpo?: unknown): Promise<T> {
  const control = new AbortController();
  const temporizador = setTimeout(() => control.abort(), TIEMPO_ESPERA_MS);
  let respuesta: Response;
  let texto: string;
  try {
    respuesta = await fetch(`${raizApi(urlApi)}${ruta}`, {
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
    throw new ErrorApi(0, abortado ? 'TIEMPO_AGOTADO' : 'SIN_CONEXION', 'Sin respuesta del servidor de pagos');
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
  return datos as T;
}

/** POST /pagos/preparar. `urlApp` es el deep link al que vuelve la página de retorno. */
export const prepararPago = (urlApi: string, usuarioId: UsuarioId, monto: number, urlApp: string) =>
  pedir<PagoPreparado>(urlApi, 'POST', '/pagos/preparar', { usuario_id: usuarioId, monto, url_app: urlApp });

/** GET /pagos/{client_transaction_id}. */
export const consultarPago = (urlApi: string, clientTransactionId: string) =>
  pedir<IntencionPago>(urlApi, 'GET', `/pagos/${encodeURIComponent(clientTransactionId)}`);

const pausa = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Consulta la intención hasta que deje de estar pendiente: INTENTOS_CONSULTA veces cada
 * ESPERA_CONSULTA_MS. Si se agotan los intentos devuelve la última (todavía pendiente).
 */
export async function esperarConfirmacion(
  consultar: () => Promise<IntencionPago>,
  intentos = INTENTOS_CONSULTA,
  esperaMs = ESPERA_CONSULTA_MS,
): Promise<IntencionPago> {
  let ultima: IntencionPago | null = null;
  let ultimoError: unknown = null;
  for (let i = 0; i < intentos; i++) {
    try {
      ultima = await consultar();
      if (ultima.estado !== 'pendiente') return ultima;
    } catch (e) {
      ultimoError = e;
    }
    if (i < intentos - 1) await pausa(esperaMs);
  }
  if (ultima) return ultima;
  throw ultimoError;
}
