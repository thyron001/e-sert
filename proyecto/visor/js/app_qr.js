// QR de la app web (`/app/`): quien lo escanea abre la app en el navegador del teléfono, elige
// su ubicación y busca parqueadero con un auto propio en la simulación.
// Usa `qrcode-generator` (global `qrcode`, cargado en index.html). Visible también en el modo
// presentación, para que el público lo escanee.

export function urlApp(origen = location.origin) {
  return origen.replace(/\/$/, "") + "/app/";
}

export class AppQR {
  constructor(el, url = urlApp()) {
    this.el = el;
    this.url = url;
    if (typeof qrcode !== "function") { el.hidden = true; return; }
    const qr = qrcode(0, "M");
    qr.addData(url);
    qr.make();
    el.innerHTML = `
      <h2>Prueba la app</h2>
      <div class="qr-app">${qr.createSvgTag({ cellSize: 4, margin: 2, scalable: true })}</div>
      <p class="nota">Escanea con la cámara del teléfono para abrir la app.</p>
      <p class="nota enlace-app"></p>`;
    el.querySelector(".enlace-app").textContent = url;
    el.hidden = false;
  }
}
