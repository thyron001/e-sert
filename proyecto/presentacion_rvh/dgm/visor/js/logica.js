// Lógica pura del visor (sin DOM ni Leaflet): se prueba con `node --test visor/tests/*.test.mjs`.

/** Segundos de simulación → "hh:mm:ss". */
export function relojSim(tSim) {
  if (tSim === null || tSim === undefined || !Number.isFinite(tSim)) return "--:--:--";
  const s = Math.max(0, Math.floor(tSim));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const seg = s % 60;
  return [h, m, seg].map((x) => String(x).padStart(2, "0")).join(":");
}

/** Número con coma decimal (es-EC) y `dec` decimales; "—" si no es un número. */
export function numero(v, dec = 0) {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return v.toFixed(dec).replace(".", ",");
}

// Tarjetas del panel: clave interna → definición. `claves` son los nombres posibles en
// `kpi.valores` (contrato §6) o en el estado derivado del snapshot; `base` es la clave en base.json.
export const TARJETAS = [
  { id: "busqueda", titulo: "Búsqueda media", unidad: "s", dec: 0,
    claves: ["busqueda_media_s"], base: "busqueda_media_s", menorMejor: true },
  { id: "falsas", titulo: "Falsas liberaciones", unidad: "/100", dec: 1,
    claves: ["falsas_liberaciones_100", "falsas_lib_100"], base: "falsas_liberaciones_100", menorMejor: true },
  { id: "ocupacion", titulo: "Ocupación", unidad: "%", dec: 1, escala: 100,
    claves: ["ocupacion", "ocupacion_media_pico"], base: "ocupacion", menorMejor: null },
  { id: "co2", titulo: "CO₂ de búsqueda", unidad: "kg/h", dec: 1,
    claves: ["co2_busqueda_kg_h", "co2_busqueda_kg"], base: "co2_busqueda_kg_h", menorMejor: true },
  { id: "sesiones", titulo: "Sesiones activas", unidad: "", dec: 0,
    claves: ["sesiones_activas"], base: null, menorMejor: null },
];

/** Primer valor numérico de `valores` entre las claves de la tarjeta (o null). */
export function valorTarjeta(tarjeta, valores) {
  for (const k of tarjeta.claves) {
    const v = valores ? valores[k] : undefined;
    if (typeof v === "number" && Number.isFinite(v)) return v;
  }
  return null;
}

/** Texto de la tarjeta: "212 s", "45,0 %", "—". */
export function formatoTarjeta(tarjeta, valor) {
  if (valor === null || valor === undefined) return "—";
  const v = valor * (tarjeta.escala || 1);
  return (numero(v, tarjeta.dec) + (tarjeta.unidad ? " " + tarjeta.unidad : "")).trim();
}

/**
 * Cambio relativo frente a la búsqueda a ciegas: {pct, texto, mejor}.
 * texto "−38 % vs a ciegas" (signo menos tipográfico). null si falta algún valor o la base es 0.
 */
export function cambioVsBase(valor, base, menorMejor = true) {
  if (!Number.isFinite(valor) || !Number.isFinite(base) || base === 0) return null;
  const pct = (100 * (valor - base)) / Math.abs(base);
  const r = Math.round(pct);
  const signo = r < 0 ? "−" : r > 0 ? "+" : "±";
  const texto = `${signo}${Math.abs(r)} % vs a ciegas`;
  const mejor = menorMejor === null ? null : (menorMejor ? pct < 0 : pct > 0);
  return { pct, texto, mejor };
}

/** Sesiones activas derivadas del snapshot: autos con app en ESTACIONADO, A_PIE o REGRESANDO. */
export function sesionesActivas(snapshot) {
  const activos = new Set(["ESTACIONADO", "A_PIE", "REGRESANDO"]);
  return (snapshot.vehiculos || []).filter((v) => v.con_app && activos.has(v.estado)).length;
}

/** Ocupación estimada (fracción) de `snapshot.puestos`. */
export function ocupacionSnapshot(snapshot) {
  let o = 0, c = 0;
  for (const p of snapshot.puestos || []) { o += p.ocupados; c += p.capacidad; }
  return c ? o / c : null;
}

/** Serie con ventana deslizante de `ventanaS` segundos simulados (minigráficas: 10 min). */
export class Serie {
  constructor(ventanaS = 600) { this.ventanaS = ventanaS; this.t = []; this.v = []; }
  agregar(t, v) {
    if (!Number.isFinite(t) || v === null || v === undefined || !Number.isFinite(v)) return;
    if (this.t.length && t < this.t[this.t.length - 1]) { this.t = []; this.v = []; } // reinicio de la corrida
    if (this.t.length && t === this.t[this.t.length - 1]) { this.v[this.v.length - 1] = v; return; }
    this.t.push(t); this.v.push(v);
    while (this.t.length && this.t[0] < t - this.ventanaS) { this.t.shift(); this.v.shift(); }
  }
}

