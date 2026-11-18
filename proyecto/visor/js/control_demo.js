// Control de la simulación en el servidor: Iniciar / Detener con la clave de la demo.
// Habla con /api/v1/demo/{estado,iniciar,detener}. La clave se guarda solo en este navegador.

const CLAVE_LS = "esert.claveDemo";
const TEXTO_FASE = {
  inactiva: "detenida",
  preparando: "preparando…",
  corriendo: "corriendo",
  deteniendo: "deteniendo…",
};

function leerClave() {
  try { return localStorage.getItem(CLAVE_LS) || ""; } catch { return ""; }
}

function guardarClave(v) {
  try { v ? localStorage.setItem(CLAVE_LS, v) : localStorage.removeItem(CLAVE_LS); } catch { /* sin almacenamiento */ }
}

export class ControlDemo {
  constructor(apiBase, el) {
    this.api = apiBase + "/demo";
    this.el = el;
    this.estado = null;
    this.ocupado = false;
    el.innerHTML = `
      <h2>Simulación en el servidor</h2>
      <div class="demo-fila"><span id="demo-fase" class="estado conectando">…</span>
        <span id="demo-esc" class="nota"></span></div>
      <div class="demo-fila demo-params">
        <label>Usuarios con app <select id="demo-pen"><option>20</option><option selected>50</option><option>80</option></select> %</label>
        <label>Ritmo <select id="demo-ritmo"><option value="1">1×</option><option value="2" selected>2×</option><option value="5">5×</option><option value="10">10×</option></select></label>
      </div>
      <div class="demo-fila">
        <input id="demo-clave" type="password" placeholder="Clave de la demo" autocomplete="current-password">
      </div>
      <div class="demo-fila">
        <button id="demo-iniciar" type="button">Iniciar</button>
        <button id="demo-detener" type="button" class="secundario">Detener</button>
      </div>
      <p id="demo-msj" class="nota"></p>`;
    this.$ = (id) => el.querySelector("#" + id);
    this.$("demo-clave").value = leerClave();
    this.$("demo-iniciar").addEventListener("click", () => this.accion("iniciar"));
    // En plena corrida, el ritmo se cambia al momento (el controlador lo aplica en el siguiente segundo).
    this.$("demo-ritmo").addEventListener("change", () => {
      if (this.estado && this.estado.corriendo) this.accion("ritmo");
    });
    this.$("demo-detener").addEventListener("click", () => this.accion("detener"));
    this.refrescar();
    setInterval(() => this.refrescar(), 4000);
  }

  async refrescar() {
    try {
      const r = await fetch(this.api + "/estado", { cache: "no-store" });
      if (!r.ok) throw new Error(r.status);
      this.pintar(await r.json());
    } catch {
      this.pintar(null);
    }
  }

  pintar(est) {
    this.estado = est;
    const fase = this.$("demo-fase");
    const iniciar = this.$("demo-iniciar");
    const detener = this.$("demo-detener");
    if (!est) {
      fase.textContent = "sin conexión";
      fase.className = "estado desconectado";
      iniciar.disabled = detener.disabled = true;
      return;
    }
    fase.textContent = est.disponible || est.corriendo ? TEXTO_FASE[est.fase] || est.fase : "no disponible";
    fase.className = "estado " + (est.corriendo ? "conectado" : est.disponible ? "conectando" : "desconectado");
    const e = est.escenario;
    this.$("demo-esc").textContent = e && est.corriendo ? `${e.id} · ${e.ritmo}× · hasta ${e.hasta_s} s` : "";
    const sel = this.$("demo-ritmo");
    if (e && est.corriendo && document.activeElement !== sel && !this.ocupado) sel.value = String(Number(e.ritmo));
    this.$("demo-pen").disabled = est.corriendo;   // los usuarios con app no cambian en vivo
    iniciar.disabled = this.ocupado || est.corriendo || !est.disponible;
    detener.disabled = this.ocupado || !est.corriendo;
    if (!est.disponible && !est.corriendo) this.mensaje(est.motivo || "");
  }

  mensaje(texto) {
    this.$("demo-msj").textContent = texto;
  }

  async accion(cual) {
    const clave = this.$("demo-clave").value.trim();
    if (!clave) { this.mensaje("Escribe la clave de la demo."); return; }
    this.ocupado = true;
    this.pintar(this.estado);
    const textos = { iniciar: "Arrancando SUMO…", detener: "Deteniendo…", ritmo: "Cambiando el ritmo…" };
    this.mensaje(textos[cual]);
    const ritmo = Number(this.$("demo-ritmo").value);
    const cuerpo = cual === "iniciar"
      ? JSON.stringify({ penetracion: Number(this.$("demo-pen").value), ritmo })
      : cual === "ritmo" ? JSON.stringify({ ritmo }) : undefined;
    try {
      const r = await fetch(`${this.api}/${cual}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Clave-Demo": clave },
        body: cuerpo,
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        guardarClave(clave);
        this.mensaje({
          iniciar: "Simulación en marcha: los autos aparecen en unos segundos.",
          detener: "Simulación detenida.",
          ritmo: `Ritmo cambiado a ${ritmo}×. Con sumo-gui en el servidor, 10× puede no alcanzarse del todo.`,
        }[cual]);
        this.pintar(d);
      } else {
        if (r.status === 401) guardarClave("");
        this.mensaje((d.error && d.error.mensaje) || `Error ${r.status}`);
      }
    } catch {
      this.mensaje("No hay conexión con el servidor.");
    } finally {
      this.ocupado = false;
      this.refrescar();
    }
  }
}
