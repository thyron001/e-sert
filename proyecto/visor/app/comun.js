// Utilidades compartidas por las pestañas de la app web.

const params = new URLSearchParams(location.search);
export const ORIGEN = (params.get("api") || location.origin).replace(/\/$/, "");
export const $ = (id) => document.getElementById(id);
export const dinero = (v) => "$" + Number(v || 0).toFixed(2).replace(".", ",");

/** Llamada a la API (`/api/v1` + ruta). Lanza Error con el mensaje del backend si falla. */
export async function api(origen, ruta, opciones = {}) {
  const r = await fetch(origen + "/api/v1" + ruta, {
    ...opciones, headers: { "Content-Type": "application/json", "X-Contrato-Version": "1" },
    body: opciones.cuerpo === undefined ? undefined : JSON.stringify(opciones.cuerpo),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((d.error && d.error.mensaje) || (d.detail && JSON.stringify(d.detail)) || `Error ${r.status}`);
  return d;
}

let temporizador = null;
/** Aviso flotante sobre la barra de pestañas. */
export function mostrarAviso(texto, tipo = "ok", ms = 6000) {
  const el = $("aviso");
  el.textContent = texto;
  el.style.background = tipo === "error" ? "#b71c1c" : "#1b5e20";
  el.hidden = false;
  clearTimeout(temporizador);
  temporizador = setTimeout(() => { el.hidden = true; }, ms);
}

export const escapar = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export function fechaLocal(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("es-EC", { day: "2-digit", month: "2-digit" }) + " " +
    d.toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" });
}
