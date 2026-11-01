// Grabador de sensores para las grabaciones caseras opcionales (validación extra del clasificador).
// GPS a ~1 Hz y acelerómetro a 10 Hz; se vuelca a disco cada 30 s para no perder datos.
// En iPhone, Expo Go no graba en segundo plano: la pantalla tiene que quedar abierta.

import { activateKeepAwakeAsync, deactivateKeepAwake } from 'expo-keep-awake';
import * as Location from 'expo-location';
import * as SecureStore from 'expo-secure-store';
import { Accelerometer } from 'expo-sensors';

import {
  archivosDe,
  encabezadoAcel,
  encabezadoGPS,
  filaAcel,
  filaGPS,
  limpiarPrecision,
  limpiarVelocidad,
  nombreBase,
  usuarioCasa,
  type ArchivosGrabacion,
  type ContextoGrabacion,
  type Etiqueta,
  type MuestraAcel,
  type MuestraGPS,
  type Persona,
  type Telefono,
} from './exportar';

const VOLCADO_MS = 30_000;
const ACEL_INTERVALO_MS = 100;
const ETIQUETA_KEEP_AWAKE = 'grabador';
// Algunos teléfonos entregan dos lecturas casi juntas: se descartan las que llegan a < 0,5 s.
const SEPARACION_MIN_S = 0.5;

export interface CambioEtiqueta {
  t: number; // segundos Unix UTC del instante del cambio
  etiqueta: Etiqueta;
}

export interface EstadoGrabacion {
  grabando: boolean;
  base: string;
  usuario_id: string;
  inicio: number; // segundos Unix
  etiqueta: Etiqueta;
  muestrasGPS: number;
  muestrasAcel: number;
  acelerometro: boolean;
  precisionActual: number | null;
  velocidadActual: number | null;
  cambios: CambioEtiqueta[];
}

async function siguienteNumero(persona: Persona): Promise<number> {
  const clave = `esert_grabacion_n_${persona.toLowerCase()}`;
  let n = 1;
  try {
    n = Number((await SecureStore.getItemAsync(clave)) ?? '0') + 1;
    await SecureStore.setItemAsync(clave, String(n));
  } catch {
    n = Math.floor(Date.now() / 1000);
  }
  return n;
}

export class Grabador {
  private ctx!: ContextoGrabacion;
  private archivos!: ArchivosGrabacion;
  private pendientesGPS: string[] = [];
  private pendientesAcel: string[] = [];
  private subGPS: Location.LocationSubscription | null = null;
  private subAcel: { remove(): void } | null = null;
  private temporizador: ReturnType<typeof setInterval> | null = null;
  private ultimoT = 0;
  private volcando: Promise<void> = Promise.resolve();
  estado: EstadoGrabacion | null = null;

  constructor(private readonly alCambiar: (estado: EstadoGrabacion) => void) {}

  async iniciar(persona: Persona, telefono: Telefono, etiqueta: Etiqueta): Promise<void> {
    if (this.estado?.grabando) return;

    const permiso = await Location.requestForegroundPermissionsAsync();
    if (permiso.status !== 'granted') {
      throw new Error('Sin permiso de ubicación: actívalo en los ajustes del teléfono');
    }

    const ahora = new Date();
    const base = nombreBase(ahora, persona, telefono);
    this.ctx = { usuario_id: usuarioCasa(persona, await siguienteNumero(persona)), persona, telefono };
    this.archivos = archivosDe(base);
    this.archivos.gps.writeSync(encabezadoGPS());
    this.archivos.acel.writeSync(encabezadoAcel());
    this.pendientesGPS = [];
    this.pendientesAcel = [];
    this.ultimoT = 0;

    const t0 = ahora.getTime() / 1000;
    this.estado = {
      grabando: true,
      base,
      usuario_id: this.ctx.usuario_id,
      inicio: t0,
      etiqueta,
      muestrasGPS: 0,
      muestrasAcel: 0,
      acelerometro: false,
      precisionActual: null,
      velocidadActual: null,
      cambios: [{ t: t0, etiqueta }],
    };
    this.escribirMeta();

    await activateKeepAwakeAsync(ETIQUETA_KEEP_AWAKE);

    this.subGPS = await Location.watchPositionAsync(
      { accuracy: Location.Accuracy.BestForNavigation, timeInterval: 1000, distanceInterval: 0 },
      (pos) => this.alRecibirGPS(pos),
    );

    if (await Accelerometer.isAvailableAsync()) {
      Accelerometer.setUpdateInterval(ACEL_INTERVALO_MS);
      this.subAcel = Accelerometer.addListener(({ x, y, z }) => this.alRecibirAcel({ t: Date.now() / 1000, ax: x, ay: y, az: z }));
      this.estado.acelerometro = true;
    }

    this.temporizador = setInterval(() => this.volcar(), VOLCADO_MS);
    this.avisar();
  }

