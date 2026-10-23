"""
Anonimiza una grabación casera antes de subirla al repo: traslada la traza para que su primer
punto quede en un lugar de referencia (por defecto el Parque Calderón), sin deformarla.

    python anonimizar_grabacion.py <grabacion.csv> [--salida otra.csv] [--ref -2.8975,-79.0045]

Se conservan intactos las distancias y rumbos entre puntos (en metros), los tiempos, la
precisión, la velocidad y las etiquetas, que es lo que usa el clasificador. Solo cambian
lat y lon. La salida por defecto es <grabacion>_anon.csv junto a la entrada.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

RADIO_TIERRA_M = 6_371_000
PARQUE_CALDERON = (-2.8975, -79.0045)


def trasladar(lat: float, lon: float, origen: tuple[float, float], ref: tuple[float, float]) -> tuple[float, float]:
    """Pasa el punto a metros relativos al origen y los vuelve a proyectar alrededor de ref."""
    x = math.radians(lon - origen[1]) * RADIO_TIERRA_M * math.cos(math.radians(origen[0]))
    y = math.radians(lat - origen[0]) * RADIO_TIERRA_M
    nueva_lat = ref[0] + math.degrees(y / RADIO_TIERRA_M)
    nueva_lon = ref[1] + math.degrees(x / (RADIO_TIERRA_M * math.cos(math.radians(ref[0]))))
    return nueva_lat, nueva_lon


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--salida", type=Path, default=None)
    ap.add_argument("--ref", default=f"{PARQUE_CALDERON[0]},{PARQUE_CALDERON[1]}", help="lat,lon del nuevo primer punto")
    args = ap.parse_args()
    ref = tuple(float(v) for v in args.ref.split(","))
    salida = args.salida or args.csv.with_name(args.csv.stem + "_anon.csv")

    with args.csv.open(newline="", encoding="utf-8") as f:
        lector = csv.reader(f)
        encabezado = next(lector)
        filas = list(lector)
    i_lat, i_lon = encabezado.index("lat"), encabezado.index("lon")
    origen = (float(filas[0][i_lat]), float(filas[0][i_lon]))

    with salida.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f, lineterminator="\n")
        escritor.writerow(encabezado)
        for fila in filas:
            lat, lon = trasladar(float(fila[i_lat]), float(fila[i_lon]), origen, ref)
            fila[i_lat], fila[i_lon] = f"{lat:.7f}", f"{lon:.7f}"
            escritor.writerow(fila)
    print(f"{salida}: {len(filas)} filas trasladadas a {ref}")


if __name__ == "__main__":
    main()
