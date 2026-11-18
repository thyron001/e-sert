// App web de e-sert (2026-11-18): todo simulado y en línea, con la estética de la app Expo anterior.
//
// Pestañas: Buscar (mapa y sesión), Historial, Billetera (Payphone), Probar IA (GPS real del teléfono
// clasificado por el RF) y Usuario (perfiles del equipo e invitados, $10 iniciales cada uno).
//
// Buscar: el usuario pone su ubicación simulada y pulsa «Buscar parqueadero cercano»; el backend
// ordena crear un auto propio en SUMO, que va por la ruta real al puesto libre más cercano. La IA
// (RF sobre el GPS emulado) detecta cuándo estacionó y se bajó → la app pide el tiempo (30/60/90/120
// min, se debita ya). A 5 min del final avisa; en 0 se renueva sola. «Me voy»: el conductor vuelve,
// la IA detecta la salida y la app vuelve a la pantalla inicial.
//
// Estado propio: GET /api/v1/web/usuarios/{id} cada segundo. Mundo: WebSocket /ws/estado.
import { crearMapa, CapaCalle, COLORES } from "../js/mapa_esert.js";
import { api, $, dinero, mostrarAviso } from "./comun.js";
import { pintarHistorial } from "./historial.js";
import { pintarBilletera } from "./billetera.js";
import { PruebaIA } from "./probar_ia.js";
import { pintarUsuarios, perfilGuardado } from "./usuario.js";

const params = new URLSearchParams(location.search);
const ORIGEN = (params.get("api") || location.origin).replace(/\/$/, "");
const WS = ORIGEN.replace(/^http/, "ws") + "/ws/estado";
const CENTRO = [-2.8975, -79.0045];
const LIMITES = L.latLngBounds([-2.905, -79.013], [-2.8895, -78.9945]);
const PRECIO = { 30: "0,25", 60: "0,50", 90: "0,75", 120: "1,00" };
const TITULOS = { buscar: "Buscar", historial: "Historial", billetera: "Billetera", ia: "Probar IA", usuario: "Usuario" };
const EN_PUESTO = ["llego", "activa", "volviendo"];   // con estos estados se muestra «mi posición»
const hoja = $("hoja");

// --- Usuario y pestañas ------------------------------------------------------------------------------
const app = {
  usuario: perfilGuardado(),
  estado: null,
  pestana: "buscar",
  cambiarUsuario(id) {
    this.usuario = id;
    this.estado = null;
    vista = "inicio"; error = ""; ultimoPinteo = ""; estadoPrevio = null;
    refrescar().then(() => abrir("buscar"));
  },
  abrir: (p) => abrir(p),
};
const ia = new PruebaIA($("t-ia"));

function abrir(p) {
  app.pestana = p;
  for (const b of document.querySelectorAll(".pestanas button")) b.classList.toggle("activa", b.dataset.pestana === p);
  for (const id of Object.keys(TITULOS)) $("t-" + id).hidden = id !== p;
  $("titulo").textContent = TITULOS[p];
  if (p === "buscar") { setTimeout(() => mapa.invalidateSize(), 50); pintar(true); }
  if (p === "historial") pintarHistorial($("t-historial"), app.usuario);
  if (p === "billetera") pintarBilletera($("t-billetera"), app.usuario);
  if (p === "usuario") pintarUsuarios($("t-usuario"), app);
  if (p === "ia") ia.mostrar(); else ia.ocultar();
}
for (const b of document.querySelectorAll(".pestanas button")) b.onclick = () => abrir(b.dataset.pestana);
$("chip-usuario").onclick = () => abrir("usuario");

