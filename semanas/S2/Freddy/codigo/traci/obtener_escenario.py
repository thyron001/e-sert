"""Copia el escenario SUMO de Tyrone desde su rama a `traci/escenario/tyrone/` (sin editarla).

Se ejecuta **en la computadora** (usa git), desde `semanas/S1/Freddy/codigo`:

    python traci/obtener_escenario.py            # rama origin/tyrone/s1

Mientras la red y la demanda no estén unificadas en `proyecto/sumo/`, el controlador y el
generador de trazas usan esta copia: `traci/escenario/tyrone/sumo/centro_base.sumocfg`.
La carpeta `escenario/` está en `traci/.gitignore`.
"""

from __future__ import annotations

import argparse
import io
import subprocess
import tarfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DESTINO = AQUI / "escenario" / "tyrone"
RUTA_EN_RAMA = "semanas/S1/Tyrone/codigo/sumo"


def obtener(rama: str = "origin/tyrone/s1", destino: Path = DESTINO) -> Path:
    """Extrae `semanas/S1/Tyrone/codigo/sumo` de `rama` en `destino/sumo`. Devuelve el .sumocfg."""
    raiz = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=AQUI, text=True).strip())
    datos = subprocess.check_output(["git", "archive", "--format=tar", rama, RUTA_EN_RAMA], cwd=raiz)
    quitar = len(Path(RUTA_EN_RAMA).parts) - 1  # deja la carpeta final `sumo/`
    with tarfile.open(fileobj=io.BytesIO(datos)) as tar:
        for miembro in tar.getmembers():
            partes = Path(miembro.name).parts[quitar:]
            if not partes or ".." in partes:
                continue
            miembro.name = str(Path(*partes))
            tar.extract(miembro, destino)
    return destino / "sumo" / "centro_base.sumocfg"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rama", default="origin/tyrone/s1")
    args = ap.parse_args()
    cfg = obtener(args.rama)
    print(f"Escenario en {cfg.relative_to(AQUI.parent)}")
