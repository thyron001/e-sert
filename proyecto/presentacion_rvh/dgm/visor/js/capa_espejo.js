// Capa del vehículo espejo (S3-3): resalta los IDs de `snapshot.espejos` (contrato §6) con un halo
// pulsante y la etiqueta "espejo", dibuja su rastro de 60 s y, con `?espejo=<veh_id>`, se conecta a
// WS /ws/espejo/{veh_id} (§7) para dibujar la ruta restante y el puesto asignado. Si el conductor se
// bajó, el halo pasa a su peatón (`ped_<veh>`). Al salir de `espejos` o con `espejo_fin`, el
// resaltado se retira en 5 s.
import { SeguimientoEspejos, posicionEspejo, recortarRastro, numero, siguienteEspera } from "./logica.js";

const COLOR = "#FFD60A";
const COLOR_RUTA = "#7B2CBF";

export class CapaEspejo {
  constructor(mapa, { wsBase, vehInicial = null, retiroS = 5 } = {}) {
    this.mapa = mapa;
    this.wsBase = wsBase;
    this.seg = new SeguimientoEspejos(retiroS);
    this.capa = L.layerGroup().addTo(mapa);
    this.items = new Map(); // id → {marcador, rastro: [[lat, lon, t]], linea}
    this.detalle = new Map(); // id → último mensaje `espejo`
    this.ruta = null;
    this.alPuesto = null;
    this.marcaPuesto = null;
    this.ultimoSnapshot = null;
    this.puestos = new Map();
    this.vehWs = vehInicial;
    if (vehInicial) { this.seg.agregar(vehInicial); this.conectarEspejo(vehInicial, 1); }
  }

  ahora() { return performance.now() / 1000; }

  /** Posición del espejo principal (para que la cámara lo siga con la tecla E). */
  principal() {
    const id = this.vehWs && this.items.has(this.vehWs) ? this.vehWs : this.seg.visibles()[0];
    const it = id && this.items.get(id);
    return it ? it.marcador.getLatLng() : null;
  }

  icono(id, tipo, retirando) {
    const clase = `halo-espejo${tipo === "peaton" ? " peaton" : ""}${retirando ? " retirando" : ""}`;
    return L.divIcon({ className: clase, iconSize: [0, 0],
                       html: `<div class="anillo"></div><div class="nucleo"></div><div class="etiqueta">espejo</div>` });
  }

  onSnapshot(msg) {
    this.ultimoSnapshot = msg;
    const espejos = [...(msg.espejos || [])];
    if (this.vehWs && this.wsActivo) espejos.push(this.vehWs);
    this.seg.actualizar(espejos, this.ahora());
    for (const id of this.seg.visibles()) {
      const pos = posicionEspejo(id, msg);
      if (!pos) continue;
      let it = this.items.get(id);
      const retirando = this.seg.retirando(id);
      const claveIcono = pos.tipo + retirando;
      if (!it) {
        const marcador = L.marker([pos.lat, pos.lon], { icon: this.icono(id, pos.tipo, retirando), zIndexOffset: 1000,
                                                       keyboard: false })
          .bindPopup(() => this.popup(id)).addTo(this.capa);
        const linea = L.polyline([], { color: COLOR, weight: 4, opacity: 0.9 }).addTo(this.capa);
        it = { marcador, linea, rastro: [], claveIcono };
        this.items.set(id, it);
      } else {
        it.marcador.setLatLng([pos.lat, pos.lon]);
        if (it.claveIcono !== claveIcono) { it.marcador.setIcon(this.icono(id, pos.tipo, retirando)); it.claveIcono = claveIcono; }
      }
      it.estado = pos.estado;
      it.rastro.push([pos.lat, pos.lon, msg.t_sim]);
      it.rastro = recortarRastro(it.rastro, msg.t_sim, 60);
      it.linea.setLatLngs(it.rastro.map((p) => [p[0], p[1]]));
    }
    this.purgar();
    window.visorEspejosVisibles = [...this.items.keys()];
  }

  cada_cuadro() { if (this.items.size) this.purgar(); }