// --- Mapa ---------------------------------------------------------------------------------------
const mapa = crearMapa("mapa", { centro: CENTRO, zoom: 17, zoomControl: false, attributionControl: true });
const calle = new CapaCalle({ datos: "../datos/puestos_geo.json", alTocarPuesto: (p) => tocarPuesto(p) }).addTo(mapa);
calle.cargar();
const pin = L.marker(CENTRO, {
  draggable: true, icon: L.divIcon({ className: "", html: '<div class="pin-ubicacion"></div>', iconSize: [26, 26], iconAnchor: [13, 26] }),
}).addTo(mapa).bindTooltip("Tu ubicación simulada", { direction: "top", offset: [0, -24] });
const ruta = L.polyline([], { color: COLORES.propio, weight: 5, opacity: 0.9 }).addTo(mapa);
// Mi posición (solo en el puesto): el teléfono del conductor, en una capa encima del lienzo.
const yo = (() => {
  const el = document.createElement("div");
  el.className = "punto-yo capa-yo";
  el.hidden = true;
  mapa.getContainer().appendChild(el);
  let pos = null;
  const ubicar = () => {
    if (!pos) return;
    const q = mapa.latLngToContainerPoint(pos);
    el.style.transform = `translate(${q.x - 9}px, ${q.y - 9}px)`;
  };
  mapa.on("move zoom resize", ubicar);
  return { fijar(latlon) { pos = latlon; el.hidden = !latlon; ubicar(); } };
})();
let posAuto = null;            // mi vehículo según el último snapshot del WebSocket
let enfoque = "vehiculo";      // a qué sigue el mapa: "vehiculo" | "posicion" | null (lo movió el usuario)
let ultimoEnfoque = "vehiculo";
mapa.on("dragstart", () => { enfoque = null; pintarBotonEnfoque(); });
try {
  new ResizeObserver(() => { mapa.invalidateSize({ pan: false }); centrar(); }).observe($("mapa"));
} catch { window.addEventListener("resize", () => mapa.invalidateSize()); }

// --- Estado de la pestaña Buscar -------------------------------------------------------------------
let vista = "inicio";          // inicio | codigo (antes de tener sesión)
let codigoElegido = "";
let error = "";
let ocupado = false;
let alertaVista = null;        // pagado_hasta ya avisado
let ultimoPinteo = "";
let estadoPrevio = null;       // para avisar al cerrar y volver a la pantalla inicial

async function refrescar() {
  if (!app.usuario) return;
  try {
    app.estado = await api(ORIGEN, `/web/usuarios/${app.usuario}`);
    avisarCierre(app.estado.sesion);
    pintarCabecera();
    if (app.pestana === "buscar") pintar();
  } catch { /* se reintenta en el próximo ciclo */ }
}

async function accion(ruta, cuerpo) {
  if (ocupado) return;
  ocupado = true; error = ""; pintar(true);
  try {
    app.estado = await api(ORIGEN, `/web/usuarios/${app.usuario}${ruta}`, { method: "POST", cuerpo });
    vista = "inicio";
  } catch (e) {
    error = e.message;
  } finally {
    ocupado = false; pintar(true); pintarCabecera();
  }
}

function pintarCabecera() {
  const e = app.estado;
  $("chip-usuario").textContent = e ? `${e.nombre.split(" ")[0]} · ${dinero(e.saldo)}` : "Elegir usuario";
}

/** Cuando la sesión termina (el auto se fue), aviso breve y de vuelta a la pantalla inicial. */
function avisarCierre(s) {
  const antes = estadoPrevio;
  estadoPrevio = s ? s.estado : null;
  if (!s || s.estado !== "cerrada" || !antes || antes === "cerrada") return;
  vista = "inicio"; enfoque = "vehiculo"; alertaVista = null;
  mostrarAviso(s.pagado_min ? `${s.mensaje || "Sesión terminada."} Pagaste ${s.pagado_min} min · ${dinero(s.debitado)}.`
    : (s.mensaje || "Sesión terminada."), s.motivo && s.motivo.startsWith("sin") ? "error" : "ok");
}

// --- Interacción en el mapa -------------------------------------------------------------------------
const abierta = () => { const s = app.estado && app.estado.sesion; return !!(s && s.estado !== "cerrada"); };

mapa.on("click", (ev) => {
  if (abierta() || vista === "codigo") return;
  if (!LIMITES.contains(ev.latlng)) { error = "Elige un punto dentro de la zona SERT del Centro Histórico."; pintar(true); return; }
  pin.setLatLng(ev.latlng); error = ""; pintar(true);
});
pin.on("dragend", () => {
  if (!LIMITES.contains(pin.getLatLng())) { pin.setLatLng(CENTRO); error = "La ubicación debe estar en la zona SERT."; pintar(true); }
});

function tocarPuesto(p) {
  // Solo dentro de «Ya estacioné»: en la pantalla inicial, tocar el mapa mueve la ubicación.
  if (abierta() || vista !== "codigo") return;
  codigoElegido = p.codigo;
  calle.resaltado = p.id;
  calle.redibujar();
  pintar(true);
}

