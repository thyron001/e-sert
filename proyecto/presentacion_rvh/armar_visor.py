"""Arma `dgm/visor/`: una copia del visor de e-sert que funciona sin servidor, para la presentación.

Copia `proyecto/visor/` (HTML, CSS, JS y datos) y solo cambia tres cosas:
- carga `grabacion.js` antes que todo, que reemplaza el WebSocket y la API por un minuto grabado;
- `principal.js` toma la dirección del WebSocket de `window.WS_GRABADO` (así el QR apunta a
  https://e-sert.tesisucuenca.com/app/);
- la hoja de estilos de Leaflet se sirve desde la copia (el artefacto solo admite estilos propios).

Uso, desde esta carpeta: python3 armar_visor.py
"""
import shutil
from pathlib import Path

AQUI = Path(__file__).resolve().parent
VISOR = AQUI.parent / "visor"
SALIDA = AQUI / "dgm" / "visor"
LEAFLET_CSS = AQUI / "leaflet-1.9.4.css"


def main():
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    (SALIDA / "js").mkdir(parents=True)
    (SALIDA / "css").mkdir()
    (SALIDA / "datos").mkdir()
    for js in sorted((VISOR / "js").glob("*.js")):
        shutil.copy(js, SALIDA / "js" / js.name)
    shutil.copy(AQUI / "grabacion.js", SALIDA / "js" / "grabacion.js")
    shutil.copy(VISOR / "css" / "visor.css", SALIDA / "css" / "visor.css")
    shutil.copy(LEAFLET_CSS, SALIDA / "css" / "leaflet.css")
    for n in ["base.json", "calles_geo.json", "puestos_geo.json", "escena3d.json"]:
        shutil.copy(VISOR / "datos" / n, SALIDA / "datos" / n)
    shutil.copy(AQUI / "dgm" / "repeticion.json", SALIDA / "datos" / "repeticion.json")

    html = (VISOR / "index.html").read_text()
    inicio = html.index('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"')
    fin = html.index(">", html.index('crossorigin=""', inicio)) + 1
    html = html[:inicio] + '<link rel="stylesheet" href="./css/leaflet.css">\n  <script src="./js/grabacion.js"></script>' + html[fin:]
    (SALIDA / "index.html").write_text(html)

    principal = (SALIDA / "js" / "principal.js").read_text()
    viejo = 'const WS_URL = params.get("ws") ||'
    assert viejo in principal, "cambió principal.js: revisa el parche"
    (SALIDA / "js" / "principal.js").write_text(principal.replace(viejo, 'const WS_URL = window.WS_GRABADO || params.get("ws") ||'))
    print("visor sin servidor en", SALIDA)


if __name__ == "__main__":
    main()
