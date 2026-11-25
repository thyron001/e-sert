"""Arma `e-sert_dgm.html`: la presentación para la DGM en un solo archivo (datos e imágenes incrustados).

Funciona abierta desde el disco; solo necesita internet para la tipografía y three.js (CDN).
Uso, desde esta carpeta: python3 armar_independiente.py
"""
import base64
import json
import pathlib

AQUI = pathlib.Path(__file__).resolve().parent
s = (AQUI / "presentacion.html").read_text()
for n in ["guiado", "activa", "billetera"]:
    b = base64.b64encode((AQUI / f"dgm/img/{n}.jpg").read_bytes()).decode()
    s = s.replace(f'src="img/{n}.jpg"', f'src="data:image/jpeg;base64,{b}"')
vista = (AQUI / "dgm/js/vista3d.js").read_text().replace("export class Vista3D", "class Vista3D")
s = s.replace('import { Vista3D } from "./js/vista3d.js";', "/* vista3d.js en línea */\n" + vista)
datos = {f"datos/{n}": json.loads((AQUI / f"dgm/datos/{n}").read_text())
         for n in ["escena3d.json", "puestos_geo.json", "calles_geo.json", "repeticion.json"]}
shim = ("<script>/* datos incrustados: el archivo funciona abierto desde el disco */\nwindow.__DATOS="
        + json.dumps(datos, separators=(",", ":"))
        + ';\n(function(){const f=window.fetch;window.fetch=function(u,o){const k=String(u).replace(/^\\.\\//,"");'
          'if(window.__DATOS[k]) return Promise.resolve(new Response(JSON.stringify(window.__DATOS[k]),'
          '{headers:{"Content-Type":"application/json"}}));return f(u,o);};})();</script>\n')
j = s.index("</style>") + len("</style>")
html = ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + s[:j] + "\n" + shim + "</head>\n<body>\n" + s[j:] + "\n</body>\n</html>\n")
(AQUI / "e-sert_dgm.html").write_text(html)
print(f"e-sert_dgm.html: {len(html) / 1e6:.2f} MB")
