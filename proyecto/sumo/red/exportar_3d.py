"""Escena 3D del visor (`visor/datos/escena3d.json`), a partir de la red de SUMO.

Todo va en metros locales (x al este, y al norte) alrededor de `origen` (lat, lon), con la misma
proyección equirectangular que usa `visor/js/vista3d.js` para los autos del snapshot:

- `edificios`: polígonos `building` de `centro.poly.xml` (de OpenStreetMap) con una altura de 2 o 3
  pisos, fija por id (el Centro Histórico es de casas de 2 y 3 pisos; OSM no trae la altura).
- `verdes`: parques y plazas (`leisure`, `natural`, `landuse`), planos.
- `calles`: el contorno de cada carril para autos, como polilínea con su ancho.

Uso (dentro del contenedor van3twin, desde esta carpeta):
    python3 exportar_3d.py
"""
import json
import math
import os
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


def main():
    red = sumolib.net.readNet(str(DIR / "centro.net.xml"))
    cos0 = math.cos(math.radians(ORIGEN[0]))

    def local(x, y):
        lon, lat = red.convertXY2LonLat(x, y)
        return [round((lon - ORIGEN[1]) * M_POR_GRADO * cos0, 1), round((lat - ORIGEN[0]) * M_POR_GRADO, 1)]

    edificios, verdes = [], []
    for poly in ET.parse(DIR / "centro.poly.xml").getroot().iter("poly"):
        tipo = poly.get("type", "")
        puntos = [tuple(map(float, p.split(","))) for p in poly.get("shape").split()]
        if len(puntos) < 4:
            continue
        forma = [local(x, y) for x, y in puntos[:-1] if True]
        if tipo == "building":
            pisos = 2 + zlib.crc32(poly.get("id").encode()) % 2          # 2 o 3 pisos
            edificios.append({"p": forma, "h": pisos * 3.2})
        elif tipo.split(".")[0] in ("leisure", "natural", "landuse"):
            verdes.append(forma)
    calles = []
    for arista in red.getEdges():
        if arista.getFunction() == "internal" or not arista.allows("passenger"):
            continue
        ancho = sum(c.getWidth() for c in arista.getLanes() if c.allows("passenger"))
        calles.append({"p": [local(x, y) for x, y in arista.getShape()], "w": round(ancho, 1)})
    SALIDA.write_text(json.dumps({"origen": ORIGEN, "edificios": edificios, "verdes": verdes, "calles": calles},
                                 separators=(",", ":")))
    print(f"{SALIDA.name}: {len(edificios)} edificios, {len(verdes)} verdes, {len(calles)} calles, "
          f"{SALIDA.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
