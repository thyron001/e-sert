// Panel de KPIs en vivo (S3-3): tarjetas alimentadas por mensajes `kpi` (contrato §6) y por el
// estado derivado de cada snapshot (ocupación y sesiones activas), comparación con la búsqueda a
// ciegas (datos/base.json, exportado por kpis/analisis.py) y minigráficas de 10 min con Chart.js.
// Redibujo limitado a 2 Hz: los mensajes marcan cambios; requestAnimationFrame pinta si toca.
import {
  TARJETAS, valorTarjeta, formatoTarjeta, cambioVsBase, relojSim, Serie, Limitador,
  sesionesActivas, ocupacionSnapshot,
} from "./logica.js";

export class PanelKpis {
  constructor(contenedor, nota, urlBase) {
    this.contenedor = contenedor;
    this.nota = nota;
    this.valores = {};
    this.tSim = null;
    this.base = null;
    this.series = new Map(TARJETAS.map((t) => [t.id, new Serie(600)]));
    this.graficas = new Map();
    this.limitador = new Limitador(2);
    this.redibujos = 0;
    this.kpisRecibidos = 0;
    this.construir();
    fetch(urlBase).then((r) => (r.ok ? r.json() : null)).then((d) => {
      this.base = d && d.base ? d.base : null;
      if (this.base) this.nota.textContent = "Comparación: búsqueda a ciegas (0 % con app), " +
        `media de ${d.semillas.length} semillas de la matriz de experimentos.`;
      this.limitador.marcar();
    }).catch(() => { this.nota.textContent = "Sin base.json: no se compara con la búsqueda a ciegas."; });
  }

  construir() {
    this.contenedor.innerHTML = TARJETAS.map((t) => `
      <div class="tarjeta" id="k-${t.id}">
        <div class="t">${t.titulo}</div>
        <div class="v">—</div>
        <div class="c"></div>
        <canvas aria-hidden="true"></canvas>
      </div>`).join("");
    if (typeof Chart === "undefined") return; // sin CDN: las tarjetas funcionan igual
    for (const t of TARJETAS) {
      const lienzo = this.contenedor.querySelector(`#k-${t.id} canvas`);
      this.graficas.set(t.id, new Chart(lienzo, {
        type: "line",
        data: { labels: [], datasets: [{ data: [], borderColor: "#1E63D6", borderWidth: 1.5, pointRadius: 0,
                                        fill: false, tension: 0 }] },
        options: { animation: false, responsive: true, maintainAspectRatio: false, events: [],
                   plugins: { legend: { display: false }, tooltip: { enabled: false } },
                   scales: { x: { display: false, type: "linear" }, y: { display: false } } },
      }));
    }
  }

  onKpi(msg) {
    Object.assign(this.valores, msg.valores || {});
    this.kpisRecibidos++;
    window.visorKpisRecibidos = this.kpisRecibidos;
    this.tSim = msg.t_sim;
    for (const t of TARJETAS) this.series.get(t.id).agregar(msg.t_sim, valorTarjeta(t, msg.valores));
    this.limitador.marcar();
  }

  onSnapshot(msg) {
    const ocup = ocupacionSnapshot(msg);
    const ses = sesionesActivas(msg);
    // si el backend no manda la ocupación ni las sesiones en `kpi`, se derivan del snapshot
    this.valores.ocupacion = ocup;
    this.valores.sesiones_activas = ses;
    this.tSim = msg.t_sim;
    if (Math.floor(msg.t_sim) % 10 === 0) {
      this.series.get("ocupacion").agregar(msg.t_sim, ocup);
      this.series.get("sesiones").agregar(msg.t_sim, ses);
    }
    this.limitador.marcar();
  }

  cada_cuadro(ahora) {
    if (!this.limitador.debe(ahora)) return;
    this.redibujos++;
    window.visorRedibujosPanel = this.redibujos;
    document.getElementById("reloj").textContent = relojSim(this.tSim);
    for (const t of TARJETAS) {
      const el = this.contenedor.querySelector(`#k-${t.id}`);
      const v = valorTarjeta(t, this.valores);
      el.querySelector(".v").textContent = formatoTarjeta(t, v);
      const c = el.querySelector(".c");
      const cambio = this.base && t.base && t.menorMejor !== null ? cambioVsBase(v, this.base[t.base], t.menorMejor) : null;
      c.textContent = cambio ? cambio.texto : "";
      c.className = "c" + (cambio && cambio.mejor !== null ? (cambio.mejor ? " mejor" : " peor") : "");
      const g = this.graficas.get(t.id);
      if (g) {
        const s = this.series.get(t.id);
        g.data.datasets[0].data = s.t.map((x, i) => ({ x, y: s.v[i] }));
        g.update("none");
      }
    }
  }
}