  /** Cambio de etiqueta en caliente: las muestras siguientes llevan la etiqueta nueva. */
  cambiarEtiqueta(etiqueta: Etiqueta): void {
    if (!this.estado?.grabando || this.estado.etiqueta === etiqueta) return;
    this.estado.etiqueta = etiqueta;
    this.estado.cambios.push({ t: Date.now() / 1000, etiqueta });
    this.escribirMeta();
    this.avisar();
  }

  async detener(): Promise<ArchivosGrabacion | null> {
    if (!this.estado?.grabando) return null;
    this.subGPS?.remove();
    this.subAcel?.remove();
    this.subGPS = null;
    this.subAcel = null;
    if (this.temporizador) clearInterval(this.temporizador);
    this.temporizador = null;
    await this.volcar();
    this.estado.grabando = false;
    this.escribirMeta(Date.now() / 1000);
    deactivateKeepAwake(ETIQUETA_KEEP_AWAKE);
    this.avisar();
    return this.archivos;
  }

  private alRecibirGPS(pos: Location.LocationObject): void {
    const e = this.estado;
    if (!e?.grabando) return;
    const t = pos.timestamp / 1000;
    if (t - this.ultimoT < SEPARACION_MIN_S) return;
    this.ultimoT = t;
    const muestra: MuestraGPS = {
      t,
      lat: pos.coords.latitude,
      lon: pos.coords.longitude,
      precision_m: limpiarPrecision(pos.coords.accuracy),
      velocidad_mps: limpiarVelocidad(pos.coords.speed),
      etiqueta: e.etiqueta,
    };
    this.pendientesGPS.push(filaGPS(muestra, this.ctx));
    e.muestrasGPS += 1;
    e.precisionActual = muestra.precision_m;
    e.velocidadActual = muestra.velocidad_mps;
    this.avisar();
  }

  private alRecibirAcel(m: MuestraAcel): void {
    if (!this.estado?.grabando) return;
    this.pendientesAcel.push(filaAcel(m));
    this.estado.muestrasAcel += 1;
  }

  /** Añade al final de los archivos lo que está en memoria. Encadenado para no solaparse. */
  private volcar(): Promise<void> {
    this.volcando = this.volcando.then(async () => {
      const gps = this.pendientesGPS.splice(0);
      const acel = this.pendientesAcel.splice(0);
      if (gps.length) await this.archivos.gps.write(gps.join('\n') + '\n', { append: true });
      if (acel.length) await this.archivos.acel.write(acel.join('\n') + '\n', { append: true });
    });
    return this.volcando;
  }

  private escribirMeta(fin: number | null = null): void {
    const e = this.estado!;
    this.archivos.meta.writeSync(
      JSON.stringify(
        { ...this.ctx, base: e.base, inicio: e.inicio, fin, cambios: e.cambios, acelerometro: e.acelerometro },
        null,
        2,
      ),
    );
  }

  private avisar(): void {
    if (this.estado) this.alCambiar({ ...this.estado, cambios: [...this.estado.cambios] });
  }
}
