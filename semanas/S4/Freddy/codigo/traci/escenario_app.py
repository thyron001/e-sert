"""Escenarios con app para S2-3: `app50_s1` (50 % de autos de búsqueda con app) y `base_s1` (sin app).

# MOCK: Tyrone prepara estos escenarios con `--porc-app` en `origin/tyrone/s2` (S2-3), que todavía
no existe. Mientras tanto se parte de la demanda base de `proyecto/sumo/demanda/demanda.rou.xml`
y se pone `con_app=1` al 50 % de los vehículos `busca` (semilla fija). Los dos escenarios tienen
las mismas llegadas y las mismas estadías; solo cambia quién tiene app.

Se escribe dentro de `traci/escenario/tyrone/sumo/` (copia local, ignorada por git):

    python3 -m traci.escenario_app
"""

from __future__ import annotations

import argparse
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Sequence

AQUI = Path(__file__).resolve().parent
SUMO = AQUI / "escenario" / "tyrone" / "sumo"
SEMILLA_APP = 1
PORC_APP = 0.5


def _clase(vehiculo: ET.Element) -> Optional[str]:
    for p in vehiculo.findall("param"):
        if p.get("key") == "clase":
            return p.get("value")
    return None


def _poner_app(vehiculo: ET.Element, valor: str) -> None:
    for p in vehiculo.findall("param"):
        if p.get("key") == "con_app":
            p.set("value", valor)
            return
    ET.SubElement(vehiculo, "param", key="con_app", value=valor)


def generar(sumo: Path = SUMO, porc_app: float = PORC_APP, semilla: int = SEMILLA_APP) -> Path:
    """Escribe las demandas y los `.sumocfg` de `app50_s1` y `base_s1`. Devuelve el de app.

    `base_s1` y `app50_s1` salen de la misma demanda corregida; solo difiere `con_app`.
    """
    demanda = sumo / "demanda"
    fuente = ET.parse(demanda / "demanda.rou.xml").getroot()
    busca = [v for v in fuente if v.tag in ("trip", "vehicle") and _clase(v) == "busca"]
    for v in busca:
        _poner_app(v, "0")
    ET.ElementTree(fuente).write(demanda / "base_s1.rou.xml", encoding="utf-8", xml_declaration=True)

    rng = random.Random(semilla)
    con_app = set(rng.sample(range(len(busca)), round(porc_app * len(busca))))
    for i, v in enumerate(busca):
        _poner_app(v, "1" if i in con_app else "0")
    ET.ElementTree(fuente).write(demanda / "app50_s1.rou.xml", encoding="utf-8", xml_declaration=True)

    base = (sumo / "centro_base.sumocfg").read_text(encoding="utf-8")
    cfg_app = sumo / "app50_s1.sumocfg"
    cfg_app.write_text(base.replace("demanda/demanda.rou.xml", "demanda/app50_s1.rou.xml")
                           .replace("salidas/base_1/", "salidas/app50_s1/"), encoding="utf-8")
    cfg_base = sumo / "base_s1.sumocfg"
    cfg_base.write_text(base.replace("demanda/demanda.rou.xml", "demanda/base_s1.rou.xml")
                            .replace("salidas/base_1/", "salidas/base_s1/"), encoding="utf-8")
    n_app = sum(1 for v in busca if _valor(v, "con_app") == "1")
    print(f"busca={len(busca)} con_app=1: {n_app} ({100 * n_app / max(1, len(busca)):.1f} %)")
    return cfg_app


def _valor(vehiculo: ET.Element, clave: str) -> Optional[str]:
    for p in vehiculo.findall("param"):
        if p.get("key") == clave:
            return p.get("value")
    return None


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Genera app50_s1 y base_s1 (MOCK de --porc-app)")
    ap.add_argument("--porc-app", type=float, default=PORC_APP)
    ap.add_argument("--semilla", type=int, default=SEMILLA_APP)
    args = ap.parse_args(argv)
    print(generar(porc_app=args.porc_app, semilla=args.semilla))


if __name__ == "__main__":
    main()
