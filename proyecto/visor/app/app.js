// App web de e-sert (2026-11-18): todo simulado y en línea.
//
// Cada navegador es un usuario `app_<uuid>` con $5 de prueba. Pone su ubicación simulada en el
// mapa y pulsa «Buscar parqueadero cercano»: el backend ordena crear un auto propio en SUMO, que va
// por la ruta real al puesto libre más cercano. La IA (RF sobre el GPS emulado) detecta cuándo
// estacionó y se bajó → la app pide el tiempo (30/60/90/120 min, se debita ya). A 5 min del final
// avisa; al llegar a 0 se renueva sola. «Me voy»: el conductor vuelve y la IA detecta la salida.
// «Ya estacioné»: con el código del puesto, el auto aparece ya estacionado ahí.
//
// Estado propio: GET /api/v1/web/usuarios/{id} cada segundo. Mundo (autos, peatones, ocupación
// real): WebSocket /ws/estado, como el visor.
import { crearMapa, CapaCalle, COLORES } from "../js/mapa_esert.js";

const params = new URLSearchParams(location.search);
const ORIGEN = (params.get("api") || location.origin).replace(/\/$/, "");
const API = ORIGEN + "/api/v1";
const WS = ORIGEN.replace(/^http/, "ws") + "/ws/estado";
const CLAVE_LS = "esert.usuarioWeb";
const CENTRO = [-2.8975, -79.0045];
const LIMITES = L.latLngBounds([-2.905, -79.013], [-2.8895, -78.9945]);
const PRECIO = { 30: "0,25", 60: "0,50", 90: "0,75", 120: "1,00" };

const $ = (id) => document.getElementById(id);
const hoja = $("hoja");

// --- Mapa ---------------------------------------------------------------------------------------
const mapa = crearMapa("mapa", { centro: CENTRO, zoom: 17, zoomControl: false, attributionControl: true });
const calle = new CapaCalle({ datos: "../datos/puestos_geo.json", alTocarPuesto: (p) => tocarPuesto(p) }).addTo(mapa);
calle.cargar();
const pin = L.marker(CENTRO, {
  draggable: true, icon: L.divIcon({ className: "", html: '<div class="pin-ubicacion"></div>', iconSize: [26, 26], iconAnchor: [13, 26] }),
}).addTo(mapa).bindTooltip("Tu ubicación simulada", { direction: "top", offset: [0, -24] });
const ruta = L.polyline([], { color: COLORES.propio, weight: 5, opacity: 0.9 }).addTo(mapa);
// Mi posición: el teléfono del conductor simulado (el peatón si camina, el auto si va dentro).
// Va en su propia capa, encima del lienzo de autos y puestos (los marcadores de Leaflet quedan debajo).
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
  return {
    fijar(latlon) { pos = latlon; el.hidden = !latlon; ubicar(); },
  };
})();
let posAuto = null;            // mi vehículo según el último snapshot del WebSocket
let enfoque = "vehiculo";      // a qué sigue el mapa: "vehiculo" | "posicion" | null (lo movió el usuario)
let ultimoEnfoque = "vehiculo";
mapa.on("dragstart", () => { enfoque = null; pintarBotonEnfoque(); });
// La hoja inferior cambia de alto según el paso: el mapa se achica o crece y Leaflet tiene que
// saberlo, si no centra mal (el auto o mi posición quedan debajo de la hoja).
try {
  new ResizeObserver(() => { mapa.invalidateSize({ pan: false }); centrar(); }).observe($("mapa"));
} catch { window.addEventListener("resize", () => mapa.invalidateSize()); }

// --- Estado ---------------------------------------------------------------------------------------
let usuario = leer();
let estado = null;
let vista = "inicio";          // inicio | codigo (antes de tener sesión)
let codigoElegido = "";
let error = "";
let ocupado = false;
let alertaVista = null;        // pagado_hasta ya avisado
let ultimoPinteo = "";

function leer() { try { return localStorage.getItem(CLAVE_LS); } catch { return null; } }
function guardar(v) { try { localStorage.setItem(CLAVE_LS, v); } catch { /* sin almacenamiento */ } }

