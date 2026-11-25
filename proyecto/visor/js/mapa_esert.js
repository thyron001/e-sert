// Mapa compartido por el visor y la app web (2026-11-18).
//
// - Fondo satelital (Esri World Imagery) con una capa encima que solo trae nombres de calles.
// - `CapaCalle`: un único lienzo con los puestos en líneas punteadas junto a la acera (verde si
//   quedan plazas, rojo si está lleno), los autos estacionados dibujados en sus plazas, los autos
//   en movimiento orientados según su rumbo y los peatones. La geometría sale de SUMO
//   (`datos/puestos_geo.json`, generado por `sumo/parqueos/exportar_puestos_geo.py`).

export const COLORES = {
  libre: "#34d399", lleno: "#f87171", linea: "#ffffff",
  estacionado: "#cbd5e1", app: "#111827",
  BUSCANDO: "#FF9F1C", GUIADO: "#a78bfa", ESTACIONADO: "#60a5fa", A_PIE: "#2dd4bf",
  REGRESANDO: "#f0abfc", SALIENDO: "#d6b48c", CERRADA: "#9ca3af", null: "#e5e7eb",
  propio: "#FFD60A", peaton: "#3b82f6",
};

/** Mapa Leaflet con fondo satelital. Los nombres de calles los dibuja `CapaCalle` (de la red de SUMO). */
export function crearMapa(id, { centro = [-2.8974, -79.0045], zoom = 16, ...opciones } = {}) {
  const mapa = L.map(id, { zoomSnap: 0.25, maxZoom: 20, ...opciones }).setView(centro, zoom);
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 20, maxNativeZoom: 19,
    attribution: "Imágenes &copy; Esri, Maxar · Calles &copy; OpenStreetMap (red de SUMO)",
  }).addTo(mapa);
  return mapa;
}

/** Metros por píxel en la latitud y el zoom actuales. */
function metrosPorPixel(mapa) {
  const lat = mapa.getCenter().lat * Math.PI / 180;
  return 40075016.686 * Math.cos(lat) / (256 * Math.pow(2, mapa.getZoom()));
}

function auto(ctx, x, y, rumboRad, largo, ancho, color, borde, grosor) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rumboRad);
  const r = Math.min(ancho, largo) * 0.28;
  ctx.beginPath();
  ctx.roundRect(-ancho / 2, -largo / 2, ancho, largo, r);
  ctx.fillStyle = color;
  ctx.fill();
  if (borde) { ctx.lineWidth = grosor; ctx.strokeStyle = borde; ctx.stroke(); }
  if (largo >= 9) {  // parabrisas y luneta
    ctx.fillStyle = "rgba(15,23,42,0.75)";
    ctx.fillRect(-ancho * 0.36, -largo * 0.3, ancho * 0.72, largo * 0.16);
    ctx.fillRect(-ancho * 0.36, largo * 0.2, ancho * 0.72, largo * 0.1);
  }
  ctx.restore();
}

export class CapaCalle extends L.Layer {
  constructor({ datos = "./datos/puestos_geo.json", calles = null, alTocarPuesto = null } = {}) {
    super();
    this.urlDatos = datos;
    this.urlCalles = calles || datos.replace("puestos_geo.json", "calles_geo.json");
    this.rotulos = [];             // [nombre, lat1, lon1, lat2, lon2]
    this.alTocarPuesto = alTocarPuesto;
    this.puestos = new Map();      // id → {id, codigo, capacidad, linea, plazas, ocupados}
    this.vehiculos = new Map();    // id → {lat, lon, rumbo, color, borde, halo}
    this.peatones = [];
    this.resaltado = null;         // id de puesto a resaltar (el asignado)
    this._pendiente = false;
  }

  async cargar() {
    fetch(this.urlCalles).then((r) => (r.ok ? r.json() : [])).then((d) => { this.rotulos = d; this.redibujar(); })
      .catch(() => {});
    const r = await fetch(this.urlDatos);
    for (const p of await r.json()) this.puestos.set(p.id, Object.assign(p, { ocupados: 0 }));
    this.redibujar();
    return this.puestos;
  }

  onAdd(mapa) {
    this._mapa = mapa;
    this._lienzo = L.DomUtil.create("canvas", "capa-calle");
    Object.assign(this._lienzo.style, { position: "absolute", left: 0, top: 0, pointerEvents: "none", zIndex: 450 });
    mapa.getContainer().appendChild(this._lienzo);
    this._eventos = { move: () => this.redibujar(), zoom: () => this.redibujar(), resize: () => this.redibujar() };
    mapa.on(this._eventos);
    this._clic = (ev) => this._tocar(ev);
    mapa.on("click", this._clic);
    this.redibujar();
  }

