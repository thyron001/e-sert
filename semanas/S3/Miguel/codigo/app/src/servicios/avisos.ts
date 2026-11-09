import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { TARIFA } from '@/src/api/tarifa';
import type { Billetera, Tarifa } from '@/src/api/tipos';
import { prepararNotificaciones } from '@/src/espejo/notificaciones';
import { calcularAvisos, escalaTiempo, type AvisoProgramado, type SesionParaAvisos } from '@/src/logica/calcularAvisos';

// Programación de los avisos de una sesión con notificaciones locales (en Expo Go no hay push
// remotas). Los IDs se guardan en AsyncStorage para poder cancelarlos aunque la app se reinicie.

export const CANAL_AVISOS = 'avisos';
export const CLAVE_PROGRAMADOS = 'esert_avisos_programados_v1';

export interface Programados {
  sesion_id: string;
  ids: string[];
  avisos: { tipo: AvisoProgramado['tipo']; cuando: string; titulo: string; cuerpo: string }[];
}

let canalListo: Promise<boolean> | null = null;

/** Tipos simples que cubre un aviso (el combinado cubre los dos). */
function componentes(tipo: AvisoProgramado['tipo']): string[] {
  return tipo === 'saldo_bajo_y_tiempo_maximo' ? ['saldo_bajo', 'tiempo_maximo'] : [tipo];
}

/** Permisos + handler en primer plano (los de S2-3) y canal Android "avisos" de alta importancia. */
export function prepararAvisos(): Promise<boolean> {
  canalListo ??= (async () => {
    await prepararNotificaciones();
    if (Platform.OS !== 'android') return true;
    try {
      await Notifications.setNotificationChannelAsync(CANAL_AVISOS, {
        name: 'Avisos de la sesión',
        importance: Notifications.AndroidImportance.HIGH,
      });
      return true;
    } catch (e) {
      // Expo Go (SDK 58, Android) rechaza crear canales (NullPointerException, ver S2-3): se usa el
      // canal por defecto.
      console.warn('[avisos] no se pudo crear el canal "avisos"; se usa el canal por defecto', e);
      return false;
    }
  })();
  return canalListo;
}

export async function leerProgramados(): Promise<Programados | null> {
  try {
    const texto = await AsyncStorage.getItem(CLAVE_PROGRAMADOS);
    return texto ? (JSON.parse(texto) as Programados) : null;
  } catch {
    return null;
  }
}

/** Cancela todas las notificaciones que se programaron para la sesión (o cualquiera guardada). */
export async function cancelarAvisos(): Promise<number> {
  const prog = await leerProgramados();
  if (!prog) return 0;
  await Promise.all(
    prog.ids.filter(Boolean).map((id) => Notifications.cancelScheduledNotificationAsync(id).catch(() => undefined)),
  );
  await AsyncStorage.removeItem(CLAVE_PROGRAMADOS).catch(() => undefined);
  let quedan = '?';
  try {
    quedan = String((await Notifications.getAllScheduledNotificationsAsync()).length);
  } catch {
    // sin la API (tests): no se informa
  }
  console.log(`[avisos] canceladas ${prog.ids.filter(Boolean).length} de ${prog.sesion_id}; programadas que quedan: ${quedan}`);
  return prog.ids.filter(Boolean).length;
}

/**
 * Al confirmar la llegada: calcula los avisos (calcularAvisos) y los programa con un disparador de
 * fecha. Antes cancela lo que hubiera, así que sirve también para reprogramar tras una recarga.
 */
export async function programarAvisos(
  sesion: SesionParaAvisos,
  billetera: Pick<Billetera, 'disponible'>,
  tarifa: Tarifa = TARIFA,
  ahora: Date = new Date(),
  escala: number = escalaTiempo(),
): Promise<Programados> {
  // Lo que ya venció en la programación anterior de ESTA sesión ya se avisó: al reprogramar
  // (p. ej. tras una recarga) no se vuelve a enviar.
  const previa = await leerProgramados();
  const yaEntregados = new Set<string>();
  if (previa?.sesion_id === sesion.sesion_id) {
    for (const a of previa.avisos) {
      if (Date.parse(a.cuando) > ahora.getTime()) continue;
      componentes(a.tipo).forEach((c) => yaEntregados.add(c));
    }
  }
  await cancelarAvisos();
  const conCanal = await prepararAvisos();
  const avisos = calcularAvisos(sesion, billetera, tarifa, ahora, escala).filter(
    (a) => !componentes(a.tipo).some((c) => yaEntregados.has(c)),
  );
  const ids: string[] = [];
  for (const a of avisos) {
    marcarAvisado(a.tipo, sesion.sesion_id);
    const fecha = new Date(Math.max(a.cuando.getTime(), ahora.getTime() + 1000));
    const id = await Notifications.scheduleNotificationAsync({
      content: { title: a.titulo, body: a.cuerpo, data: { sesion_id: sesion.sesion_id, tipo: a.tipo } },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: fecha,
        ...(conCanal ? { channelId: CANAL_AVISOS } : {}),
      },
    });
    ids.push(id);
  }
  const prog: Programados = {
    sesion_id: sesion.sesion_id,
    ids,
    avisos: avisos.map((a) => ({ ...a, cuando: a.cuando.toISOString() })),
  };
  await AsyncStorage.setItem(CLAVE_PROGRAMADOS, JSON.stringify(prog)).catch(() => undefined);
  console.log(
    `[avisos] programados ${ids.length} para ${sesion.sesion_id} (escala ${escala}): ` +
      prog.avisos.map((a) => `${a.tipo} ${a.cuando}`).join(', '),
  );
  return prog;
}

