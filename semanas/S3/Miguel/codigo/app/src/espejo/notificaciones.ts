import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import type { EstadoSesion, MensajeEspejo } from '@/src/api/tipos';
import { avisarUnaVez, olvidarSesion } from '@/src/servicios/avisos';

// Notificaciones locales del modo espejo (en Expo Go no hay push remotas; las locales sí).

export const CANAL_ESPEJO = 'espejo';

export interface Aviso {
  titulo: string;
  cuerpo: string;
}

const usd = (v: number) => `$${v.toFixed(2)}`;

/** Texto de la notificación de cada transición clave; null si el estado no notifica. */
export function textoTransicion(m: MensajeEspejo): Aviso | null {
  switch (m.estado) {
    case 'GUIADO':
      return {
        titulo: 'Puesto asignado',
        cuerpo: m.puesto ? `Puesto asignado a ${Math.round(m.puesto.distancia_m)} m` : 'Puesto asignado',
      };
    case 'ESTACIONADO':
      return {
        titulo: 'Sesión iniciada',
        cuerpo: `Sesión iniciada, retenido ${usd(m.sesion?.retenido_usd ?? 0)}`,
      };
    case 'SALIENDO':
      return {
        titulo: 'Saliendo del puesto',
        cuerpo: `El auto está saliendo; costo hasta ahora ${usd(m.sesion?.costo_usd ?? 0)}`,
      };
    case 'CERRADA':
      return {
        titulo: 'Sesión cerrada',
        cuerpo: m.recibo
          ? `Cobrado ${usd(m.recibo.cobrado_usd)}, ahorraste ${usd(m.recibo.ahorro_usd)}`
          : `Cobrado ${usd(m.sesion?.costo_usd ?? 0)}`,
      };
    default:
      return null;
  }
}

const TEXTO_AVISO_ESPEJO: Partial<Record<string, (m: MensajeEspejo) => Aviso>> = {
  saldo_bajo: (m) => ({
    titulo: 'Saldo bajo',
    cuerpo: `Disponible ${usd(m.billetera?.disponible ?? 0)}: recarga para no quedarte sin saldo`,
  }),
  tiempo_maximo_cerca: () => ({ titulo: 'Tope SERT cerca', cuerpo: 'En pocos minutos llegas al máximo de tiempo en el puesto.' }),
  sesiones_bloqueadas: () => ({ titulo: 'Sesiones bloqueadas', cuerpo: 'Tu saldo es negativo: recarga para volver a parquear.' }),
};

const ESTADOS_QUE_NOTIFICAN: readonly EstadoSesion[] = ['GUIADO', 'ESTACIONADO', 'SALIENDO', 'CERRADA'];

/**
 * Decide qué notificar con cada mensaje: una sola vez por (veh_id, estado) y una vez por
 * (veh_id, saldo_bajo), aunque el estado se repita a 1 Hz o el socket se reconecte.
 */
export class NotificadorEspejo {
  private enviadas = new Set<string>();
  private sesiones = new Set<string>();

  constructor(private readonly enviar: (a: Aviso) => void = enviarLocal) {}

  procesar(m: MensajeEspejo): Aviso[] {
    const nuevos: Aviso[] = [];
    if (m.estado && ESTADOS_QUE_NOTIFICAN.includes(m.estado)) {
      const clave = `${m.veh_id}|${m.estado}`;
      const aviso = textoTransicion(m);
      if (aviso && !this.enviadas.has(clave)) {
        this.enviadas.add(clave);
        nuevos.push(aviso);
      }
    }
    // Avisos que trae el mensaje espejo (§7): mismo texto y sin duplicar los que ya programó
    // calcularAvisos para esa sesión (clave tipo + sesion_id, compartida con servicios/avisos).
    const sesionId = m.sesion?.sesion_id ?? m.veh_id;
    this.sesiones.add(sesionId);
    for (const aviso of m.avisos) {
      const texto = TEXTO_AVISO_ESPEJO[aviso];
      if (!texto || this.enviadas.has(`${aviso}|${sesionId}`)) continue;
      this.enviadas.add(`${aviso}|${sesionId}`);
      if (!avisarUnaVez(aviso, sesionId)) continue;
      nuevos.push(texto(m));
    }
    nuevos.forEach(this.enviar);
    return nuevos;
  }

  reiniciar(): void {
    this.enviadas.clear();
    this.sesiones.forEach(olvidarSesion);
    this.sesiones.clear();
  }
}

let preparado: Promise<boolean> | null = null;
let canalListo = false; // si Expo Go rechaza el canal, se usa el canal por defecto

/** Permisos, canal Android "espejo" (alta importancia) y mostrar en primer plano. Idempotente. */
export function prepararNotificaciones(): Promise<boolean> {
  preparado ??= (async () => {
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowBanner: true,
        shouldShowList: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
      }),
    });
    if (Platform.OS === 'android') {
      try {
        await Notifications.setNotificationChannelAsync(CANAL_ESPEJO, {
          name: 'Modo espejo',
          importance: Notifications.AndroidImportance.HIGH,
        });
        canalListo = true;
      } catch (e) {
        // Expo Go (SDK 58, Android) responde NullPointerException al crear el canal: sin canal
        // propio las notificaciones van al canal por defecto, y el permiso se pide igual.
        console.warn('[espejo] no se pudo crear el canal "espejo"; se usa el canal por defecto', e);
      }
    }
    const permiso = await Notifications.requestPermissionsAsync();
    console.log(`[espejo] permiso de notificaciones: ${permiso.status} (granted=${permiso.granted})`);
    return permiso.granted;
  })().catch((e) => {
    console.warn('[espejo] notificaciones no disponibles', e);
    return false;
  });
  return preparado;
}

function enviarLocal(a: Aviso): void {
  Notifications.scheduleNotificationAsync({
    content: { title: a.titulo, body: a.cuerpo },
    // Inmediata; en Android, en el canal del espejo.
    trigger: Platform.OS === 'android' && canalListo ? { channelId: CANAL_ESPEJO } : null,
  })
    .then((id) => console.log(`[espejo] notificación programada ${id}: ${a.titulo}`))
    .catch((e) => console.warn('[espejo] no se pudo notificar', e));
}
