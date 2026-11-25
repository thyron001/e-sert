// Pestaña Billetera: saldo, movimientos y recarga con Payphone (modo de pruebas).
import { ORIGEN, api, dinero, escapar, fechaLocal, mostrarAviso } from "./comun.js";

const MONTOS = [5, 10, 20];
const TIPOS = { recarga: "Recarga", debito: "Parqueo", retencion: "Retención", liberacion: "Liberación" };

function retornoPayphone() {
  // vuelta de Payphone: #billetera?clientTransactionId=…&estado=…
  const i = location.hash.indexOf("?");
  if (!location.hash.startsWith("#billetera") || i < 0) return null;
  const q = new URLSearchParams(location.hash.slice(i + 1));
  history.replaceState(null, "", location.pathname + location.search);
  return { id: q.get("clientTransactionId"), estado: q.get("estado") };
}

export async function pintarBilletera(el, usuario) {
  if (!usuario) { el.innerHTML = `<p class="vacio">Elige un usuario en la pestaña Usuario.</p>`; return; }
  const vuelta = retornoPayphone();
  if (vuelta) {
    const textos = { APROBADO: ["Recarga confirmada.", "ok"], RECHAZADO: ["El pago fue rechazado o cancelado: no se cobró nada.", "error"],
                     PENDIENTE: ["El pago está en revisión; el saldo se actualizará al confirmarse.", "ok"] };
    const [t, tipo] = textos[vuelta.estado] || ["Volviste de Payphone.", "ok"];
    mostrarAviso(t, tipo, 7000);
  }
  let b;
  try {
    b = await api(ORIGEN, `/billetera/${usuario}`);
  } catch (e) {
    el.innerHTML = `<p class="error">${escapar(e.message)}</p>`;
    return;
  }
  el.innerHTML = `
    <div class="tarjeta roja">
      <div class="etq">Disponible</div>
      <div class="grande">${dinero(b.disponible)}</div>
      <div class="etq">Saldo ${dinero(b.saldo)} · Retenido ${dinero(b.retenido)}</div>
    </div>
    <p class="etq">Recargar con Payphone:</p>
    <div class="fila-botones" style="grid-template-columns:repeat(3,1fr);margin-bottom:10px">
      ${MONTOS.map((m) => `<button type="button" class="borde" data-monto="${m}">${dinero(m)}</button>`).join("")}
    </div>
    <button id="b-recargar" class="rojo" type="button" disabled>Recargar con Payphone</button>
    <p id="msj-recarga" class="error"></p>
    <h3 style="margin:18px 0 6px">Movimientos</h3>
    ${b.movimientos.length ? [...b.movimientos].reverse().slice(0, 40).map((m) => {
      const signo = m.tipo === "recarga" || m.tipo === "liberacion" ? "+" : "−";
      const detalle = m.referencia_payphone === "saldo_inicial" ? "Saldo inicial"
        : (m.referencia_payphone || "").startsWith("web:") ? "Tiempo de parqueo"
        : m.referencia_payphone ? `Payphone ${escapar(m.referencia_payphone)}` : "";
      return `<div class="fila"><span><b>${TIPOS[m.tipo] || m.tipo}</b><br><span class="etq">${fechaLocal(m.ts)}${detalle ? " · " + detalle : ""}</span></span>
        <span class="v ${signo === "+" ? "pos" : "neg"}">${signo}${dinero(m.monto)}</span></div>`;
    }).join("") : `<p class="vacio">Sin movimientos.</p>`}`;
  let monto = null;
  for (const bt of el.querySelectorAll("[data-monto]")) {
    bt.onclick = () => {
      monto = Number(bt.dataset.monto);
      for (const o of el.querySelectorAll("[data-monto]")) o.classList.toggle("rojo", o === bt);
      el.querySelector("#b-recargar").disabled = false;
      el.querySelector("#b-recargar").textContent = `Recargar ${dinero(monto)} con Payphone`;
    };
  }
  el.querySelector("#b-recargar").onclick = async () => {
    const boton = el.querySelector("#b-recargar");
    boton.disabled = true;
    boton.textContent = "Abriendo Payphone…";
    try {
      const url_app = `${location.origin}${location.pathname}#billetera`;
      const p = await api(ORIGEN, "/pagos/preparar", { method: "POST", cuerpo: { usuario_id: usuario, monto, url_app } });
      location.href = p.pay_url;
    } catch (e) {
      el.querySelector("#msj-recarga").textContent = e.message;
      boton.disabled = false;
      boton.textContent = `Recargar ${dinero(monto)} con Payphone`;
    }
  };
}
