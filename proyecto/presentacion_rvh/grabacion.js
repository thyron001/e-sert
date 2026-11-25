// Visor de e-sert sin servidor: reemplaza la conexión en vivo por un minuto grabado de la simulación.
//
// La presentación (artefacto de claude.ai) no puede conectarse a e-sert.tesisucuenca.com, así que
// esta copia del visor recibe lo mismo que mandaría el servidor:
// - WebSocket /ws/estado → un `snapshot` por segundo de `datos/repeticion.json` (en bucle) y un `kpi`
//   cada 5 s con los valores medidos al 50 % de usuarios con ocupación real (corrida final);
// - GET /api/v1/puestos, /web/activos y /demo/estado → respuestas armadas con los mismos datos.
// El resto del visor (HTML, CSS y JS) es el del servidor, sin cambios. Lo arma `armar_visor.py`.
(function () {
  "use strict";
  window.WS_GRABADO = "wss://e-sert.tesisucuenca.com/ws/estado";
  const NOMBRE_USUARIO = "Usuario e-Sert";
  const KPI = { busqueda_media_s: 356.7, falsas_liberaciones_100: 0, co2_busqueda_kg_h: 660.7 };
  const fetchReal = window.fetch.bind(window);
  const datos = Promise.all(["datos/repeticion.json", "datos/puestos_geo.json"].map((u) => fetchReal(u).then((r) => r.json())))
    .then(([rep, puestos]) => ({ rep, puestos, cap: new Map(puestos.map((p) => [p.id, p.capacidad])) }));

  const json = (d, estado = 200) => new Response(JSON.stringify(d), { status: estado, headers: { "Content-Type": "application/json" } });
  window.fetch = function (url, opciones) {
    const ruta = new URL(String(url), location.href).pathname;
    if (!ruta.includes("/api/v1/")) return fetchReal(url, opciones);
    if (ruta.endsWith("/api/v1/puestos")) {
      return datos.then(({ puestos }) => json(puestos.map((p) => {
        const m = p.linea[Math.floor(p.linea.length / 2)];
        return { puesto_id: p.id, lat: m[0], lon: m[1], calle: "", capacidad: p.capacidad, ocupados: 0 };
      })));
    }
    if (ruta.endsWith("/web/activos")) {
      return datos.then(({ rep }) => json(rep.destacados.slice(0, 1).map((v) => ({ veh_id: v, nombre: NOMBRE_USUARIO, estado: "activa" }))));
    }
    if (ruta.endsWith("/demo/estado")) {
      return Promise.resolve(json({ disponible: true, corriendo: true, fase: "corriendo", motivo: null,
        escenario: { id: "grabación del Centro", penetracion: 50, ritmo: 1, hasta_s: 3600 } }));
    }
    if (ruta.includes("/demo/")) {
      return Promise.resolve(json({ error: { mensaje: "Esta es una grabación. La demo en vivo está en e-sert.tesisucuenca.com." } }, 409));
    }
    return Promise.resolve(json([]));
  };

  class WebSocketGrabado {
    constructor(url) {
      this.url = url; this.readyState = 0;
      if (!String(url).includes("/ws/estado")) return;   // el espejo no se usa en la grabación
      datos.then((d) => {
        this.readyState = 1;
        this.onopen && this.onopen({});
        let k = 0, vuelta = 0;
        const paso = () => {
          if (this.readyState !== 1) return;
          const f = d.rep.frames[k], t = f.t + vuelta * d.rep.frames.length;
          const snap = {
            tipo: "snapshot", t_sim: t, ts: new Date().toISOString(),
            vehiculos: f.v.map(([i, lat, lon, e, app]) => ({ id: d.rep.ids[i], lat, lon, estado: d.rep.estados[e], con_app: !!app })),
            peatones: [], espejos: d.rep.destacados.slice(0, 1),
            puestos: d.rep.puestos.map((id, i) => ({ puesto_id: id, capacidad: d.cap.get(id) || f.o[i], ocupados: f.o[i] })),
          };
          this.onmessage && this.onmessage({ data: JSON.stringify(snap) });
          if (k % 5 === 0) this.onmessage && this.onmessage({ data: JSON.stringify({ tipo: "kpi", t_sim: t, ts: snap.ts, valores: KPI }) });
          if (k === 0 && vuelta === 0 && window.parent !== window) window.parent.postMessage({ esert: "listo" }, "*");
          k = (k + 1) % d.rep.frames.length;
          if (k === 0) vuelta++;
        };
        paso();
        this.reloj = setInterval(paso, 1000);
      });
    }
    send() {}
    close() { this.readyState = 3; clearInterval(this.reloj); }
  }
  window.WebSocket = WebSocketGrabado;

  // Dentro de la presentación: las flechas cambian de diapositiva aunque el visor tenga el foco.
  addEventListener("keydown", (e) => {
    if (window.parent !== window && ["ArrowRight", "ArrowLeft", "PageDown", "PageUp", " "].includes(e.key)) {
      e.preventDefault();
      window.parent.postMessage({ esert: "tecla", key: e.key }, "*");
    }
  });
})();
