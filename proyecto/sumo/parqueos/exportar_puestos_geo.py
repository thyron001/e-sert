"""Geometría de los puestos y nombres de calles para el visor y la app web.

- `visor/datos/puestos_geo.json`: los puestos (ver abajo);
- `visor/datos/calles_geo.json`: dónde y con qué ángulo escribir el nombre de cada calle (el mapa
  satelital no trae nombres: se dibujan sobre el lienzo, solo nombres de calles).

Para cada `parkingArea` de `parqueos.add.xml`: el tramo junto a la acera (lado derecho del carril,
entre `startPos` y `endPos`) como línea en lat/lon, y la posición y el rumbo de cada plaza
(`roadsideCapacity`), para dibujar los autos estacionados en su lugar. El `codigo` (001…) es el
mismo que usa el backend (`backend/web/servicio.py: codigos_de`): orden alfabético de los ids.

Uso (dentro del contenedor van3twin, desde esta carpeta):
    python3 exportar_puestos_geo.py
"""
import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import sumolib  # noqa: E402
from sumolib.geomhelper import positionAtShapeOffset, polygonOffsetWithMinimumDistanceToPoint  # noqa: E402,F401

DIR = Path(__file__).resolve().parent
RED = DIR.parent / "red" / "centro.net.xml"
SALIDA = DIR.parent.parent / "visor" / "datos" / "puestos_geo.json"
SALIDA_CALLES = DIR.parent.parent / "visor" / "datos" / "calles_geo.json"
SEPARACION_NOMBRES_M = 160  # entre dos rótulos de la misma calle
LARGO_MIN_ARISTA_M = 45
SEPARACION_ACERA_M = 1.4   # del borde del carril hacia la acera


def punto_desplazado(forma, pos, lateral):
    """(x, y, rumbo°) a `pos` metros sobre `forma`, corrido `lateral` metros a la derecha."""
    x, y = positionAtShapeOffset(forma, pos)
    x2, y2 = positionAtShapeOffset(forma, min(pos + 0.5, sumolib.geomhelper.polyLength(forma)))
    if (x2, y2) == (x, y):
        x0, y0 = positionAtShapeOffset(forma, max(pos - 0.5, 0))
        dx, dy = x - x0, y - y0
    else:
        dx, dy = x2 - x, y2 - y
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    rx, ry = uy, -ux                                    # normal a la derecha (y hacia arriba)
    rumbo = (math.degrees(math.atan2(ux, uy)) + 360) % 360  # grados desde el norte, horario
    return x + rx * lateral, y + ry * lateral, rumbo


def main():
    net = sumolib.net.readNet(str(RED))
    areas = ET.parse(DIR / "parqueos.add.xml").getroot().findall("parkingArea")
    ids = sorted(a.get("id") for a in areas)
    codigos = {pid: f"{i + 1:03d}" for i, pid in enumerate(ids)}
    salida = []
    for a in areas:
        carril = net.getLane(a.get("lane"))
        forma = carril.getShape()
        largo = carril.getLength()
        ini = float(a.get("startPos", 0))
        fin = float(a.get("endPos", largo))
        ini, fin = max(0.0, ini), min(largo, fin if fin > 0 else largo + fin)
        lateral = carril.getWidth() / 2 + SEPARACION_ACERA_M
        cap = int(a.get("roadsideCapacity", 0))
        linea = []
        pasos = max(2, int((fin - ini) / 4) + 1)
        for i in range(pasos):
            x, y, _ = punto_desplazado(forma, ini + (fin - ini) * i / (pasos - 1), lateral)
            lon, lat = net.convertXY2LonLat(x, y)
            linea.append([round(lat, 7), round(lon, 7)])
        plazas = []
        for i in range(cap):
            x, y, rumbo = punto_desplazado(forma, ini + (fin - ini) * (i + 0.5) / cap, lateral)
            lon, lat = net.convertXY2LonLat(x, y)
            plazas.append([round(lat, 7), round(lon, 7), round(rumbo, 1)])
        salida.append({"id": a.get("id"), "codigo": codigos[a.get("id")], "capacidad": cap,
                       "linea": linea, "plazas": plazas})
    salida.sort(key=lambda p: p["id"])
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(salida)} puestos, {sum(p['capacidad'] for p in salida)} plazas → {SALIDA} "
          f"({SALIDA.stat().st_size // 1024} KiB)")
    exportar_calles(net)


def exportar_calles(net):
    """Rótulos: por cada calle con nombre, el centro de sus aristas largas, separados ≥ 160 m."""
    rotulos = []
    por_nombre = {}
    for arista in net.getEdges():
        nombre = (arista.getName() or "").strip()
        if not nombre or arista.getFunction() or arista.getLength() < LARGO_MIN_ARISTA_M:
            continue
        if not arista.allows("passenger"):
            continue
        forma = arista.getLanes()[0].getShape()
        mitad = arista.getLanes()[0].getLength() / 2
        x, y = positionAtShapeOffset(forma, mitad)
        puestos = por_nombre.setdefault(nombre, [])
        if any(math.hypot(x - px, y - py) < SEPARACION_NOMBRES_M for px, py in puestos):
            continue
        puestos.append((x, y))
        x1, y1 = positionAtShapeOffset(forma, max(0.0, mitad - 6))
        x2, y2 = positionAtShapeOffset(forma, mitad + 6)
        (lo1, la1), (lo2, la2) = net.convertXY2LonLat(x1, y1), net.convertXY2LonLat(x2, y2)
        rotulos.append([nombre, round(la1, 7), round(lo1, 7), round(la2, 7), round(lo2, 7)])
    SALIDA_CALLES.write_text(json.dumps(rotulos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(rotulos)} rótulos de {len(por_nombre)} calles → {SALIDA_CALLES} "
          f"({SALIDA_CALLES.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
