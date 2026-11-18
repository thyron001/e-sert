// Modo presentación (S3-3): tecla P o ?presentacion=1. Pantalla completa, sin controles, fuentes
// ×1,5 y leyenda grande; encuadre automático a la zona SERT (fitBounds de los puestos).
// Teclas: E (la cámara sigue al vehículo espejo), T (recorrido de 3 vistas cada 20 s), H (ayuda).
import { encuadre } from "./logica.js";

export const VISTAS = [
  { nombre: "Zona SERT completa", centro: null, zoom: null },
  { nombre: "Parque Calderón", centro: [-2.897308, -79.004488], zoom: 18 },
  { nombre: "Mercado 10 de Agosto", centro: [-2.899212, -79.007545], zoom: 18 },
];

export class Presentacion {
  constructor(mapa, { puestos, espejo, inicial = false, cadaS = 20 }) {
    this.mapa = mapa;
    this.puestos = puestos;
    this.espejo = espejo;
    this.cadaS = cadaS;
    this.activa = false;
    this.siguiendo = false;
    this.recorrido = null;
    this.vista = 0;
    this.aviso = document.getElementById("aviso");
    document.addEventListener("keydown", (ev) => this.tecla(ev));
    document.addEventListener("fullscreenchange", () => {
      if (!document.fullscreenElement && this.activa && this.porPantallaCompleta) this.salir();
    });
    setInterval(() => this.seguir(), 1000);
    this.inicial = inicial;
    if (inicial) this.entrar(false);
    window.visorPresentacion = () => ({ activa: this.activa, siguiendo: this.siguiendo,
                                        recorrido: !!this.recorrido, vista: VISTAS[this.vista].nombre,
                                        ayuda: !document.getElementById("ayuda").hidden });
  }

  limites() {
    const pts = [...this.puestos.values()].filter((p) => Number.isFinite(p.lat));
    return encuadre(pts);
  }

  puestosCargados() { if (this.activa || this.inicial) this.encuadrar(); }

  encuadrar() {
    const b = this.limites();
    if (b) this.mapa.fitBounds(b, { padding: [24, 24] });
  }

  tecla(ev) {
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    if (ev.target && ["INPUT", "TEXTAREA", "SELECT"].includes(ev.target.tagName)) return;  // p. ej. la clave de la demo
    const k = ev.key.toLowerCase();
    if (k === "p") this.activa ? this.salir() : this.entrar(true);
    else if (k === "e") this.alternarSeguir();
    else if (k === "t") this.alternarRecorrido();
    else if (k === "h") { const a = document.getElementById("ayuda"); a.hidden = !a.hidden; }
    else if (k === "escape") document.getElementById("ayuda").hidden = true;
  }

  entrar(pantallaCompleta) {
    this.activa = true;
    document.body.classList.add("presentacion");
    this.porPantallaCompleta = false;
    if (pantallaCompleta && document.documentElement.requestFullscreen) {
      document.documentElement.requestFullscreen().then(() => { this.porPantallaCompleta = true; }).catch(() => {});
    }
    setTimeout(() => { this.mapa.invalidateSize(); this.encuadrar(); }, 150);
    this.avisar("Modo presentación · H: ayuda");
  }

  salir() {
    this.activa = false;
    document.body.classList.remove("presentacion");
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    setTimeout(() => this.mapa.invalidateSize(), 150);
  }

  alternarSeguir() {
    this.siguiendo = !this.siguiendo;
    if (this.siguiendo && this.recorrido) this.alternarRecorrido();
    this.avisar(this.siguiendo ? (this.espejo.principal() ? "Siguiendo al vehículo espejo" : "Sin vehículo espejo todavía")
                               : "Cámara libre");
    this.seguir();
  }

  seguir() {
    if (!this.siguiendo) return;
    const pos = this.espejo.principal();
    if (pos) this.mapa.panTo(pos, { animate: true, duration: 0.8, easeLinearity: 0.5 });
  }

  alternarRecorrido() {
    if (this.recorrido) {
      clearInterval(this.recorrido); this.recorrido = null; this.avisar("Recorrido detenido"); return;
    }
    this.siguiendo = false;
    this.vista = -1;
    const paso = () => {
      this.vista = (this.vista + 1) % VISTAS.length;
      const v = VISTAS[this.vista];
      if (v.centro) this.mapa.flyTo(v.centro, v.zoom, { duration: 1.5 });
      else { const b = this.limites(); if (b) this.mapa.flyToBounds(b, { padding: [24, 24], duration: 1.5 }); }
      this.avisar(`Vista: ${v.nombre}`);
    };
    paso();
    this.recorrido = setInterval(paso, this.cadaS * 1000);
  }

  avisar(texto) {
    this.aviso.textContent = texto;
    this.aviso.hidden = false;
    clearTimeout(this._t);
    this._t = setTimeout(() => { this.aviso.hidden = true; }, 2500);
  }
}