  purgar() {
    for (const id of this.seg.purgar(this.ahora())) this.retirar(id);
    for (const id of [...this.items.keys()]) if (!this.seg.visibles().includes(id)) this.retirar(id);
  }

  retirar(id) {
    const it = this.items.get(id);
    if (!it) return;
    this.capa.removeLayer(it.marcador);
    this.capa.removeLayer(it.linea);
    this.items.delete(id);
    if (id === this.vehWs) this.limpiarRuta();
    window.visorEspejosVisibles = [...this.items.keys()];
  }

  popup(id) {
    const d = this.detalle.get(id);
    const it = this.items.get(id) || {};
    const filas = [`<b>${id}</b> · espejo`, `Estado: ${(d && d.estado) || it.estado || "—"}`];
    if (d && d.destino) filas.push(`Destino: ${d.destino.nombre}`);
    if (d && d.puesto) filas.push(`Puesto: ${d.puesto.puesto_id} (${numero(d.puesto.distancia_m)} m al destino)`);
    if (d && d.sesion) filas.push(`Sesión: ${numero(d.sesion.minutos, 1)} min · $${numero(d.sesion.costo_usd, 2)}`);
    if (d && d.recibo) filas.push(`Recibo: $${numero(d.recibo.cobrado_usd, 2)}`);
    if (!d) filas.push("<i>Abre ?espejo=" + id + " para ver ruta, puesto y costo</i>");
    return filas.join("<br>");
  }

  // --- WS /ws/espejo/{veh_id} ------------------------------------------------------------------
  conectarEspejo(veh, espera) {
    let ws;
    try { ws = new WebSocket(`${this.wsBase}/ws/espejo/${encodeURIComponent(veh)}`); } catch (e) { return; }
    ws.onopen = () => { this.wsActivo = true; espera = 1; };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.tipo === "espejo") this.onEspejo(m);
      else if (m.tipo === "espejo_fin") { this.terminado = m.motivo; this.wsActivo = false; this.seg.fin(m.veh_id, this.ahora()); }
    };
    ws.onclose = () => {
      this.wsActivo = false;
      if (!this.terminado) setTimeout(() => this.conectarEspejo(veh, siguienteEspera(espera)), espera * 1000);
    };
    ws.onerror = () => ws.close();
  }

  onEspejo(m) {
    this.detalle.set(m.veh_id, m);
    this.seg.agregar(m.veh_id);
    window.visorEspejoMensajes = (window.visorEspejoMensajes || 0) + 1;
    const ruta = (m.ruta || []).map((p) => [p[0], p[1]]);
    if (!this.ruta) this.ruta = L.polyline([], { color: COLOR_RUTA, weight: 4, opacity: 0.8 }).addTo(this.capa);
    this.ruta.setLatLngs(ruta);
    if (m.puesto) {
      const destinoRuta = [m.lat, m.lon];
      const puesto = [m.puesto.lat, m.puesto.lon];
      if (!this.alPuesto) this.alPuesto = L.polyline([], { color: COLOR_RUTA, weight: 2.5, dashArray: "6 6" }).addTo(this.capa);
      this.alPuesto.setLatLngs([ruta.length ? ruta[ruta.length - 1] : destinoRuta, puesto]);
      if (!this.marcaPuesto) {
        this.marcaPuesto = L.circleMarker(puesto, { radius: 10, color: COLOR_RUTA, weight: 3, fillColor: "#ffffff",
                                                    fillOpacity: 0.9 }).bindTooltip("puesto asignado", { permanent: true,
                                                    direction: "right", offset: [10, 0] }).addTo(this.capa);
      } else this.marcaPuesto.setLatLng(puesto);
    }
    window.visorEspejoRuta = ruta.length;
    window.visorEspejoPuesto = m.puesto ? m.puesto.puesto_id : null;
  }

  limpiarRuta() {
    for (const k of ["ruta", "alPuesto", "marcaPuesto"]) if (this[k]) { this.capa.removeLayer(this[k]); this[k] = null; }
    window.visorEspejoRuta = 0;
    window.visorEspejoPuesto = null;
  }
}
