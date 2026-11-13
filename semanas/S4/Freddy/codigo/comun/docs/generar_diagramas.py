"""Renderiza cada `comun/docs/diagramas/*.mmd` a PNG y SVG con una versión fija de mermaid-cli (S4-2).

    python comun/docs/generar_diagramas.py                 # todos
    python comun/docs/generar_diagramas.py seq_espejo      # solo uno (sin extensión)
    python comun/docs/generar_diagramas.py --evidencias semanas/S4/Freddy/evidencias

Motor, en este orden (o forzado con `--motor npx|docker`):

1. `npx -y @mermaid-js/mermaid-cli@10.9.1` si hay Node ≥ 18 en la computadora.
2. La imagen oficial `minlag/mermaid-cli:10.9.1` con Docker (misma versión; sirve en el
   contenedor de la materia, que trae Node 12, demasiado viejo).
3. Si no hay ninguno, explica qué instalar y sale con código 2. No se cae a Graphviz: Graphviz
   no interpreta Mermaid, así que el resultado no correspondería al `.mmd`.

PNG a escala 2 (`-s 2`) con fondo blanco y SVG, junto a cada `.mmd`. Con `--evidencias DIR`
copia además `componentes.png` → `s2_arquitectura.png` y `seq_falsa_liberacion_evitada.png` →
`s2_secuencia-cierre.png`.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

VERSION_MERMAID_CLI = "10.9.1"
PAQUETE_NPM = f"@mermaid-js/mermaid-cli@{VERSION_MERMAID_CLI}"
IMAGEN_DOCKER = f"minlag/mermaid-cli:{VERSION_MERMAID_CLI}"
DIAGRAMAS = Path(__file__).resolve().parent / "diagramas"
EVIDENCIAS = {"componentes.png": "s2_arquitectura.png",
              "seq_falsa_liberacion_evitada.png": "s2_secuencia-cierre.png"}


def node_sirve() -> bool:
    """True si hay `node` ≥ 18 y `npx`."""
    if not (shutil.which("node") and shutil.which("npx")):
        return False
    salida = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout
    m = re.match(r"v(\d+)", salida.strip())
    return bool(m and int(m.group(1)) >= 18)


def docker_sirve() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True, text=True).returncode == 0


def elegir_motor(pedido: Optional[str]) -> Optional[str]:
    if pedido:
        return pedido
    if node_sirve():
        return "npx"
    if docker_sirve():
        return "docker"
    return None


def comando(motor: str, entrada: Path, salida: Path) -> List[str]:
    opciones = ["-b", "white"] + (["-s", "2"] if salida.suffix == ".png" else [])
    if motor == "npx":
        return ["npx", "-y", PAQUETE_NPM, "-i", str(entrada), "-o", str(salida), *opciones]
    # Docker: la carpeta de diagramas se monta en /data; el usuario es el de la computadora para
    # que los archivos no queden de root.
    usuario = [] if os.name == "nt" else ["-u", f"{os.getuid()}:{os.getgid()}"]
    return ["docker", "run", "--rm", *usuario, "-v", f"{DIAGRAMAS}:/data", IMAGEN_DOCKER,
            "-i", f"/data/{entrada.name}", "-o", f"/data/{salida.name}", *opciones]


def renderizar(motor: str, mmd: Path) -> List[Path]:
    hechos = []
    for ext in (".png", ".svg"):
        salida = mmd.with_suffix(ext)
        r = subprocess.run(comando(motor, mmd, salida), capture_output=True, text=True)
        if r.returncode != 0 or not salida.is_file():
            raise RuntimeError(f"{mmd.name} → {ext}: {(r.stderr or r.stdout).strip()[-800:]}")
        hechos.append(salida)
    return hechos


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("nombres", nargs="*", help="diagramas sin extensión (por defecto, todos)")
    ap.add_argument("--motor", choices=["npx", "docker"], default=None)
    ap.add_argument("--evidencias", type=Path, default=None, help="carpeta evidencias/ de la sesión")
    args = ap.parse_args(argv)

    archivos = sorted(DIAGRAMAS.glob("*.mmd"))
    if args.nombres:
        archivos = [a for a in archivos if a.stem in set(args.nombres)]
    if not archivos:
        print(f"No hay .mmd que renderizar en {DIAGRAMAS}")
        return 1
    motor = elegir_motor(args.motor)
    if motor is None:
        print("No puedo renderizar: hace falta Node ≥ 18 (para `npx`) o Docker.\n"
              f"  - Con Node:   npm i -g {PAQUETE_NPM}   (o deja que npx lo descargue)\n"
              f"  - Con Docker: docker pull {IMAGEN_DOCKER}\n"
              "Los .mmd se pueden ver mientras tanto en https://mermaid.live o en la vista previa de GitHub.")
        return 2
    print(f"mermaid-cli {VERSION_MERMAID_CLI} con {motor}: {len(archivos)} diagramas")
    errores = 0
    for mmd in archivos:
        try:
            hechos = renderizar(motor, mmd)
            print(f"  ok  {mmd.name} → {', '.join(h.name for h in hechos)}")
        except RuntimeError as err:
            errores += 1
            print(f"  ERROR {err}")
    if args.evidencias:
        args.evidencias.mkdir(parents=True, exist_ok=True)
        for origen, destino in EVIDENCIAS.items():
            if (DIAGRAMAS / origen).is_file():
                shutil.copyfile(DIAGRAMAS / origen, args.evidencias / destino)
                print(f"  evidencia {args.evidencias / destino}")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