async function api(ruta, opciones = {}) {
  const r = await fetch(API + ruta, {
    ...opciones, headers: { "Content-Type": "application/json", "X-Contrato-Version": "1" },
    body: opciones.cuerpo === undefined ? undefined : JSON.stringify(opciones.cuerpo),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((d.error && d.error.mensaje) || (d.detail && JSON.stringify(d.detail)) || `Error ${r.status}`);
  return d;
}

async function asegurarUsuario() {
  if (usuario) {
    try { estado = await api(`/web/usuarios/${usuario}`); return; } catch { usuario = null; }
  }
  const d = await api("/web/usuarios", { method: "POST" });
  usuario = d.usuario_id;
  guardar(usuario);
  estado = await api(`/web/usuarios/${usuario}`);
}

async function refrescar() {
  if (!usuario) return;
  try {
    estado = await api(`/web/usuarios/${usuario}`);
    pintar();
  } catch { /* se reintenta en el próximo ciclo */ }
}

async function accion(ruta, cuerpo) {
  if (ocupado) return;
  ocupado = true; error = ""; pintar(true);
  try {
    estado = await api(`/web/usuarios/${usuario}${ruta}`, { method: "POST", cuerpo });
    vista = "inicio";
  } catch (e) {
    error = e.message;
  } finally {
    ocupado = false; pintar(true);
  }
}

// --- Interacción en el mapa -------------------------------------------------------------------------
function sinSesionAbierta() {
  const s = estado && estado.sesion;
  return !s || s.estado === "cerrada";
}

mapa.on("click", (ev) => {
  if (!sinSesionAbierta() || vista === "codigo") return;
  if (!LIMITES.contains(ev.latlng)) { error = "Elige un punto dentro de la zona SERT del Centro Histórico."; pintar(true); return; }
  pin.setLatLng(ev.latlng); error = ""; pintar(true);
});
pin.on("dragend", () => {
  if (!LIMITES.contains(pin.getLatLng())) { pin.setLatLng(CENTRO); error = "La ubicación debe estar en la zona SERT."; pintar(true); }
});

function tocarPuesto(p) {
  // Solo dentro de «Ya estacioné»: en la pantalla inicial, tocar el mapa mueve la ubicación.
  if (!sinSesionAbierta() || vista !== "codigo") return;
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
const dinero = (v) => "$" + Number(v || 0).toFixed(2).replace(".", ",");

function pintar(forzar = false) {
  if (!estado) return;
  $("saldo").textContent = dinero(estado.saldo);
  $("aviso-sim").hidden = estado.sim_activa;
  $("aviso-sim").textContent = "La simulación está detenida: pídele a quien presenta que la inicie en el visor.";
  const s = estado.sesion;
  const abierta = s && s.estado !== "cerrada";
  // Sin sesión: el pin para elegir la ubicación simulada. Con sesión: el punto azul de mi posición.
  pin.setOpacity(abierta ? 0 : 1);
  pin.dragging[abierta ? "disable" : "enable"]();
  const auto = abierta && s.auto;
  yo.fijar(auto ? [auto.lat, auto.lon] : null);
  if (!abierta) posAuto = null;
  ruta.setLatLngs(auto && ["yendo"].includes(s.estado) ? auto.ruta : []);
  calle.resaltado = abierta && s.puesto ? s.puesto.puesto_id : (vista === "codigo" ? calle.resaltado : null);
  calle.redibujar();
  pintarBotonEnfoque();
  centrar();
  alertar(s);
  // La hoja solo se reescribe cuando cambia su estructura; los relojes se actualizan en su texto
  // (si se reescribiera cada segundo, un toque en un botón podría perderse).
  const html = contenido(s, abierta);
  if (forzar || html !== ultimoPinteo) {
    const enfoque = document.activeElement && document.activeElement.id === "codigo";
    if (!enfoque || forzar) { hoja.innerHTML = html; ultimoPinteo = html; enlazar(s); }
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
  const s = estado && estado.sesion;
  if (!s || s.estado === "cerrada" || !s.auto) return null;
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
  const s = estado && estado.sesion;
  b.hidden = !(s && s.estado !== "cerrada" && s.auto);
  // el botón ofrece lo otro: si sigo al vehículo, «Mi posición», y al revés
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

function contenido(s, abierta) {
  const err = error ? `<p class="error">${error}</p>` : "";
  const ia = (t) => `<p class="ia">🧠 ${t}</p>`;
  if (!abierta) {
    const fin = s && s.estado === "cerrada" ? recibo(s) : "";
    if (vista === "codigo") {
      return `${fin}<h2>Ya estacioné</h2>
        <p>Escribe el número del puesto pintado en la calle, o tócalo en el mapa.</p>
        <input id="codigo" class="codigo" inputmode="numeric" maxlength="3" placeholder="000" value="${codigoElegido}">
        ${err}
        <div class="fila-botones">
          <button id="b-volver" class="secundario" type="button">Volver</button>
          <button id="b-pagar" class="principal" type="button" ${ocupado ? "disabled" : ""}>Continuar</button>
        </div>`;
    }
    return `${fin}<h2>¿Qué necesitas?</h2>
      <p>Toca el mapa o arrastra el pin azul para poner <span class="dato">tu ubicación simulada</span>.</p>
      ${err}
      <div class="pila">
        <button id="b-buscar" class="principal" type="button" ${ocupado || !estado.sim_activa ? "disabled" : ""}>Buscar parqueadero cercano</button>
        <button id="b-codigo" class="secundario" type="button" ${!estado.sim_activa ? "disabled" : ""}>Ya estacioné · pagar con código</button>
      </div>`;
  }
  const puesto = s.puesto ? `puesto <span class="dato">${s.puesto.codigo}</span> · ${s.puesto.calle}` : "";
  if (s.estado === "pendiente") {
    return `<h2 class="puntos">Buscando el puesto libre más cercano</h2>
      <p>La simulación está creando tu auto en la calle.</p>${err}`;
  }
  if (s.estado === "yendo") {
    return `<h2>Vas al ${puesto}</h2>
      <p>Tu auto (amarillo) sigue la ruta real de la simulación. El puesto queda reservado para ti.</p>
      ${ia("La IA detectará cuando estaciones y te bajes del auto.")}${err}`;
  }
  if (s.estado === "llego") {
    const quedan = s.eleccion_restante_s != null ? `Si no eliges en <span id="d-eleccion"></span> min se cobran 30 min.` : "";
    return `<h2>Llegaste al ${puesto}</h2>
      <p>¿Cuánto tiempo te vas a quedar? Se debita de inmediato. ${quedan}</p>
      <div class="opciones">${s.opciones_min.map((m) =>
        `<button type="button" data-min="${m}" ${ocupado ? "disabled" : ""}><b>${m}</b><small>min · $${PRECIO[m]}</small></button>`).join("")}</div>
      ${err}`;
  }
  if (s.estado === "activa") {
    return `<h2>Estacionado en el ${puesto}</h2>
      <div id="d-reloj" class="reloj"></div>
      <div class="etiqueta">tiempo restante (tiempo de la simulación)</div>
      <div class="resumen">
        <div><small>Pagado</small><b>${s.pagado_min} min</b></div>
        <div><small>Debitado</small><b>${dinero(s.debitado)}</b></div>
      </div>
      ${s.mensaje ? `<p class="mensaje">${s.mensaje}</p>` : ""}
      ${s.alerta ? `<p class="error">${s.alerta}</p>` : ""}
      ${err}
      <div class="fila-botones">
        <button id="b-extender" class="principal" type="button" ${!s.puede_extender || ocupado ? "disabled" : ""}>+30 min · $0,25</button>
        <button id="b-irme" class="peligro" type="button" ${ocupado ? "disabled" : ""}>Me voy</button>
      </div>
      <p class="etiqueta">${s.puede_extender ? "Puedes extender hasta 120 min en total." : "Llegaste al máximo de 120 min."}</p>`;
  }
  if (s.estado === "volviendo") {
    return `<h2>Vuelves a tu auto</h2>
      <p>${s.mensaje || ""}</p>
      ${ia("Cuando arranques, la IA detectará que vas manejando y cerrará la sesión.")}`;
  }
  return `<h2>${s.estado}</h2>`;
}

function recibo(s) {
  return `<div class="mensaje" style="margin-bottom:12px">
      <b>${s.mensaje || "Sesión terminada."}</b><br>
      ${s.pagado_min ? `Pagaste ${s.pagado_min} min · ${dinero(s.debitado)}` : "Sin cobro."}
    </div>`;
}

function enlazar(s) {
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
      const propio = estado && estado.sesion && estado.sesion.estado !== "cerrada" ? estado.sesion.veh_id : null;
      calle.fijarVehiculos(m.vehiculos.map((v) => ({
        id: v.id, lat: v.lat, lon: v.lon,
        color: v.id === propio ? COLORES.propio : (COLORES[v.estado] || COLORES.null),
        borde: v.id === propio ? "#0f172a" : null, halo: v.id === propio,
      })));
      if (propio) {
        const mio = m.vehiculos.find((v) => v.id === propio);
        if (mio) posAuto = [mio.lat, mio.lon];
      }
      // peatones de la app (el propio va como punto azul que late, no se repite)
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
  hoja.innerHTML = '<h2 class="puntos">Preparando tu billetera de prueba</h2>';
  try {
    await asegurarUsuario();
  } catch (e) {
    hoja.innerHTML = `<h2>No hay conexión con el servidor</h2><p class="error">${e.message}</p>`;
    return;
  }
  const s = estado.sesion;
  if (s && s.estado !== "cerrada" && s.puesto) mapa.setView([s.puesto.lat, s.puesto.lon], 17);
  pintar(true);
  conectar();
  setInterval(refrescar, 1000);
})();
window.app = { mapa, calle, estado: () => estado };