// --- Pintado de la hoja inferior --------------------------------------------------------------------
const reloj = (s) => {
  s = Math.max(0, Math.round(s || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return (h ? `${h}:${String(m).padStart(2, "0")}` : `${m}`) + `:${String(x).padStart(2, "0")}`;
};

function pintar(forzar = false) {
  const e = app.estado;
  if (!e) return;
  $("aviso-sim").hidden = e.sim_activa;
  $("aviso-sim").textContent = "La simulación está detenida: pídele a quien presenta que la inicie en el visor.";
  const s = e.sesion;
  const hay = abierta();
  pin.setOpacity(hay ? 0 : 1);
  pin.dragging[hay ? "disable" : "enable"]();
  const auto = hay && s.auto;
  const enPuesto = hay && EN_PUESTO.includes(s.estado);
  // Buscando o yendo: como antes (el mapa sigue al auto). En el puesto: punto azul y botón.
  yo.fijar(enPuesto && auto ? [auto.lat, auto.lon] : null);
  if (!enPuesto && enfoque === "posicion") enfoque = "vehiculo";
  if (!hay) posAuto = null;
  ruta.setLatLngs(auto && s.estado === "yendo" ? auto.ruta : []);
  calle.resaltado = hay && s.puesto ? s.puesto.puesto_id : (vista === "codigo" ? calle.resaltado : null);
  calle.redibujar();
  pintarBotonEnfoque();
  centrar();
  alertar(s);
  const html = contenido(s, hay);
  if (forzar || html !== ultimoPinteo) {
    const escribiendo = document.activeElement && document.activeElement.id === "codigo";
    if (!escribiendo || forzar) { hoja.innerHTML = html; ultimoPinteo = html; enlazar(); }
  }
  dinamicos(s);
}

function dinamicos(s) {
  const r = $("d-reloj");
  if (r && s) { r.textContent = reloj(s.restante_s); r.classList.toggle("cerca", s.restante_s != null && s.restante_s <= 300); }
  const el = $("d-eleccion");
  if (el && s) el.textContent = reloj(s.eleccion_restante_s);
}

function puntoEnfoque() {
  const s = app.estado && app.estado.sesion;
  if (!abierta() || !s.auto) return null;
  if (enfoque === "posicion") return [s.auto.lat, s.auto.lon];
  if (enfoque === "vehiculo") return posAuto || [s.auto.lat, s.auto.lon];
  return null;
}

function centrar() {
  const p = puntoEnfoque();
  if (p) mapa.panTo(p, { animate: true, duration: 0.6 });
}

function pintarBotonEnfoque() {
  const b = $("b-enfoque");
  const s = app.estado && app.estado.sesion;
  b.hidden = !(abierta() && s.auto && EN_PUESTO.includes(s.estado));
  const siguiente = enfoque === "vehiculo" ? "posicion" : enfoque === "posicion" ? "vehiculo" : ultimoEnfoque;
  b.dataset.siguiente = siguiente;
  b.textContent = siguiente === "vehiculo" ? "🚗 Mi vehículo" : "📍 Mi posición";
}

$("b-enfoque").onclick = () => {
  enfoque = $("b-enfoque").dataset.siguiente || "vehiculo";
  ultimoEnfoque = enfoque === "vehiculo" ? "posicion" : "vehiculo";
  pintarBotonEnfoque();
  centrar();
};

/** Línea de progreso con el estado que da la IA en el controlador. */
function pasos(s) {
  const nombres = [["BUSCANDO", "Buscando"], ["GUIADO", "Guiado"], ["ESTACIONADO", "Estacionado"], ["A_PIE", "A pie"],
                   ["REGRESANDO", "Regresando"], ["SALIENDO", "Saliendo"]];
  const actual = (s.auto && s.auto.estado) || (s.estado === "pendiente" ? "BUSCANDO" : null);
  const i = nombres.findIndex(([k]) => k === actual);
  return `<div class="pasos">${nombres.map(([, n], j) =>
    `<div class="paso ${j < i ? "hecho" : j === i ? "actual" : ""}">${n}</div>`).join("")}</div>`;
}

function contenido(s, hay) {
  const err = error ? `<p class="error">${error}</p>` : "";
  const nota = (t) => `<p class="ia-nota">🧠 ${t}</p>`;
  if (!hay) {
    if (vista === "codigo") {
      return `<h2>Ya estacioné</h2>
        <p>Escribe el número del puesto pintado en la calle, o tócalo en el mapa.</p>
        <input id="codigo" class="codigo" inputmode="numeric" maxlength="3" placeholder="000" value="${codigoElegido}">
        ${err}
        <div class="fila-botones">
          <button id="b-volver" class="gris" type="button">Volver</button>
          <button id="b-pagar" class="rojo" type="button" ${ocupado ? "disabled" : ""}>Continuar</button>
        </div>`;
    }
    return `<h2>Parquear en el Centro</h2>
      <p>Toca el mapa o arrastra el pin para poner <span class="dato">tu ubicación simulada</span>.
         La app te lleva al puesto SERT libre más cercano.</p>
      ${err}
      <div class="pila">
        <button id="b-buscar" class="rojo" type="button" ${ocupado || !app.estado.sim_activa ? "disabled" : ""}>Buscar parqueadero cercano</button>
        <button id="b-codigo" class="azul" type="button" ${!app.estado.sim_activa ? "disabled" : ""}>🅿️ Ya estacioné · pagar con código</button>
      </div>`;
  }
  const puesto = s.puesto ? `puesto <span class="dato">${s.puesto.codigo}</span> · ${s.puesto.calle}` : "";
  if (s.estado === "pendiente") {
    return `<h2 class="puntos">Buscando puesto</h2>${pasos(s)}
      <p>La simulación está creando tu auto en la calle.</p>${err}`;
  }
  if (s.estado === "yendo") {
    return `<h2>Guiado</h2>${pasos(s)}
      <p>Vas al ${puesto}. Tu auto (amarillo) sigue la ruta real de la simulación; el puesto queda reservado.</p>
      ${nota("La IA detectará cuando estaciones y te bajes del auto.")}${err}`;
  }
  if (s.estado === "llego") {
    const quedan = s.eleccion_restante_s != null ? `Si no eliges en <span id="d-eleccion"></span> min se cobran 30 min.` : "";
    return `<h2>Llegaste</h2>${pasos(s)}
      <p>Estás en el ${puesto}. ¿Cuánto tiempo te vas a quedar? Se debita de inmediato. ${quedan}</p>
      <div class="opciones">${s.opciones_min.map((m) =>
        `<button type="button" data-min="${m}" ${ocupado ? "disabled" : ""}><b>${m}</b><small>min · $${PRECIO[m]}</small></button>`).join("")}</div>
      ${err}`;
  }
  if (s.estado === "activa") {
    return `<h2>Sesión activa</h2>${pasos(s)}
      <p class="centro">${puesto}</p>
      <div id="d-reloj" class="reloj"></div>
      <div class="tarjeta">
        <div class="fila"><span class="etq">Pagado</span><span class="v">${s.pagado_min} min</span></div>
        <div class="fila"><span class="etq">Debitado</span><span class="v neg">${dinero(s.debitado)}</span></div>
        <div class="fila"><span class="etq">Saldo</span><span class="v">${dinero(app.estado.saldo)}</span></div>
      </div>
      ${s.mensaje ? `<p class="mensaje">${s.mensaje}</p>` : ""}
      ${s.alerta ? `<p class="error">${s.alerta}</p>` : ""}
      ${err}
      <div class="fila-botones">
        <button id="b-extender" class="azul" type="button" ${!s.puede_extender || ocupado ? "disabled" : ""}>+30 min · $0,25</button>
        <button id="b-irme" class="rojo" type="button" ${ocupado ? "disabled" : ""}>Ya me voy</button>
      </div>
      <p class="etq centro">${s.puede_extender ? "Puedes extender hasta 120 min en total." : "Llegaste al máximo de 120 min."}</p>`;
  }
  if (s.estado === "volviendo") {
    return `<h2>Regresando</h2>${pasos(s)}
      <p>${s.mensaje || "Vuelves a tu auto…"}</p>
      ${nota("Cuando arranques, la IA detectará que vas manejando y cerrará la sesión.")}`;
  }
  return `<h2>${s.estado}</h2>`;
}

function enlazar() {
  const b = (id, fn) => { const el = $(id); if (el) el.onclick = fn; };
  b("b-buscar", () => {
    const { lat, lng } = pin.getLatLng();
    enfoque = "vehiculo";
    accion("/buscar", { lat, lon: lng });
  });
  b("b-codigo", () => { vista = "codigo"; codigoElegido = ""; error = ""; pintar(true); });
  b("b-volver", () => { vista = "inicio"; error = ""; calle.resaltado = null; pintar(true); });
  b("b-pagar", () => {
    const codigo = ($("codigo").value || "").trim();
    if (!/^\d{1,3}$/.test(codigo)) { error = "Escribe el número del puesto (1 a 3 cifras)."; pintar(true); return; }
    enfoque = "vehiculo";
    accion("/estacionado", { codigo });
  });
  b("b-extender", () => accion("/extender", { minutos: 30 }));
  b("b-irme", () => accion("/me-voy"));
  for (const el of hoja.querySelectorAll("[data-min]")) {
    el.onclick = () => { pedirNotificaciones(); accion("/tiempo", { minutos: Number(el.dataset.min) }); };
  }
  const entrada = $("codigo");
  if (entrada) entrada.oninput = () => { codigoElegido = entrada.value.replace(/\D/g, "").slice(0, 3); entrada.value = codigoElegido; };
}

// --- Alerta de los 5 minutos ---------------------------------------------------------------------
function pedirNotificaciones() {
  try { if ("Notification" in window && Notification.permission === "default") Notification.requestPermission(); } catch { /* */ }
}

function alertar(s) {
  if (!s || s.estado !== "activa" || !s.alerta || alertaVista === s.pagado_hasta) return;
  alertaVista = s.pagado_hasta;
  $("alerta-texto").textContent = s.alerta;
  $("alerta-extender").hidden = !s.puede_extender;
  $("alerta").hidden = false;
  try { navigator.vibrate && navigator.vibrate([300, 150, 300]); } catch { /* */ }
  try {
    if ("Notification" in window && Notification.permission === "granted" && document.hidden) {
      new Notification("e-sert · tu tiempo se acaba", { body: s.alerta });
    }
  } catch { /* */ }
}
$("alerta-cerrar").onclick = () => { $("alerta").hidden = true; };
$("alerta-extender").onclick = () => { $("alerta").hidden = true; accion("/extender", { minutos: 30 }); };

// --- Mundo en vivo (WebSocket del visor) -------------------------------------------------------------
let espera = 1;
function conectar() {
  let ws;
  try { ws = new WebSocket(WS); } catch { setTimeout(conectar, 3000); return; }
  ws.onopen = () => { espera = 1; };
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.tipo === "snapshot") {
      const propio = abierta() ? app.estado.sesion.veh_id : null;
      calle.fijarVehiculos(m.vehiculos.map((v) => ({
        id: v.id, lat: v.lat, lon: v.lon,
        color: v.id === propio ? COLORES.propio : (COLORES[v.estado] || COLORES.null),
        borde: v.id === propio ? "#0f172a" : null, halo: v.id === propio,
      })));
      if (propio) {
        const mio = m.vehiculos.find((v) => v.id === propio);
        if (mio) posAuto = [mio.lat, mio.lon];
      }
      const miPeaton = propio ? "ped_" + propio.slice(4) : null;
      calle.fijarPeatones((m.peatones || []).filter((p) => p.id !== miPeaton));
    } else if (m.tipo === "verdad") {
      calle.fijarOcupacion(m.puestos);
    }
  };
  ws.onclose = () => { setTimeout(conectar, espera * 1000); espera = Math.min(espera * 2, 30); };
  ws.onerror = () => ws.close();
}

// --- Arranque -------------------------------------------------------------------------------------
(async () => {
  conectar();
  setInterval(refrescar, 1000);
  // vuelta desde Payphone: #billetera?clientTransactionId=…&estado=…
  if (location.hash.startsWith("#billetera")) { abrir("billetera"); if (app.usuario) await refrescar(); return; }
  if (!app.usuario) { abrir("usuario"); return; }
  await refrescar();
  const s = app.estado && app.estado.sesion;
  if (s && s.estado !== "cerrada" && s.puesto) mapa.setView([s.puesto.lat, s.puesto.lon], 17);
  abrir("buscar");
})();
window.app = { mapa, calle, estado: () => app.estado, abrir, cambiarUsuario: (id) => app.cambiarUsuario(id) };
export { ORIGEN };
