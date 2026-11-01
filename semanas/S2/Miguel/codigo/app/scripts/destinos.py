"""Regenera src/datos/destinos.ts a partir de proyecto/sumo/demanda/destinos.csv (Tyrone, S1).

Uso (desde cualquier carpeta, solo biblioteca estándar):
    python scripts/destinos.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
SALIDA = APP / "src" / "datos" / "destinos.ts"

CABECERA = """// Copia de proyecto/sumo/demanda/destinos.csv (Tyrone, S1), generada con scripts/destinos.py.
// No editar a mano: si cambia el CSV, vuelve a ejecutar el script.
import type { Destino } from '@/src/api/tipos';

export interface DestinoApp extends Destino {
  peso: number;
}

export const DESTINOS: DestinoApp[] = [
"""


def buscar_csv() -> Path:
    """Sube desde la app hasta encontrar la carpeta proyecto/ con el CSV de destinos."""
    for carpeta in [APP, *APP.parents]:
        csv_destinos = carpeta / "proyecto" / "sumo" / "demanda" / "destinos.csv"
        if csv_destinos.is_file():
            return csv_destinos
    raise SystemExit("No se encontró proyecto/sumo/demanda/destinos.csv subiendo desde la app")


def generar(ruta_csv: Path) -> str:
    lineas = [CABECERA]
    with ruta_csv.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            nombre = json.dumps(fila["nombre"], ensure_ascii=False)
            lat, lon, peso = float(fila["lat"]), float(fila["lon"]), int(fila["peso"])
            lineas.append(f"  {{ nombre: {nombre}, lat: {lat!r}, lon: {lon!r}, peso: {peso} }},\n")
    lineas.append("];\n")
    return "".join(lineas)


def main() -> None:
    ruta_csv = buscar_csv()
    texto = generar(ruta_csv)
    # newline="\n": el mismo archivo en Windows y en Linux.
    with SALIDA.open("w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    print(f"{SALIDA.relative_to(APP)}: {texto.count('nombre:')} destinos desde {ruta_csv}")


if __name__ == "__main__":
    main()
