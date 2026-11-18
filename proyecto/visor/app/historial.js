// Pestaña Historial: sesiones terminadas del usuario.
import { ORIGEN, api, dinero, escapar, fechaLocal } from "./comun.js";

const MOTIVOS = {
  me_voy: "Te fuiste", salida: "Salida detectada", tiempo_maximo: "Tiempo máximo (120 min)",
  saldo: "Sin saldo para renovar", sin_puesto: "No había puestos libres", puesto_lleno: "Puesto lleno",
  sin_respuesta: "La simulación no respondió", simulacion_reiniciada: "La simulación se reinició", error: "Error",
};

export async function pintarHistorial(el, usuario) {
  if (!usuario) { el.innerHTML = `<p class="vacio">Elige un usuario en la pestaña Usuario.</p>`; return; }
  el.innerHTML = `<h2 class="titulo">Historial</h2><p class="sub">Tus parqueos anteriores.</p><div id="lista-hist"><p class="vacio puntos">Cargando</p></div>`;
  let filas;
  try {
    filas = await api(ORIGEN, `/web/usuarios/${usuario}/historial`);
  } catch (e) {
    el.querySelector("#lista-hist").innerHTML = `<p class="error">${escapar(e.message)}</p>`;
    return;
  }
  el.querySelector("#lista-hist").innerHTML = filas.length ? filas.map((h) => `
    <div class="tarjeta">
      <div class="fila"><b>${h.codigo ? `Puesto ${h.codigo}` : "Sin puesto"}${h.calle ? ` · ${escapar(h.calle)}` : ""}</b>
        <span class="etq">${fechaLocal(h.fecha)}</span></div>
      <div class="fila"><span class="etq">Tiempo pagado</span><span class="v">${h.pagado_min} min</span></div>
      <div class="fila"><span class="etq">Débito</span><span class="v ${h.debitado ? "neg" : ""}">${dinero(h.debitado)}</span></div>
      <div class="fila"><span class="etq">${h.modo === "estacionado" ? "Pagado con código" : "Buscó parqueadero"}</span>
        <span class="v">${escapar(MOTIVOS[h.motivo] || h.motivo || "")}</span></div>
    </div>`).join("") : `<p class="vacio">Todavía no tienes parqueos. Ve a <b>Buscar</b> para empezar.</p>`;
}