  onRemove(mapa) {
    mapa.off(this._eventos);
    mapa.off("click", this._clic);
    this._lienzo.remove();
  }

  /** `ocupacion`: Map o lista de {puesto_id, ocupados}. */
  fijarOcupacion(lista) {
    for (const o of lista) {
      const p = this.puestos.get(o.puesto_id);
      if (p) p.ocupados = Math.min(o.ocupados, p.capacidad);
    }
    this.redibujar();
  }

  /** `lista`: [{id, lat, lon, color, borde?, halo?}]. El rumbo se calcula con la posición previa;
   *  un auto que todavía no se ha movido (p. ej. estacionado) toma el del puesto más cercano. */
  fijarVehiculos(lista) {
    const vistos = new Set();
    for (const v of lista) {
      vistos.add(v.id);
      const previo = this.vehiculos.get(v.id);
      let rumbo = previo ? previo.rumbo : null, movido = previo ? previo.movido : false;
      if (previo) {
        const dy = (v.lat - previo.lat) * 111320;
        const dx = (v.lon - previo.lon) * 111320 * Math.cos(v.lat * Math.PI / 180);
        if (Math.hypot(dx, dy) > 0.6) { rumbo = Math.atan2(dx, dy); movido = true; }
      }
      if (!movido) { const r = this.rumboPlaza(v.lat, v.lon); if (r !== null) rumbo = r; }
      this.vehiculos.set(v.id, Object.assign({}, v, { rumbo: rumbo ?? 0, movido }));
    }
    for (const id of [...this.vehiculos.keys()]) if (!vistos.has(id)) this.vehiculos.delete(id);
    this.redibujar();
  }

