// MOCK: reemplazar cuando Freddy publique WS /ws/espejo (S3-3).
// (Freddy ya lo publicó en S3-3; el mock se queda para trabajar sin backend ni simulación.)
//
// Reproduce el recorrido de S1-3/S2-3 (recorridoMock.ts) pero comprime la sesión para que el
// mensaje CERRADA, con `recibo`, llegue SEGUNDOS_HASTA_CIERRE después del primer ESTACIONADO.
// El recibo es el del recorrido (47 min reales), coherente con src/logica/tarifa.ts.

import type { EstadoSesion, MensajeEspejo, MensajeEspejoWS } from '@/src/api/tipos';
import { generarRecorrido } from '@/src/espejo/recorridoMock';

export const SEGUNDOS_HASTA_CIERRE = 20;

/** Estados de la sesión que se comprimen (de ESTACIONADO a SALIENDO). */
const EN_SESION: readonly EstadoSesion[] = ['ESTACIONADO', 'A_PIE', 'REGRESANDO', 'SALIENDO'];

/** Toma `n` elementos repartidos de forma pareja, conservando el primero y el último. */
function repartir<T>(xs: T[], n: number): T[] {
  if (xs.length <= n) return xs;
  return Array.from({ length: n }, (_, k) => xs[Math.round((k * (xs.length - 1)) / Math.max(1, n - 1))]);
}

/** Recorrido con cierre: antes de estacionar igual; la sesión en 20 mensajes; luego CERRADA y fin. */
export function generarRecorridoCierre(vehId = 'sim_veh42'): MensajeEspejoWS[] {
  const todos = generarRecorrido(vehId);
  const espejo = todos.filter((m): m is MensajeEspejo => m.tipo === 'espejo');
  const antes = espejo.filter((m) => !m.estado || (!EN_SESION.includes(m.estado) && m.estado !== 'CERRADA'));
  const sesion = espejo.filter((m) => m.estado && EN_SESION.includes(m.estado));
  const cerrada = espejo.filter((m) => m.estado === 'CERRADA');
  const fin = todos[todos.length - 1];
  // Cada estado de la sesión conserva al menos un mensaje.
  const comprimida = repartir(sesion, SEGUNDOS_HASTA_CIERRE);
  return [...antes, ...comprimida, ...cerrada.slice(0, 3), fin];
}

/** Misma firma que suscribirMock (S1-3): un mensaje por intervalo, el primero enseguida. */
export function suscribirCierreMock(
  vehId: string,
  onMensaje: (m: MensajeEspejoWS) => void,
  opciones: { intervaloMs?: number } = {},
): () => void {
  const mensajes = generarRecorridoCierre(vehId);
  let i = 0;
  const emitir = () => {
    if (i >= mensajes.length) return clearInterval(id);
    onMensaje({ ...mensajes[i++], ts: new Date().toISOString() });
  };
  const id = setInterval(emitir, opciones.intervaloMs ?? 1000);
  emitir();
  return () => clearInterval(id);
}