/** Limitador de redibujo: `debe(ahoraMs)` true como mucho una vez cada `1000/hz` ms y solo si hubo cambios. */
export class Limitador {
  constructor(hz = 2) { this.intervalo = 1000 / hz; this.ultimo = -Infinity; this.sucio = false; }
  marcar() { this.sucio = true; }
  debe(ahoraMs) {
    if (!this.sucio || ahoraMs - this.ultimo < this.intervalo) return false;
    this.ultimo = ahoraMs; this.sucio = false; return true;
  }
}

/** Espera de reconexión: 1, 2, 4, … hasta `tope` s. */
export function siguienteEspera(actual, tope = 30) {
  return Math.min(Math.max(1, actual) * 2, tope);
}

/**
 * Seguimiento de los vehículos espejo. `actualizar(espejos, tSegReal)` con la lista del
 * snapshot; un ID que sale de la lista (o recibe `espejo_fin`) se retira `retiroS` s después.
 * `visibles()` devuelve los IDs que deben dibujarse con halo.
 */
export class SeguimientoEspejos {
  constructor(retiroS = 5) { this.retiroS = retiroS; this.activos = new Map(); } // id → {retirarEn}
  actualizar(espejos, ahoraS) {
    const lista = new Set(espejos || []);
    for (const id of lista) this.activos.set(id, { retirarEn: null });
    for (const [id, e] of this.activos) {
      if (!lista.has(id) && e.retirarEn === null) e.retirarEn = ahoraS + this.retiroS;
    }
    return this.purgar(ahoraS);
  }
  fin(id, ahoraS) {
    const e = this.activos.get(id);
    if (e) e.retirarEn = Math.min(e.retirarEn ?? Infinity, ahoraS + this.retiroS);
  }
  agregar(id) { this.activos.set(id, { retirarEn: null }); }
  purgar(ahoraS) {
    const retirados = [];
    for (const [id, e] of this.activos) {
      if (e.retirarEn !== null && ahoraS >= e.retirarEn) { this.activos.delete(id); retirados.push(id); }
    }
    return retirados;
  }
  visibles() { return [...this.activos.keys()]; }
  retirando(id) { const e = this.activos.get(id); return !!(e && e.retirarEn !== null); }
}

/** ID del peatón de un vehículo (`sim_veh42` → `ped_veh42`), contrato §1/§6. */
export function peatonDe(vehId) {
  return "ped_" + String(vehId).replace(/^sim_/, "");
}

/**
 * Posición del objeto a resaltar: el vehículo si está en el snapshot; si no, su peatón
 * (el conductor se bajó); si tampoco, null.
 */
export function posicionEspejo(id, snapshot) {
  const v = (snapshot.vehiculos || []).find((x) => x.id === id);
  if (v) return { tipo: "vehiculo", lat: v.lat, lon: v.lon, estado: v.estado };
  const ped = peatonDe(id);
  const p = (snapshot.peatones || []).find((x) => x.id === ped);
  if (p) return { tipo: "peaton", lat: p.lat, lon: p.lon, estado: "A_PIE" };
  return null;
}

/** Rastro: puntos [lat, lon, tSim] de los últimos `ventanaS` segundos simulados. */
export function recortarRastro(rastro, tSim, ventanaS = 60) {
  return rastro.filter((p) => p[2] >= tSim - ventanaS);
}

/** Encuadre (sur, oeste, norte, este) de una lista de {lat, lon}. */
export function encuadre(puntos) {
  if (!puntos.length) return null;
  let s = Infinity, w = Infinity, n = -Infinity, e = -Infinity;
  for (const p of puntos) {
    s = Math.min(s, p.lat); n = Math.max(n, p.lat); w = Math.min(w, p.lon); e = Math.max(e, p.lon);
  }
  return [[s, w], [n, e]];
}

/** Estadística de tiempos por cuadro (ms): media, p95 y máximo. */
export function estadisticaCuadros(ms) {
  if (!ms.length) return { n: 0, media: null, p95: null, max: null };
  const o = [...ms].sort((a, b) => a - b);
  const media = o.reduce((a, b) => a + b, 0) / o.length;
  return { n: o.length, media, p95: o[Math.min(o.length - 1, Math.floor(0.95 * o.length))], max: o[o.length - 1] };
}
