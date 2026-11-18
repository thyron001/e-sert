// Pestaña Probar IA: el GPS REAL del teléfono, clasificado en vivo por el mismo Random Forest que
// usa la simulación. Cada 5 s se mandan los últimos 30 s de GPS a /api/v1/web/ia/clasificar (lo
// ejecuta el servicio `sim`, que tiene el modelo). Sirve para demostrar que la IA distingue si la
// persona camina, está quieta o va en un vehículo.
import { ORIGEN, api, escapar } from "./comun.js";

const VENTANA_S = 30;
const PERIODO_MS = 5000;
const MODOS = {
  a_pie: ["🚶", "Caminando"], quieto: ["🧍", "Quieto"], vehiculo: ["🚗", "En vehículo"],
};

export class PruebaIA {
  constructor(el) {
    this.el = el;
    this.muestras = [];
    this.vigia = null;
    this.reloj = null;
    this.bloqueo = null;
    this.historia = [];
    this.ultimo = null;
    this.error = "";
  }

  mostrar() { this.pintar(); }

  ocultar() { /* sigue midiendo en segundo plano mientras la página esté abierta */ }

  get activa() { return this.vigia !== null; }

  async empezar() {
    if (!("geolocation" in navigator)) { this.error = "Este navegador no da acceso al GPS."; this.pintar(); return; }
    this.error = "";
    this.muestras = [];
    this.vigia = navigator.geolocation.watchPosition(
      (p) => {
        this.muestras.push({ t: p.timestamp / 1000, lat: p.coords.latitude, lon: p.coords.longitude,
                             precision_m: p.coords.accuracy });
        const corte = Date.now() / 1000 - 2 * VENTANA_S;
        this.muestras = this.muestras.filter((m) => m.t >= corte);
        if (this.error.startsWith("GPS") || this.error.startsWith("Esperando")) { this.error = ""; this.pintar(); }
        this.pintarEstado();
      },
      (e) => {
        if (e.code === 3 && this.muestras.length) return;  // tiempo de espera: ya llegarán más puntos
        this.error = e.code === 1 ? "Sin permiso de ubicación: actívalo para este sitio en el navegador."
          : `GPS: ${e.message || "sin señal todavía"}`;
        this.pintar();
      },
      { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 },
    );
    this.reloj = setInterval(() => this.clasificar(), PERIODO_MS);
    try { this.bloqueo = await navigator.wakeLock.request("screen"); } catch { /* sin bloqueo de pantalla */ }
    this.pintar();
  }

  detener() {
    if (this.vigia !== null) navigator.geolocation.clearWatch(this.vigia);
    clearInterval(this.reloj);
    this.vigia = null;
    try { this.bloqueo && this.bloqueo.release(); } catch { /* */ }
    this.pintar();
  }

  async clasificar() {
    const ahora = Date.now() / 1000;
    const ventana = this.muestras.filter((m) => m.t >= ahora - VENTANA_S);
    if (ventana.length < 3) { this.error = "Esperando más puntos de GPS…"; this.pintarEstado(); return; }
    try {
      const r = await api(ORIGEN, "/web/ia/clasificar", { method: "POST", cuerpo: { muestras: ventana } });
      this.error = "";
      this.ultimo = { ...r, hora: new Date() };
      this.historia.unshift(this.ultimo);
      this.historia = this.historia.slice(0, 12);
    } catch (e) {
      this.error = e.message;
    }
    this.pintar();
  }

  velocidad() {
    const m = this.muestras.slice(-6);
    if (m.length < 2) return null;
    let d = 0;
    for (let i = 1; i < m.length; i++) {
      const dy = (m[i].lat - m[i - 1].lat) * 111320;
      const dx = (m[i].lon - m[i - 1].lon) * 111320 * Math.cos(m[i].lat * Math.PI / 180);
      d += Math.hypot(dx, dy);
    }
    const dt = m[m.length - 1].t - m[0].t;
    return dt > 0 ? d / dt * 3.6 : null;
  }

  pintarEstado() {
    const el = this.el.querySelector("#ia-gps");
    if (!el) return;
    const ult = this.muestras[this.muestras.length - 1];
    const v = this.velocidad();
    el.textContent = ult ? `${this.muestras.length} puntos · precisión ${Math.round(ult.precision_m)} m` +
      (v != null ? ` · ~${v.toFixed(1)} km/h` : "") : "Esperando el primer punto de GPS…";
  }

  pintar() {
    const u = this.ultimo;
    const [icono, nombre] = u ? MODOS[u.modo] || ["❔", u.modo] : ["🛰️", this.activa ? "Midiendo…" : "Sin medir"];
    this.el.innerHTML = `
      <h2 class="titulo">Probar IA</h2>
      <p class="sub">Usa el GPS real de este teléfono. Cada 5 s, el mismo Random Forest que usa la simulación decide si
        vas <b>caminando</b>, estás <b>quieto</b> o vas <b>en un vehículo</b>. Prueba caminar y luego subir a un auto.</p>
      <div class="tarjeta modo-ia">
        <div class="icono">${icono}</div>
        <div class="nombre">${nombre}</div>
        ${u ? `<div class="conf">Confianza ${Math.round(u.confianza * 100)} % · ${u.fuente === "rf" ? "Random Forest" : "regla de umbral (pocos datos)"}</div>
               <div class="barra-conf"><div style="width:${Math.round(u.confianza * 100)}%"></div></div>` : ""}
      </div>
      <p id="ia-gps" class="etq centro"></p>
      ${this.error ? `<p class="error centro">${escapar(this.error)}</p>` : ""}
      <button id="b-ia" type="button" class="${this.activa ? "gris" : "rojo"}">${this.activa ? "Detener" : "Empezar a medir"}</button>
      ${this.historia.length ? `<h3 style="margin:18px 0 8px">Últimas detecciones</h3><div class="linea-ia">${this.historia.map((h) =>
        `<span>${(MODOS[h.modo] || ["❔"])[0]} ${h.hora.toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>`).join("")}</div>` : ""}
      <p class="etq" style="margin-top:16px">El GPS necesita cielo abierto: dentro de un edificio la precisión baja y la IA
        puede confundirse. Los datos no se guardan.</p>`;
    this.el.querySelector("#b-ia").onclick = () => (this.activa ? this.detener() : this.empezar());
    this.pintarEstado();
  }
}
