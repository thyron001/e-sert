// Pestaña Usuario: el equipo y tres invitados, cada uno con su billetera ($10 iniciales).
import { ORIGEN, api, dinero, escapar } from "./comun.js";

const CLAVE = "esert.perfil";
const COLORES = ["#1E63D6", "#2E9E4F", "#C62828", "#FF7043", "#8e24aa", "#00897b", "#6d4c41"];

export function perfilGuardado() {
  try { return localStorage.getItem(CLAVE); } catch { return null; }
}

function guardar(id) {
  try { localStorage.setItem(CLAVE, id); } catch { /* sin almacenamiento */ }
}

const iniciales = (n) => n.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();

export async function pintarUsuarios(el, app) {
  el.innerHTML = `<h2 class="titulo">¿Quién eres?</h2>
    <p class="sub">Cada usuario tiene su propia billetera (empieza con $10) y su historial. Varios pueden usar la
      app a la vez: en el visor se ve el auto de cada uno.</p><div id="lista-perfiles"><p class="vacio puntos">Cargando</p></div>`;
  let perfiles;
  try {
    perfiles = await api(ORIGEN, "/web/perfiles");
  } catch (e) {
    el.querySelector("#lista-perfiles").innerHTML = `<p class="error">${escapar(e.message)}</p>`;
    return;
  }
  el.querySelector("#lista-perfiles").innerHTML = perfiles.map((p, i) => `
    <button type="button" class="perfil ${p.usuario_id === app.usuario ? "actual" : ""}" data-id="${p.usuario_id}">
      <span class="avatar" style="background:${COLORES[i % COLORES.length]}">${iniciales(p.nombre)}</span>
      <span><span class="n">${escapar(p.nombre)}</span><br><span class="s">Saldo ${dinero(p.saldo)}</span></span>
      ${p.usuario_id === app.usuario ? '<span class="marca">Actual</span>' : ""}
    </button>`).join("");
  for (const b of el.querySelectorAll(".perfil")) {
    b.onclick = () => { guardar(b.dataset.id); app.cambiarUsuario(b.dataset.id); };
  }
}
