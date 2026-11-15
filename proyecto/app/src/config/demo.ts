import AsyncStorage from '@react-native-async-storage/async-storage';

import { raizApi } from '@/src/api/cliente';
import { origenServidor, urlWsEspejo } from '@/src/api/espejo';

// Configuración de la demo (S4-1): a qué backend apunta la app, sin reinstalar. La URL elegida en
// "Ajustes de demo" se guarda en AsyncStorage y manda sobre EXPO_PUBLIC_API_URL.

export const URL_VPS = 'https://demo.e-sert.tesisucuenca.com';
/** Puerto del backend en `demo.py --local` de Tyrone (uvicorn en la computadora). */
export const PUERTO_LOCAL = 8000;
export const CLAVE_URL_DEMO = 'esert_demo_url_v1';
export const CLAVE_IP_LOCAL = 'esert_demo_ip_local_v1';

export async function leerUrlDemo(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(CLAVE_URL_DEMO);
  } catch {
    return null;
  }
}

export async function guardarUrlDemo(url: string): Promise<void> {
  try {
    await AsyncStorage.setItem(CLAVE_URL_DEMO, url);
  } catch {
    // sin persistencia: vale hasta cerrar la app
  }
}

export async function leerIpLocal(): Promise<string> {
  try {
    return (await AsyncStorage.getItem(CLAVE_IP_LOCAL)) ?? '';
  } catch {
    return '';
  }
}

export async function guardarIpLocal(ip: string): Promise<void> {
  await AsyncStorage.setItem(CLAVE_IP_LOCAL, ip).catch(() => undefined);
}

/** "192.168.1.20" o "192.168.1.20:8000" → "http://192.168.1.20:8000". */
export function urlLocal(ip: string): string {
  const limpia = ip.trim().replace(/^https?:\/\//, '').replace(/\/+$/, '');
  return `http://${/:\d+$/.test(limpia) ? limpia : `${limpia}:${PUERTO_LOCAL}`}`;
}

export interface Prueba {
  ok: boolean;
  ms: number | null;
  detalle: string;
}

async function medir(url: string, esperaMs: number): Promise<{ respuesta: Response | null; ms: number; error?: string }> {
  const control = new AbortController();
  const t = setTimeout(() => control.abort(), esperaMs);
  const t0 = Date.now();
  try {
    const respuesta = await fetch(url, { headers: { Accept: 'application/json' }, signal: control.signal, cache: 'no-store' });
    return { respuesta, ms: Date.now() - t0 };
  } catch (e) {
    return { respuesta: null, ms: Date.now() - t0, error: (e as Error)?.name === 'AbortError' ? 'sin respuesta' : 'sin conexión' };
  } finally {
    clearTimeout(t);
  }
}

/** GET /salud y GET /api/v1/espejo/candidatos, con su latencia. */
export async function probarConexion(urlBase: string, esperaMs = 6000): Promise<{ salud: Prueba; candidatos: Prueba; ids: string[] }> {
  const s = await medir(`${origenServidor(urlBase)}/salud`, esperaMs);
  const salud: Prueba = s.respuesta?.ok
    ? { ok: true, ms: s.ms, detalle: 'responde' }
    : { ok: false, ms: s.respuesta ? s.ms : null, detalle: s.error ?? `HTTP ${s.respuesta?.status}` };
  const c = await medir(`${raizApi(urlBase)}/espejo/candidatos`, esperaMs);
  let ids: string[] = [];
  let candidatos: Prueba;
  if (c.respuesta?.ok) {
    try {
      ids = ((await c.respuesta.json()) as { id: string }[]).map((x) => x.id);
      candidatos = { ok: true, ms: c.ms, detalle: `${ids.length} autos con app` };
    } catch {
      candidatos = { ok: false, ms: c.ms, detalle: 'respuesta inválida' };
    }
  } else {
    candidatos = { ok: false, ms: c.respuesta ? c.ms : null, detalle: c.error ?? `HTTP ${c.respuesta?.status}` };
  }
  return { salud, candidatos, ids };
}

/** Abre WS /ws/espejo/{veh_id} y mide cuánto tarda el primer mensaje (máx. 6 s). */
export function probarWsEspejo(urlBase: string, vehId: string, esperaMs = 6000): Promise<Prueba> {
  return new Promise((resolver) => {
    const t0 = Date.now();
    let listo = false;
    const ws = new WebSocket(urlWsEspejo(urlBase, vehId));
    const terminar = (p: Prueba) => {
      if (listo) return;
      listo = true;
      clearTimeout(t);
      try {
        ws.close();
      } catch {
        // ya cerrado
      }
      resolver(p);
    };
    const t = setTimeout(() => terminar({ ok: false, ms: null, detalle: 'sin mensajes en 6 s' }), esperaMs);
    ws.onmessage = (ev) => {
      let tipo = '?';
      try {
        tipo = (JSON.parse(String(ev.data)) as { tipo?: string }).tipo ?? '?';
      } catch {
        // mensaje no JSON
      }
      terminar({ ok: tipo === 'espejo', ms: Date.now() - t0, detalle: tipo === 'espejo' ? `${vehId} en vivo` : `recibió ${tipo}` });
    };
    ws.onerror = () => terminar({ ok: false, ms: null, detalle: 'no se pudo abrir el WebSocket' });
  });
}

// Estado del WebSocket del espejo que esté abierto, para mostrarlo en Ajustes de demo.
export type EstadoWsEspejo = { estado: string; vehId: string | null; desde: number };
let estadoWs: EstadoWsEspejo = { estado: 'cerrado', vehId: null, desde: Date.now() };
const oyentes = new Set<(e: EstadoWsEspejo) => void>();

export function reportarEstadoEspejo(estado: string, vehId: string | null): void {
  if (estado === estadoWs.estado && vehId === estadoWs.vehId) return;
  estadoWs = { estado, vehId, desde: Date.now() };
  oyentes.forEach((f) => f(estadoWs));
}

export function suscribirEstadoEspejo(f: (e: EstadoWsEspejo) => void): () => void {
  oyentes.add(f);
  f(estadoWs);
  return () => oyentes.delete(f);
}