  /** Rumbo (rad) de la plaza de parqueo más cercana a menos de 8 m, o null. */
  rumboPlaza(lat, lon) {
    if (!this._plazas) {
      if (!this.puestos.size) return null;
      this._plazas = new Map();
      for (const p of this.puestos.values()) for (const [la, lo, r] of p.plazas || []) {
        const k = `${Math.round(la * 1e4)},${Math.round(lo * 1e4)}`;
        if (!this._plazas.has(k)) this._plazas.set(k, []);
        this._plazas.get(k).push([la, lo, r * Math.PI / 180]);
      }
    }
    const ci = Math.round(lat * 1e4), cj = Math.round(lon * 1e4), cos = Math.cos(lat * Math.PI / 180);
    let mejor = null, dmin = 8;
    for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) {
      for (const [la, lo, r] of this._plazas.get(`${ci + i},${cj + j}`) || []) {
        const d = Math.hypot((la - lat) * 111320, (lo - lon) * 111320 * cos);
        if (d < dmin) { dmin = d; mejor = r; }
      }
    }
    return mejor;
  }

  fijarPeatones(lista) { this.peatones = lista || []; this.redibujar(); }

  redibujar() {
    if (!this._mapa || this._pendiente) return;
    this._pendiente = true;
    requestAnimationFrame(() => { this._pendiente = false; this._dibujar(); });
  }

  _dibujar() {
    const mapa = this._mapa, c = this._lienzo;
    const tam = mapa.getSize(), dpr = window.devicePixelRatio || 1;
    if (c.width !== tam.x * dpr || c.height !== tam.y * dpr) {
      c.width = tam.x * dpr; c.height = tam.y * dpr;
      c.style.width = tam.x + "px"; c.style.height = tam.y + "px";
    }
    const ctx = c.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, tam.x, tam.y);
    const limites = mapa.getBounds().pad(0.1);
    const mpp = metrosPorPixel(mapa);
    const zoom = mapa.getZoom();
    const largo = Math.max(4.6 / mpp, 7), ancho = Math.max(1.9 / mpp, 3.2);
    const pt = (lat, lon) => mapa.latLngToContainerPoint([lat, lon]);

    // Puestos: línea punteada junto a la acera y autos en las plazas ocupadas
    ctx.lineCap = "round";
    for (const p of this.puestos.values()) {
      const [lat0, lon0] = p.linea[0];
      if (!limites.contains([lat0, lon0]) && !limites.contains(p.linea[p.linea.length - 1])) continue;
      const lleno = p.ocupados >= p.capacidad;
      ctx.beginPath();
      p.linea.forEach(([la, lo], i) => { const q = pt(la, lo); i ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y); });
      ctx.setLineDash(zoom >= 17 ? [6, 4] : [3, 3]);
      ctx.lineWidth = zoom >= 17 ? 3 : 2;
      ctx.strokeStyle = lleno ? COLORES.lleno : COLORES.libre;
      ctx.stroke();
      if (p.id === this.resaltado) {
        ctx.setLineDash([]);
        ctx.lineWidth = 9;
        ctx.strokeStyle = "rgba(255,214,10,0.55)";
        ctx.stroke();
      }
      if (zoom >= 16.5) {
        for (let i = 0; i < p.ocupados && i < p.plazas.length; i++) {
          const [la, lo, r] = p.plazas[i];
          const q = pt(la, lo);
          auto(ctx, q.x, q.y, r * Math.PI / 180, largo, ancho, COLORES.estacionado, "#0f172a", 1);
        }
      }
    }
    ctx.setLineDash([]);
    // Nombres de calles (solo eso: el satélite no trae etiquetas)
    if (zoom >= 15.5 && this.rotulos.length) {
      const tam = zoom >= 17.5 ? 13 : zoom >= 16.5 ? 12 : 10.5;
      ctx.font = `600 ${tam}px system-ui, -apple-system, "Segoe UI", sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.lineJoin = "round"; ctx.lineWidth = 3.5; ctx.strokeStyle = "rgba(2,6,23,0.85)"; ctx.fillStyle = "#ffffff";
      for (const [nombre, la1, lo1, la2, lo2] of this.rotulos) {
        if (!limites.contains([la1, lo1])) continue;
        const a = pt(la1, lo1), b = pt(la2, lo2);
        let ang = Math.atan2(b.y - a.y, b.x - a.x);
        if (ang > Math.PI / 2) ang -= Math.PI; else if (ang < -Math.PI / 2) ang += Math.PI;
        ctx.save();
        ctx.translate((a.x + b.x) / 2, (a.y + b.y) / 2);
        ctx.rotate(ang);
        ctx.strokeText(nombre, 0, 0);
        ctx.fillText(nombre, 0, 0);
        ctx.restore();
      }
    }
    // Peatones
    ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2;
    for (const ped of this.peatones) {
      if (!limites.contains([ped.lat, ped.lon])) continue;
      ctx.fillStyle = ped.color || COLORES.peaton;
      const q = pt(ped.lat, ped.lon);
      ctx.beginPath(); ctx.arc(q.x, q.y, Math.max(4.5, 1.2 / mpp), 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
    }
    // Vehículos en movimiento (el propio/espejo al final, encima)
    const lista = [...this.vehiculos.values()].sort((a, b) => (a.halo ? 1 : 0) - (b.halo ? 1 : 0));
    for (const v of lista) {
      if (!limites.contains([v.lat, v.lon])) continue;
      const q = pt(v.lat, v.lon);
      if (v.halo) {
        // el auto propio (app) o el seguido (espejo): grande y con halo, visible a cualquier zoom
        const radio = Math.max(largo * 1.3, 20);
        ctx.beginPath(); ctx.arc(q.x, q.y, radio, 0, 2 * Math.PI);
        ctx.globalAlpha = 0.28; ctx.fillStyle = v.color; ctx.fill(); ctx.globalAlpha = 1;
        ctx.lineWidth = 2; ctx.strokeStyle = v.color; ctx.stroke();
        auto(ctx, q.x, q.y, v.rumbo, Math.max(largo * 1.6, 18), Math.max(ancho * 1.6, 8.5), v.color, "#0f172a", 2);
        if (v.etiqueta) {  // nombre del usuario de la app (visor)
          ctx.font = '700 12px system-ui, -apple-system, "Segoe UI", sans-serif';
          ctx.textAlign = "center"; ctx.textBaseline = "bottom";
          const y = q.y - radio - 3, w = ctx.measureText(v.etiqueta).width + 10;
          ctx.fillStyle = v.color;
          ctx.beginPath(); ctx.roundRect(q.x - w / 2, y - 17, w, 18, 6); ctx.fill();
          ctx.fillStyle = "#fff"; ctx.fillText(v.etiqueta, q.x, y);
        }
        continue;
      }
      auto(ctx, q.x, q.y, v.rumbo, largo, ancho, v.color, v.borde || "#0f172a", v.borde ? 2 : 1);
    }
  }

  /** Puesto más cercano al toque (a menos de 18 px de su línea), o null. */
  puestoEn(punto) {
    const mapa = this._mapa;
    let mejor = null, dist = 18;
    for (const p of this.puestos.values()) {
      for (let i = 1; i < p.linea.length; i++) {
        const a = mapa.latLngToContainerPoint(p.linea[i - 1]), b = mapa.latLngToContainerPoint(p.linea[i]);
        const d = distanciaASegmento(punto, a, b);
        if (d < dist) { dist = d; mejor = p; }
      }
    }
    return mejor;
  }

  _tocar(ev) {
    if (!this.alTocarPuesto) return;
    const p = this.puestoEn(ev.containerPoint);
    if (p) this.alTocarPuesto(p, ev);
  }
}

function distanciaASegmento(p, a, b) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const l2 = dx * dx + dy * dy || 1;
  const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / l2));
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}
