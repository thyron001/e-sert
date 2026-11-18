// Visor e-sert (S3-3): mapa, conexión al WS /ws/estado y reparto de mensajes a los módulos.
// Parámetros de URL:
//   ?ws=ws://localhost:8000/ws/estado   otro servidor (por defecto, el WS del mismo origen)
//   ?verdad=1                           muestra los mensajes `verdad` (depuración)
//   ?ocupacion=sistema                  colorea los puestos con el mapa del sistema (solo usuarios con
//                                       app). Por defecto, con la ocupación real de SUMO (`verdad`)
//                                       cuando llega, y si no, con la del `snapshot`.
//   ?espejo=<veh_id>                    sigue además WS /ws/espejo/{veh_id}: ruta y puesto asignado
//   ?presentacion=1                     arranca en modo presentación
//   ?base=<url>                         base.json de la búsqueda a ciegas (por defecto ./datos/base.json)
import { estadisticaCuadros, siguienteEspera } from "./logica.js";
import { PanelKpis } from "./panel_kpis.js";
import { CapaEspejo } from "./capa_espejo.js";
import { Presentacion } from "./presentacion.js";
import { ControlDemo } from "./control_demo.js";

const params = new URLSearchParams(location.search);
const WS_URL = params.get("ws") ||
  (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/estado";
const VER_VERDAD = params.get("verdad") === "1";
const OCUPACION_REAL = params.get("ocupacion") !== "sistema";
const ORIGEN = WS_URL.replace(/^ws/, "http").replace(/\/ws\/estado.*$/, "");
const API_BASE = ORIGEN + "/api/v1";
const WS_BASE = WS_URL.replace(/\/ws\/estado.*$/, "");

export const COLOR_PUESTO = { libre: "#2E9E4F", lleno: "#C62828" };
export const COLOR_ESTADO = {
  BUSCANDO: "#FF9F1C", GUIADO: "#7B2CBF", ESTACIONADO: "#1E63D6", A_PIE: "#00A6A6",
  REGRESANDO: "#E040FB", SALIENDO: "#6D4C41", CERRADA: "#9E9E9E", null: "#8A96A3",
};
const COLOR_PEATON = "#111827";
const $ = (id) => document.getElementById(id);

// --- Mapa (canvas: miles de circleMarker sin DOM por marcador) -------------------------------
const lienzo = L.canvas({ padding: 0.3 });
const mapa = L.map("mapa", { preferCanvas: true, renderer: lienzo, zoomSnap: 0.25 }).setView([-2.8974, -79.0045], 16);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(mapa);
const capaPuestos = L.layerGroup().addTo(mapa);
const capaVehiculos = L.layerGroup().addTo(mapa);
const capaPeatones = L.layerGroup().addTo(mapa);

const puestos = new Map();
const vehiculos = new Map();
const peatones = new Map();

const panel = new PanelKpis($("tarjetas"), $("nota-base"), params.get("base") || "./datos/base.json");
const espejo = new CapaEspejo(mapa, { wsBase: WS_BASE, vehInicial: params.get("espejo") });
const presentacion = new Presentacion(mapa, { puestos, espejo, inicial: params.get("presentacion") === "1" });

function leyenda() {
  const filas = [
    ["Puesto con lugar", COLOR_PUESTO.libre, ""],
    [OCUPACION_REAL ? "Puesto lleno (ocupación real de SUMO)" : "Puesto lleno (mapa del sistema)", COLOR_PUESTO.lleno, ""],
    ["Auto sin app (color = estado)", "#ffffff", ""], ["Auto con app (borde negro)", "#ffffff", "app"],
    ["Buscando", COLOR_ESTADO.BUSCANDO, ""], ["Guiado por la app", COLOR_ESTADO.GUIADO, ""],
    ["Estacionado", COLOR_ESTADO.ESTACIONADO, ""], ["A pie / regresando", COLOR_ESTADO.A_PIE, ""],
    ["Sin búsqueda (paso)", COLOR_ESTADO.null, ""], ["Peatón", COLOR_PEATON, ""],
    ["Vehículo espejo", "#FFD60A", "halo"],
  ];
  $("leyenda").innerHTML = filas.map(([t, c, cl]) =>
    `<li><span class="punto ${cl}" style="background:${c}"></span>${t}</li>`).join("");
  $("ws-url").textContent = WS_URL;
}

// --- Puestos -----------------------------------------------------------------------------------
/** Ocupados que se muestran: los reales de SUMO (`verdad`) si llegaron, si no los del mapa del sistema. */
function ocupadosMostrados(p) {
  return OCUPACION_REAL && p.real !== undefined ? p.real : p.ocupados;
}

function contarLlenos() {
  let llenos = 0, total = 0;
  for (const p of puestos.values()) {
    if (p.capacidad === undefined) continue;
    total++;
    if (ocupadosMostrados(p) >= p.capacidad) llenos++;
  }
  $("n-llenos").textContent = `${llenos} / ${total}`;
}

function pintarPuesto(id) {
  const p = puestos.get(id);
  if (!p || !p.marcador) return;
  const color = ocupadosMostrados(p) < p.capacidad ? COLOR_PUESTO.libre : COLOR_PUESTO.lleno;
  if (p.color !== color) { p.marcador.setStyle({ color, fillColor: color }); p.color = color; }
}

async function cargarPuestos() {
  try {
    const r = await fetch(API_BASE + "/puestos", { headers: { "X-Contrato-Version": "1" } });
    if (!r.ok) throw new Error("HTTP " + r.status);
    for (const p of await r.json()) {
      const previo = puestos.get(p.puesto_id) || {};
      const dato = Object.assign(previo, {
        lat: p.lat, lon: p.lon, calle: p.calle, capacidad: p.capacidad,
        ocupados: previo.ocupados !== undefined ? previo.ocupados : p.ocupados,
      });
      if (!dato.marcador) {
        dato.marcador = L.circleMarker([p.lat, p.lon], { renderer: lienzo, radius: 5, weight: 1, fillOpacity: 0.85 })
          .bindPopup(() => {
            let t = `${dato.calle || p.puesto_id} · ${dato.ocupados}/${dato.capacidad}`;
            if (VER_VERDAD && dato.real !== undefined) t += ` (real ${dato.real})`;
            return t;
          }).addTo(capaPuestos);
      }
      puestos.set(p.puesto_id, dato);
      pintarPuesto(p.puesto_id);
    }
    espejo.puestos = puestos;
    presentacion.puestosCargados();
  } catch (err) {
    console.warn("No se pudieron cargar los puestos:", err);
    setTimeout(cargarPuestos, 5000);
  }
}

// --- Vehículos y peatones: se actualizan en sitio, sin recrear capas -------------------------
function actualizarMarcadores(mapaIds, capa, lista, estilo) {
  const vistos = new Set();
  for (const item of lista) {
    vistos.add(item.id);
    const op = estilo(item);
    const clave = op.color + op.fillColor + op.weight + op.radius;
    let m = mapaIds.get(item.id);
    if (!m) {
      m = L.circleMarker([item.lat, item.lon], Object.assign({ renderer: lienzo }, op)).addTo(capa);
      m._clave = clave;
      mapaIds.set(item.id, m);
    } else {
      m.setLatLng([item.lat, item.lon]);
      if (m._clave !== clave) { m.setStyle(op); m._clave = clave; }
    }
  }
  for (const [id, m] of mapaIds) if (!vistos.has(id)) { capa.removeLayer(m); mapaIds.delete(id); }
}

const proc = []; // ms de procesamiento por snapshot
function onSnapshot(msg) {
  const t0 = performance.now();
  actualizarMarcadores(vehiculos, capaVehiculos, msg.vehiculos, (v) => {
    const c = COLOR_ESTADO[v.estado] || COLOR_ESTADO.null;
    return { radius: v.con_app ? 5 : 3.5, color: v.con_app ? "#000000" : c, fillColor: c,
             weight: v.con_app ? 2.5 : 1, fillOpacity: 0.95 };
  });
  actualizarMarcadores(peatones, capaPeatones, msg.peatones || [], () => (
    { radius: 2, color: COLOR_PEATON, fillColor: COLOR_PEATON, weight: 0, fillOpacity: 0.9 }));
  for (const p of msg.puestos) {
    const dato = puestos.get(p.puesto_id) || {};
    dato.ocupados = p.ocupados; dato.capacidad = p.capacidad;
    puestos.set(p.puesto_id, dato);
    pintarPuesto(p.puesto_id);
  }
  espejo.onSnapshot(msg);
  panel.onSnapshot(msg);
  $("n-vehiculos").textContent = msg.vehiculos.length;
  $("n-buscando").textContent = msg.vehiculos.filter((v) => v.estado === "BUSCANDO" || v.estado === "GUIADO").length;
  $("n-app").textContent = msg.vehiculos.filter((v) => v.con_app).length;
  $("n-peatones").textContent = (msg.peatones || []).length;
  contarLlenos();
  window.visorUltimoSnapshot = msg.t_sim;
  window.visorVehiculos = msg.vehiculos.length;
  proc.push(performance.now() - t0);
  if (proc.length > 600) proc.shift();
}

function onVerdad(msg) {
  let difieren = 0;
  for (const p of msg.puestos) {
    const dato = puestos.get(p.puesto_id);
    if (!dato) continue;
    dato.real = p.ocupados;
    if (dato.capacidad === undefined) dato.capacidad = p.capacidad;
    if (dato.ocupados !== p.ocupados) difieren++;
    if (OCUPACION_REAL) pintarPuesto(p.puesto_id);
  }
  window.visorVerdadRecibida = (window.visorVerdadRecibida || 0) + 1;
  if (OCUPACION_REAL) { contarLlenos(); panel.onVerdad(msg); }
  if (!VER_VERDAD) return;
  $("verdad-texto").textContent = `${difieren} de ${msg.puestos.length} puestos difieren del mapa estimado · ` +
    `${msg.falsas_liberaciones.length} falsas liberaciones en este paso`;
}

function onMensaje(evento) {
  const msg = JSON.parse(evento.data);
  if (msg.tipo === "snapshot") onSnapshot(msg);
  else if (msg.tipo === "kpi") panel.onKpi(msg);
  else if (msg.tipo === "verdad") onVerdad(msg);
}

// --- Conexión con reconexión exponencial (1, 2, 4… hasta 30 s) --------------------------------
let espera = 1;
function estadoConexion(clase, texto) {
  const el = $("conexion");
  el.className = "estado " + clase;
  el.textContent = texto;
  window.visorConexion = clase;
}

function conectar() {
  estadoConexion("conectando", "conectando…");
  let ws;
  try { ws = new WebSocket(WS_URL); } catch (err) { reintentar(); return; }
  ws.onopen = () => {
    espera = 1; estadoConexion("conectado", "conectado");
    window.visorReconexiones = (window.visorReconexiones || 0) + 1;
    if (!puestos.size || ![...puestos.values()].some((p) => p.marcador)) cargarPuestos();
  };
  ws.onmessage = onMensaje;
  ws.onclose = reintentar;
  ws.onerror = () => ws.close();
}

function reintentar() {
  estadoConexion("desconectado", `sin conexión · reintento en ${espera} s`);
  setTimeout(conectar, espera * 1000);
  espera = siguienteEspera(espera, 30);
}

// --- Tiempo por cuadro (tecla D) ---------------------------------------------------------------
const cuadros = [];
let previo = performance.now();
function medir(ahora) {
  cuadros.push(ahora - previo);
  previo = ahora;
  if (cuadros.length > 600) cuadros.shift();
  espejo.cada_cuadro(ahora);
  panel.cada_cuadro(ahora);
  requestAnimationFrame(medir);
}
window.visorEstadisticaCuadros = () => ({ cuadro_ms: estadisticaCuadros(cuadros.slice(-300)),
                                          snapshot_ms: estadisticaCuadros(proc.slice(-300)) });
setInterval(() => {
  const el = $("depuracion");
  if (el.hidden) return;
  const e = window.visorEstadisticaCuadros();
  const f = (x) => (x === null ? "—" : x.toFixed(1));
  el.textContent = `cuadro (rAF)   media ${f(e.cuadro_ms.media)} ms · p95 ${f(e.cuadro_ms.p95)} ms · max ${f(e.cuadro_ms.max)} ms\n` +
    `snapshot (JS)  media ${f(e.snapshot_ms.media)} ms · p95 ${f(e.snapshot_ms.p95)} ms\n` +
    `vehículos ${window.visorVehiculos || 0} · meta < 33 ms por cuadro`;
}, 500);

document.addEventListener("keydown", (ev) => {
  if (ev.target && ["INPUT", "TEXTAREA", "SELECT"].includes(ev.target.tagName)) return;
  if (ev.key === "d" || ev.key === "D") $("depuracion").hidden = !$("depuracion").hidden;
});

if (VER_VERDAD) $("verdad").hidden = false;
leyenda();
const controlDemo = new ControlDemo(API_BASE, $("control-demo"));
cargarPuestos();
conectar();
requestAnimationFrame(medir);
window.visor = { mapa, puestos, vehiculos, espejo, panel, presentacion, controlDemo };
