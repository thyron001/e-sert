// MOCK: reemplazar por el backend real cuando Freddy entregue proyecto/backend/ (FastAPI).
// Responde con las mismas formas que docs/CONTRATO.md sección 4. Se activa en Ajustes.

import {
  ErrorApi,
  type ApiESert,
  type Billetera,
  type Movimiento,
  type Puesto,
  type Sesion,
  type TipoMovimiento,
  type UsuarioId,
} from './tipos';
import { TARIFA, costoMinutos, minutosCobrados, montoRetencion, redondearCentavos } from './tarifa';

export const LATENCIA_MS = 300;
const PARQUE_CALDERON = { lat: -2.8975, lon: -79.0045 };
const SALDO_INICIAL_USD = 5.0;

const esperar = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** uuid4 sin dependencias nativas (el mock tiene que poder correr fuera del teléfono). */
export function uuid4(aleatorio: () => number = Math.random): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.floor(aleatorio() * 16);
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/** Generador pseudoaleatorio con semilla (mulberry32): los 20 puestos salen siempre iguales. */
function mulberry32(semilla: number): () => number {
  let a = semilla;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function distanciaM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000;
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const a =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

// Calles tarifadas alrededor del Parque Calderón. Los edgeId son inventados (no son de la red de Tyrone).
const CALLES = [
  'Simón Bolívar',
  'Mariscal Sucre',
  'Gran Colombia',
  'Presidente Córdova',
  'Benigno Malo',
  'Luis Cordero',
  'Padre Aguirre',
  'Antonio Borrero',
];

export function generarPuestosFalsos(n = 20, semilla = 2026): Puesto[] {
  const azar = mulberry32(semilla);
  const puestos: Puesto[] = [];
  for (let i = 0; i < n; i++) {
    // Dentro de unos ±350 m del parque (1° de latitud ≈ 111 km).
    const lat = PARQUE_CALDERON.lat + (azar() - 0.5) * 0.0063;
    const lon = PARQUE_CALDERON.lon + (azar() - 0.5) * 0.0063;
    const capacidad = 3 + Math.floor(azar() * 6);
    // Más o menos un tercio de los puestos llenos, para que se vean los dos colores.
    const ocupados = azar() < 0.35 ? capacidad : Math.floor(azar() * capacidad);
    puestos.push({
      puesto_id: `pa_-${100200 + i * 37}#${i % 3}_0`,
      lat: Number(lat.toFixed(6)),
      lon: Number(lon.toFixed(6)),
      calle: CALLES[i % CALLES.length],
      capacidad,
      ocupados,
    });
  }
  return puestos;
}

/** Crea un backend falso en memoria que cumple la misma interfaz que el cliente HTTP. */
export function crearClienteMock(opciones: { latenciaMs?: number; ahora?: () => Date } = {}): ApiESert {
  const latencia = opciones.latenciaMs ?? LATENCIA_MS;
  const ahora = opciones.ahora ?? (() => new Date());
  const puestos = generarPuestosFalsos();
  const sesiones = new Map<string, Sesion>();
  const libros = new Map<UsuarioId, Movimiento[]>();

  function libro(usuarioId: UsuarioId): Movimiento[] {
    let movs = libros.get(usuarioId);
    if (!movs) {
      movs = [];
      libros.set(usuarioId, movs);
      anotar(usuarioId, 'recarga', SALDO_INICIAL_USD, { referencia_payphone: 'mock-saldo-inicial' });
    }
    return movs;
  }

  function anotar(
    usuarioId: UsuarioId,
    tipo: TipoMovimiento,
    monto: number,
    extra: Partial<Movimiento> = {},
  ): Movimiento {
    const mov: Movimiento = {
      movimiento_id: `mov_${uuid4()}`,
      tipo,
      monto: redondearCentavos(monto),
      ts: ahora().toISOString(),
      ...extra,
    };
    libros.get(usuarioId)!.push(mov);
    return mov;
  }

  // saldo = recargas − débitos; retenido = retenciones − liberaciones (CONTRATO §4).
  function estadoBilletera(usuarioId: UsuarioId): Billetera {
    const movs = libro(usuarioId);
    const suma = (t: TipoMovimiento) => movs.filter((m) => m.tipo === t).reduce((s, m) => s + m.monto, 0);
    const saldo = redondearCentavos(suma('recarga') - suma('debito'));
    const retenido = redondearCentavos(suma('retencion') - suma('liberacion'));
    return {
      saldo,
      retenido,
      disponible: redondearCentavos(saldo - retenido),
      bloqueada: saldo < 0,
      movimientos: [...movs],
    };
  }

  function buscarPuesto(puestoId: string): Puesto {
    const p = puestos.find((x) => x.puesto_id === puestoId);
    if (!p) throw new ErrorApi(404, 'PUESTO_NO_EXISTE', `No existe el puesto ${puestoId}`);
    return p;
  }

  function buscarSesion(sesionId: string): Sesion {
    const s = sesiones.get(sesionId);
    if (!s) throw new ErrorApi(404, 'SESION_NO_EXISTE', `No existe la sesión ${sesionId}`);
    return s;
  }

  // Simula la latencia de red y devuelve copias, como si vinieran por JSON.
  async function responder<T>(fn: () => T): Promise<T> {
    await esperar(latencia);
    const r = fn();
    return r === undefined ? r : (JSON.parse(JSON.stringify(r)) as T);
  }

  return {
    listarPuestos: () => responder(() => puestos),

    pedirGuia: (c) =>
      responder(() => {
        const libres = puestos.filter((p) => p.ocupados < p.capacidad);
        if (libres.length === 0) {
          throw new ErrorApi(404, 'SIN_PUESTOS_LIBRES', 'No hay puestos libres cerca del destino');
        }
        const conDistancia = libres.map((p) => ({
          p,
          d: distanciaM(c.destino_lat, c.destino_lon, p.lat, p.lon),
        }));
        conDistancia.sort((a, b) => a.d - b.d);
        const { p } = conDistancia[0];
        return {
          puesto_id: p.puesto_id,
          lat: p.lat,
          lon: p.lon,
          // Como el backend v1: distancia del puesto al destino, no desde el auto.
          distancia_m: Math.round(conDistancia[0].d),
        };
      }),

    enviarUbicacion: () => responder(() => undefined),
    enviarModo: () => responder(() => undefined),

    crearSesion: (datos) =>
      responder(() => {
        // Mismo orden de comprobaciones que el backend v1 de Freddy.
        const puesto = buscarPuesto(datos.puesto_id);
        const abierta = [...sesiones.values()].find(
          (x) => x.usuario_id === datos.usuario_id && x.estado !== 'CERRADA',
        );
        if (abierta) {
          throw new ErrorApi(409, 'SESION_ACTIVA', `Ya tienes una sesión abierta (${abierta.sesion_id})`);
        }
        const retener = montoRetencion();
        const billetera = estadoBilletera(datos.usuario_id);
        if (billetera.saldo < 0) {
          throw new ErrorApi(403, 'SESIONES_BLOQUEADAS', 'Hay saldo negativo: recarga antes de una nueva sesión');
        }
        if (billetera.disponible < retener) {
          throw new ErrorApi(
            402,
            'SALDO_INSUFICIENTE',
            `Necesitas $${retener.toFixed(2)} disponibles; recarga $${TARIFA.recarga_minima_usd.toFixed(2)} o más`,
          );
        }
        if (puesto.ocupados >= puesto.capacidad) {
          throw new ErrorApi(409, 'PUESTO_LLENO', `El puesto ${puesto.puesto_id} está lleno`);
        }
        const sesion: Sesion = {
          sesion_id: `ses_${uuid4()}`,
          usuario_id: datos.usuario_id,
          placa: datos.placa.toUpperCase(),
          puesto_id: puesto.puesto_id,
          estado: 'ESTACIONADO',
          inicio: datos.ts ?? ahora().toISOString(),
          fin: null,
          retenido: retener,
          minutos_reales: null,
          minutos_cobrados: null,
          debitado: null,
        };
        sesiones.set(sesion.sesion_id, sesion);
        puesto.ocupados += 1;
        anotar(datos.usuario_id, 'retencion', retener, { sesion_id: sesion.sesion_id });
        return { sesion_id: sesion.sesion_id, estado: 'ESTACIONADO' as const, retenido: retener };
      }),

    cerrarSesion: (sesionId, datos) =>
      responder(() => {
        const s = buscarSesion(sesionId);
        if (s.estado === 'CERRADA') {
          throw new ErrorApi(409, 'SESION_YA_CERRADA', `La sesión ${sesionId} ya está cerrada`);
        }
        const fin = new Date(datos.ts);
        const minutosReales = (fin.getTime() - new Date(s.inicio).getTime()) / 60000;
        if (minutosReales < 0) throw new ErrorApi(422, 'VALIDACION', 'El cierre es anterior al inicio');
        const cobrados = minutosCobrados(minutosReales);
        // CONTRATO §5 v1: el débito se aplica completo aunque el saldo quede negativo.
        const debitado = costoMinutos(cobrados);
        anotar(s.usuario_id, 'debito', debitado, { sesion_id: s.sesion_id });
        anotar(s.usuario_id, 'liberacion', s.retenido, { sesion_id: s.sesion_id });
        s.estado = 'CERRADA';
        s.fin = fin.toISOString();
        s.minutos_reales = redondearCentavos(minutosReales);
        s.minutos_cobrados = cobrados;
        s.debitado = debitado;
        const puesto = buscarPuesto(s.puesto_id);
        puesto.ocupados = Math.max(0, puesto.ocupados - 1);
        return {
          sesion_id: s.sesion_id,
          minutos_reales: redondearCentavos(minutosReales),
          minutos_cobrados: cobrados,
          debitado,
          saldo: estadoBilletera(s.usuario_id).saldo,
        };
      }),

    obtenerSesion: (sesionId) => responder(() => buscarSesion(sesionId)),

    obtenerBilletera: (usuarioId) => responder(() => estadoBilletera(usuarioId)),

    recargar: (usuarioId, datos) =>
      responder(() => {
        if (!(datos.monto >= TARIFA.recarga_minima_usd)) {
          throw new ErrorApi(
            422,
            'RECARGA_MINIMA',
            `La recarga mínima es $${TARIFA.recarga_minima_usd.toFixed(2)}`,
          );
        }
        libro(usuarioId);
        const mov = anotar(usuarioId, 'recarga', datos.monto, {
          referencia_payphone: datos.referencia_payphone,
        });
        return { movimiento_id: mov.movimiento_id, saldo: estadoBilletera(usuarioId).saldo };
      }),
  };
}