/**
 * En primer plano, un aviso vencido se dispara enseguida y se cancela su notificación programada:
 * Android usa alarmas inexactas para los disparadores de fecha (llegaban 10 s a 1 min tarde), y la
 * app abierta sí sabe la hora exacta. Devuelve true si lo disparó (una sola vez por aviso).
 */
export async function dispararSiVencio(tipo: AvisoProgramado['tipo'], ahora: number = Date.now()): Promise<boolean> {
  const prog = await leerProgramados();
  if (!prog) return false;
  const i = prog.avisos.findIndex((a) => a.tipo === tipo);
  if (i < 0 || !prog.ids[i] || Date.parse(prog.avisos[i].cuando) > ahora) return false;
  const aviso = prog.avisos[i];
  await Notifications.cancelScheduledNotificationAsync(prog.ids[i]).catch(() => undefined);
  prog.ids[i] = ''; // ya no queda programada
  await AsyncStorage.setItem(CLAVE_PROGRAMADOS, JSON.stringify(prog)).catch(() => undefined);
  // Si Android ya la mostró (p. ej. con la app en segundo plano), no se repite.
  try {
    const mostradas = await Notifications.getPresentedNotificationsAsync();
    const yaMostrada = mostradas.some((n) => {
      const d = n.request.content.data as { sesion_id?: string; tipo?: string } | undefined;
      return d?.sesion_id === prog.sesion_id && d?.tipo === tipo;
    });
    if (yaMostrada) return false;
  } catch {
    // sin la API (tests o plataforma): se sigue
  }
  await Notifications.scheduleNotificationAsync({
    content: { title: aviso.titulo, body: aviso.cuerpo, data: { sesion_id: prog.sesion_id, tipo: aviso.tipo } },
    trigger: null,
  });
  console.log(`[avisos] ${tipo} disparado en primer plano (programado para ${aviso.cuando})`);
  return true;
}

/** Avisos ya vencidos (para el banner dentro de la app, que en iPhone suple al segundo plano). */
export function avisosVencidos(prog: Programados | null, ahora: number = Date.now()): Programados['avisos'] {
  return (prog?.avisos ?? []).filter((a) => Date.parse(a.cuando) <= ahora);
}

// Registro de lo ya avisado por sesión, compartido con el modo espejo para no duplicar: la clave
// es tipo + sesion_id (los tipos del espejo se traducen a los de calcularAvisos).
const avisados = new Set<string>();
const TIPO_DEL_ESPEJO: Record<string, AvisoProgramado['tipo'] | undefined> = {
  saldo_bajo: 'saldo_bajo',
  tiempo_maximo_cerca: 'tiempo_maximo',
};

export function marcarAvisado(tipo: string, sesionId: string): void {
  avisados.add(`${tipo}|${sesionId}`);
  if (tipo === 'saldo_bajo_y_tiempo_maximo') {
    avisados.add(`saldo_bajo|${sesionId}`);
    avisados.add(`tiempo_maximo|${sesionId}`);
  }
}

/** true si el aviso (del espejo o de calcularAvisos) ya se avisó para esa sesión; lo marca. */
export function avisarUnaVez(tipoEspejoOPropio: string, sesionId: string): boolean {
  const tipo = TIPO_DEL_ESPEJO[tipoEspejoOPropio] ?? tipoEspejoOPropio;
  const clave = `${tipo}|${sesionId}`;
  if (avisados.has(clave)) return false;
  marcarAvisado(tipo, sesionId);
  return true;
}

/** Olvida lo avisado de una sesión (p. ej. "Reiniciar recorrido" en el espejo mock). */
export function olvidarSesion(sesionId: string): void {
  for (const clave of [...avisados]) if (clave.endsWith(`|${sesionId}`)) avisados.delete(clave);
}

/** Solo para tests. */
export function olvidarAvisados(): void {
  avisados.clear();
}
