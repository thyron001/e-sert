"""Escena 3D del visor (`visor/datos/escena3d.json`), a partir de la red de SUMO.

Todo va en metros locales (x al este, y al norte) alrededor de `origen` (lat, lon), con la misma
proyección equirectangular que usa `visor/js/vista3d.js` para los autos del snapshot:

- `edificios`: polígonos `building` de `centro.poly.xml` (OpenStreetMap) con 2 o 3 pisos, fijos por
  id (el Centro Histórico es de casas de 2 y 3 pisos; OSM no trae la altura) y un tipo de techo: teja
  (la mayoría, como en Cuenca) o losa.
- `parques` (`leisure`, `natural`, `tourism`, `farm`), `canchas` (`sport`), `terrenos` (`landuse`), `agua` (`water`, el río
  Tomebamba) y `parqueaderos` (`parking`, fuera de la vía): polígonos planos.
- `calles`: la calzada de cada arista para autos, como polilínea con su ancho.
- `aceras`: los carriles solo peatonales (aceras) con su ancho; `cruces`: los pasos de cebra.
- `centro`: línea amarilla entre los dos sentidos de una calle doble; `carriles`: líneas blancas entre
  carriles del mismo sentido.
- `arboles`: puntos dentro de los parques (uno cada ~110 m², semilla fija).

Uso (dentro del contenedor van3twin, desde esta carpeta):
    python3 exportar_3d.py
"""
import json
import math
import os
import random
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import sumolib  # noqa: E402

DIR = Path(__file__).resolve().parent
SALIDA = DIR.parent.parent / "visor" / "datos" / "escena3d.json"
ORIGEN = (-2.8974, -79.0045)          # el mismo centro que usa el mapa 2D
M_POR_GRADO = 111320.0
M2_POR_ARBOL = 110.0
MAX_ARBOLES = 2500


def desplazar(forma, d):
    """Polilínea corrida `d` metros a la izquierda (d < 0: a la derecha)."""
    out = []
    for i, (x, y) in enumerate(forma):
        a, b = forma[max(i - 1, 0)], forma[min(i + 1, len(forma) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        out.append((x - dy / n * d, y + dx / n * d))
    return out


def area(p):
    return abs(sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p)))) / 2


def dentro(x, y, p):
    c = False
    for i in range(len(p)):
        (x1, y1), (x2, y2) = p[i - 1], p[i]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def main():
    red = sumolib.net.readNet(str(DIR / "centro.net.xml"), withPedestrianConnections=True)
    cos0 = math.cos(math.radians(ORIGEN[0]))

    def local(x, y):
        lon, lat = red.convertXY2LonLat(x, y)
        return [round((lon - ORIGEN[1]) * M_POR_GRADO * cos0, 1), round((lat - ORIGEN[0]) * M_POR_GRADO, 1)]

    def lista(forma):
        return [local(x, y) for x, y in forma]

    escena = {"origen": ORIGEN, "edificios": [], "parques": [], "canchas": [], "terrenos": [], "agua": [],
              "parqueaderos": [], "calles": [], "aceras": [], "cruces": [], "centro": [], "carriles": [],
              "arboles": []}
    # polyconvert pierde la subetiqueta de OSM: el Parque Calderón llega como `tourism` y `farm`.
    # `historic` no se dibuja: es el contorno de todo el Centro Histórico.
    clase = {"leisure": "parques", "natural": "parques", "tourism": "parques", "farm": "parques",
             "sport": "canchas", "landuse": "terrenos", "water": "agua", "parking": "parqueaderos"}
    for poly in ET.parse(DIR / "centro.poly.xml").getroot().iter("poly"):
        tipo = poly.get("type", "")
        puntos = [tuple(map(float, p.split(","))) for p in poly.get("shape").split()]
        if len(puntos) < 4:
            continue
        forma = lista(puntos[:-1])
        if tipo == "building":
            h = zlib.crc32(poly.get("id").encode())
            escena["edificios"].append({"p": forma, "h": (2 + h % 2) * 3.2, "t": 0 if h % 4 else 1})
        elif tipo in clase:
            escena[clase[tipo]].append(forma)

    # índice de edificios por celdas de 50 m, para no poner árboles dentro de una casa
    celdas = {}
    for e in escena["edificios"]:
        xs, ys = [q[0] for q in e["p"]], [q[1] for q in e["p"]]
        for cx in range(int(min(xs) // 50), int(max(xs) // 50) + 1):
            for cy in range(int(min(ys) // 50), int(max(ys) // 50) + 1):
                celdas.setdefault((cx, cy), []).append(e["p"])

    def libre(x, y):
        return not any(dentro(x, y, b) for b in celdas.get((int(x // 50), int(y // 50)), []))

    rng = random.Random(42)
    for p in escena["parques"]:
        xs, ys = [q[0] for q in p], [q[1] for q in p]
        n = min(int(area(p) / M2_POR_ARBOL), 400)
        for _ in range(n * 3):
            if n <= 0 or len(escena["arboles"]) >= MAX_ARBOLES:
                break
            x, y = rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys))
            if dentro(x, y, p) and libre(x, y):
                escena["arboles"].append([round(x, 1), round(y, 1)])
                n -= 1

    ids = {e.getID() for e in red.getEdges()}
    for arista in red.getEdges(withInternal=True):
        funcion = arista.getFunction()
        if funcion == "crossing":
            carril = arista.getLanes()[0]
            escena["cruces"].append({"p": lista(carril.getShape()), "w": round(carril.getWidth(), 1)})
            continue
        if funcion in ("walkingarea", "internal"):
            continue
        autos = [c for c in arista.getLanes() if c.allows("passenger")]
        for c in arista.getLanes():
            if not c.allows("passenger") and c.allows("pedestrian"):
                escena["aceras"].append({"p": lista(c.getShape()), "w": round(c.getWidth(), 1)})
        if not autos:
            continue
        ancho = sum(c.getWidth() for c in autos)
        escena["calles"].append({"p": lista(arista.getShape()), "w": round(ancho, 1)})
        izquierdo = max(autos, key=lambda c: c.getIndex())
        contraria = arista.getID()[1:] if arista.getID().startswith("-") else "-" + arista.getID()
        if contraria in ids and not arista.getID().startswith("-"):
            escena["centro"].append(lista(desplazar(izquierdo.getShape(), izquierdo.getWidth() / 2)))
        for c in sorted(autos, key=lambda c: c.getIndex())[1:]:
            escena["carriles"].append(lista(desplazar(c.getShape(), -c.getWidth() / 2)))

    SALIDA.write_text(json.dumps(escena, separators=(",", ":")))
    print(f"{SALIDA.name}: " + ", ".join(f"{len(v)} {k}" for k, v in escena.items() if isinstance(v, list))
          + f", {SALIDA.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
