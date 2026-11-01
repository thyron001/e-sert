// Visor e-sert: autos, peatones y puestos en vivo desde /ws/estado (CONTRATO §6).
// Sin build: Leaflet 1.9 desde CDN y este archivo. Parámetros de URL:
//   ?ws=ws://localhost:8000/ws/estado   otro servidor (por defecto, el WS del mismo origen)
//   ?verdad=1                           muestra los mensajes `verdad` (depuración)
(function () {
  "use strict";

  const params = new URLSearchParams(location.search);
  const WS_URL = params.get("ws") ||
    (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/estado";
  const VER_VERDAD = params.get("verdad") === "1";
  // La API REST vive en el mismo servidor que el WS
  const API_BASE = WS_URL.replace(/^ws/, "http").replace(/\/ws\/estado.*$/, "") + "/api/v1";

  const COLOR_PUESTO = { libre: "#2E9E4F", lleno: "#C62828" };
  const COLOR_ESTADO = {
    BUSCANDO: "#FF9F1C",
    GUIADO: "#7B2CBF",
    ESTACIONADO: "#1E63D6",
    A_PIE: "#00A6A6",
    REGRESANDO: "#E040FB",
    SALIENDO: "#6D4C41",
    CERRADA: "#9E9E9E",
    null: "#8A96A3", // sin búsqueda ni app (tráfico de paso)
  };
  const COLOR_PEATON = "#111827";
  const COLOR_ESPEJO = "#FFD60A";

  // --- Mapa -----------------------------------------------------------------------------
  const lienzo = L.canvas({ padding: 0.3 });
  const mapa = L.map("mapa", { preferCanvas: true, renderer: lienzo })
    .setView([-2.8974, -79.0045], 16);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(mapa);
  const capaPuestos = L.layerGroup().addTo(mapa);
  const capaVehiculos = L.layerGroup().addTo(mapa);
  const capaPeatones = L.layerGroup().addTo(mapa);
  const capaEspejos = L.layerGroup().addTo(mapa);

  const puestos = new Map(); // puesto_id -> {marcador, calle, capacidad, ocupados, real}
  const vehiculos = new Map(); // id -> marcador
  const peatones = new Map();
  const halos = new Map();

  const $ = (id) => document.getElementById(id);

  function leyenda() {
    const filas = [
      ["Puesto con lugar", COLOR_PUESTO.libre], ["Puesto lleno", COLOR_PUESTO.lleno],
      ...Object.entries(COLOR_ESTADO).map(([k, c]) => [k === "null" ? "Sin búsqueda" : k, c]),
      ["Peatón", COLOR_PEATON], ["Seguido por un espejo", COLOR_ESPEJO],
    ];
    $("leyenda").innerHTML = filas.map(([t, c]) =>
      `<li><span class="punto" style="background:${c}"></span>${t}</li>`).join("");
    $("ws-url").textContent = WS_URL;
  }

  // --- Puestos ---------------------------------------------------------------------------
  function popupPuesto(id) {
    const p = puestos.get(id);
    let texto = `${p.calle || id} · ${p.ocupados}/${p.capacidad}`;
    if (VER_VERDAD && p.real !== undefined) texto += ` (real ${p.real})`;
    return texto;
  }

  function pintarPuesto(id) {
    const p = puestos.get(id);
    if (!p || !p.marcador) return;
    const color = p.ocupados < p.capacidad ? COLOR_PUESTO.libre : COLOR_PUESTO.lleno;
    if (p.color !== color) {
      p.marcador.setStyle({ color: color, fillColor: color });
      p.color = color;
    }
  }

  async function cargarPuestos() {
    try {
      const r = await fetch(API_BASE + "/puestos", { headers: { "X-Contrato-Version": "1" } });
      if (!r.ok) throw new Error("HTTP " + r.status);
      for (const p of await r.json()) {
        const previo = puestos.get(p.puesto_id) || {};
        const dato = Object.assign(previo, {
          calle: p.calle, capacidad: p.capacidad,
          ocupados: previo.ocupados !== undefined ? previo.ocupados : p.ocupados,
        });
        dato.marcador = L.circleMarker([p.lat, p.lon], {
          renderer: lienzo, radius: 5, weight: 1, fillOpacity: 0.85,
        }).bindPopup(() => popupPuesto(p.puesto_id)).addTo(capaPuestos);
        puestos.set(p.puesto_id, dato);
        pintarPuesto(p.puesto_id);
      }
    } catch (err) {
      console.warn("No se pudieron cargar los puestos:", err);
      setTimeout(cargarPuestos, 5000);
    }
  }

  // --- Mensajes ----------------------------------------------------------------------------
  function actualizarMarcadores(mapaIds, capa, lista, estilo) {
    const vistos = new Set();
    for (const item of lista) {
      vistos.add(item.id);
      const opciones = estilo(item);
      let m = mapaIds.get(item.id);
      if (!m) {
        m = L.circleMarker([item.lat, item.lon], Object.assign({ renderer: lienzo }, opciones))
          .addTo(capa);
        m._clave = opciones.color + opciones.fillColor + opciones.weight;
        mapaIds.set(item.id, m);
      } else {
        m.setLatLng([item.lat, item.lon]);
        const clave = opciones.color + opciones.fillColor + opciones.weight;
        if (m._clave !== clave) { m.setStyle(opciones); m._clave = clave; }
      }
    }
    for (const [id, m] of mapaIds) {
      if (!vistos.has(id)) { capa.removeLayer(m); mapaIds.delete(id); }
    }
  }

  function onSnapshot(msg) {
    actualizarMarcadores(vehiculos, capaVehiculos, msg.vehiculos, (v) => {
      const c = COLOR_ESTADO[v.estado] || COLOR_ESTADO.null;
      return { radius: v.con_app ? 5 : 3.5, color: v.con_app ? "#000000" : c, fillColor: c,
               weight: v.con_app ? 3 : 1, fillOpacity: 0.95 };
    });
    actualizarMarcadores(peatones, capaPeatones, msg.peatones || [], () => (
      { radius: 2, color: COLOR_PEATON, fillColor: COLOR_PEATON, weight: 0, fillOpacity: 0.9 }));
    const espejos = new Set(msg.espejos || []);
    const conEspejo = msg.vehiculos.filter((v) => espejos.has(v.id));
    actualizarMarcadores(halos, capaEspejos, conEspejo, () => (
      { radius: 12, color: COLOR_ESPEJO, fillColor: COLOR_ESPEJO, weight: 3, fillOpacity: 0.25 }));

    let llenos = 0, ocupados = 0, capacidad = 0;
    for (const p of msg.puestos) {
      const dato = puestos.get(p.puesto_id) || {};
      dato.ocupados = p.ocupados;
      dato.capacidad = p.capacidad;
      puestos.set(p.puesto_id, dato);
      pintarPuesto(p.puesto_id);
      if (p.ocupados >= p.capacidad) llenos++;
      ocupados += p.ocupados;
      capacidad += p.capacidad;
    }
    const cuenta = (e) => msg.vehiculos.filter((v) => v.estado === e).length;
    $("t-sim").textContent = msg.t_sim.toFixed(0) + " s";
    $("n-vehiculos").textContent = msg.vehiculos.length;
    $("n-buscando").textContent = cuenta("BUSCANDO") + cuenta("GUIADO");
    $("n-estacionados").textContent = cuenta("ESTACIONADO");
    $("n-app").textContent = msg.vehiculos.filter((v) => v.con_app).length;
    $("n-peatones").textContent = (msg.peatones || []).length;
    $("n-llenos").textContent = `${llenos} / ${msg.puestos.length}`;
    $("ocupacion").textContent = capacidad ? (100 * ocupados / capacidad).toFixed(1) + " %" : "—";
    window.visorUltimoSnapshot = msg.t_sim;
  }

  const NOMBRES_KPI = {
    busqueda_media_s: ["Búsqueda media", (v) => v.toFixed(0) + " s"],
    distancia_busqueda_media_m: ["Distancia media", (v) => v.toFixed(0) + " m"],
    co2_busqueda_g: ["CO₂ por búsqueda", (v) => v.toFixed(0) + " g"],
    ocupacion_media_pico: ["Ocupación pico", (v) => (100 * v).toFixed(1) + " %"],
    falsas_liberaciones_100: ["Falsas liberaciones", (v) => v.toFixed(1) + " /100"],
    precision_mapa: ["Precisión del mapa", (v) => (100 * v).toFixed(1) + " %"],
  };

  function onKpi(msg) {
    $("kpis").innerHTML = Object.entries(msg.valores).map(([k, v]) => {
      const [nombre, fmt] = NOMBRES_KPI[k] || [k, (x) => String(x)];
      return `<dt>${nombre}</dt><dd>${fmt(v)}</dd>`;
    }).join("");
  }

  function onVerdad(msg) {
    let difieren = 0;
    for (const p of msg.puestos) {
      const dato = puestos.get(p.puesto_id);
      if (!dato) continue;
      dato.real = p.ocupados;
      if (dato.ocupados !== p.ocupados) difieren++;
    }
    $("verdad-texto").textContent =
      `${difieren} de ${msg.puestos.length} puestos difieren del mapa estimado · ` +
      `${msg.falsas_liberaciones.length} falsas liberaciones en este paso`;
  }

  function onMensaje(evento) {
    const msg = JSON.parse(evento.data);
    if (msg.tipo === "snapshot") onSnapshot(msg);
    else if (msg.tipo === "kpi") onKpi(msg);
    else if (msg.tipo === "verdad" && VER_VERDAD) onVerdad(msg);
  }

  // --- Conexión con reconexión exponencial (1, 2, 4... hasta 30 s) ------------------------
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
    try { ws = new WebSocket(WS_URL); } catch (err) { return reintentar(); }
    ws.onopen = () => { espera = 1; estadoConexion("conectado", "conectado"); };
    ws.onmessage = onMensaje;
    ws.onclose = reintentar;
    ws.onerror = () => ws.close();
  }

  function reintentar() {
    estadoConexion("desconectado", `desconectado · reintento en ${espera} s`);
    setTimeout(conectar, espera * 1000);
    espera = Math.min(espera * 2, 30);
  }

  // --- FPS (para medir el rendimiento con el snapshot de hora pico) -----------------------
  let cuadros = 0, t0 = performance.now();
  function medirFps(ahora) {
    cuadros++;
    if (ahora - t0 >= 1000) {
      window.visorFps = (cuadros * 1000) / (ahora - t0);
      $("fps").textContent = window.visorFps.toFixed(0);
      cuadros = 0;
      t0 = ahora;
    }
    requestAnimationFrame(medirFps);
  }

  if (VER_VERDAD) $("verdad").hidden = false;
  leyenda();
  cargarPuestos();
  conectar();
  requestAnimationFrame(medirFps);
})();
