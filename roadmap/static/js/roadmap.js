/* ==========================================================================================
   e-sert · Roadmap: popups de sesión, copiado de prompts, filtros y plegado de semanas.
   El contenido ya viene pintado desde el servidor (#es-datos); aquí solo se mueve.
   ========================================================================================== */
(function () {
  "use strict";

  const modal = document.getElementById("es-modal");
  const cuerpo = document.getElementById("es-cuerpo");
  const datos = document.getElementById("es-datos");
  const toast = document.getElementById("toast");
  let actual = null;

  // ---------------------------------------------------------------- copiar
  function avisar(txt) {
    toast.textContent = txt;
    toast.classList.add("visible");
    clearTimeout(avisar.t);
    avisar.t = setTimeout(() => toast.classList.remove("visible"), 1800);
  }

  async function copiar(texto, aviso) {
    try {
      await navigator.clipboard.writeText(texto);
    } catch (e) {               // http sin permisos: copia con un textarea temporal
      const ta = document.createElement("textarea");
      ta.value = texto; document.body.appendChild(ta); ta.select();
      document.execCommand("copy"); ta.remove();
    }
    avisar(aviso || "Copiado");
  }

  // ---------------------------------------------------------------- popup
  function pestaña(nombre) {
    if (!actual) return;
    modal.querySelectorAll(".es-tab").forEach(b => b.classList.toggle("activo", b.dataset.tab === nombre));
    cuerpo.innerHTML = "";
    const origen = actual.querySelector(nombre === "resultado" ? ".es-p-resultado" : ".es-p-prompt");
    cuerpo.appendChild(origen.cloneNode(true));
    cuerpo.scrollTop = 0;
  }

  function abrir(id) {
    const sec = datos.querySelector(`section[data-id="${CSS.escape(id)}"]`);
    if (!sec) return;
    actual = sec;
    modal.style.setProperty("--p", sec.dataset.color);
    modal.style.setProperty("--pt", sec.dataset.tinte);
    document.getElementById("es-etq").textContent = sec.dataset.etiqueta;
    document.getElementById("es-tipo").textContent = sec.dataset.tipo;
    document.getElementById("es-titulo").textContent = sec.dataset.titulo;
    modal.hidden = false;
    document.body.classList.add("rm-sin-scroll");
    // Si ya hay resultados se abre en esa pestaña; si no, en el prompt.
    const pendiente = sec.dataset.tipo === "Pendiente";
    pestaña(sec.dataset.tab || (pendiente ? "prompt" : "resultado"));
    history.replaceState(null, "", "#" + id);
  }

  function cerrar() {
    modal.hidden = true;
    actual = null;
    document.body.classList.remove("rm-sin-scroll");
    history.replaceState(null, "", location.pathname);
  }

  document.addEventListener("click", (ev) => {
    const a = ev.target.closest("[data-abrir]");
    if (a) { ev.preventDefault(); abrir(a.dataset.abrir); return; }
    const c = ev.target.closest("[data-copiar]");
    if (c) { copiar(c.dataset.copiar, "Comando copiado: pégalo en Claude Code"); return; }
    if (ev.target.closest("[data-copiar-prompt]") && actual) {
      copiar(actual.querySelector(".es-crudo").value, "Prompt completo copiado"); return;
    }
    const t = ev.target.closest(".es-tab");
    if (t) { pestaña(t.dataset.tab); return; }
    if (ev.target.closest("[data-cerrar]")) cerrar();
  });
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !modal.hidden) cerrar(); });

  // ---------------------------------------------------------------- filtros por persona
  document.querySelectorAll(".cr-chip[data-persona]").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".cr-chip[data-persona]").forEach(c => c.classList.toggle("activo", c === chip));
      const p = chip.dataset.persona;
      document.querySelectorAll(".es-carril").forEach(car => { car.hidden = !!p && car.dataset.persona !== p; });
      document.querySelectorAll(".es-carriles").forEach(g => { g.style.gridTemplateColumns = p ? "minmax(0, 520px)" : ""; });
    });
  });

  // ---------------------------------------------------------------- plegado
  document.querySelectorAll(".cr-sem-toggle").forEach(b => {
    b.addEventListener("click", () => b.closest(".cr-semana").classList.toggle("plegada"));
  });
  const plegar = document.getElementById("plegar-todo");
  if (plegar) plegar.addEventListener("click", () => {
    const semanas = document.querySelectorAll(".cr-semana");
    const todas = [...semanas].every(s => s.classList.contains("plegada"));
    semanas.forEach(s => s.classList.toggle("plegada", !todas));
    plegar.textContent = todas ? "Plegar todo" : "Desplegar todo";
  });
  const ir = document.getElementById("ir-actual");
  if (ir) ir.addEventListener("click", () => {
    const s = document.querySelector(".es-semana.actual") || document.querySelector(".es-semana");
    s.classList.remove("plegada");
    s.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  // Las semanas pasadas y completas empiezan plegadas; el enlace #S1-Pablo-2 abre su popup.
  document.querySelectorAll(".es-semana").forEach(s => {
    const prog = s.querySelector(".cr-sem-prog span").textContent.split("/").map(x => parseInt(x));
    if (prog[0] === prog[1] && !s.classList.contains("actual")) s.classList.add("plegada");
  });
  if (location.hash.length > 1) abrir(decodeURIComponent(location.hash.slice(1)));
})();
