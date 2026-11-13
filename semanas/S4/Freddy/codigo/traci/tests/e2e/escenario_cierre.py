"""Corrida mínima con SUMO para la prueba de cierre automático (S4-1). Se ejecuta en `van3twin`:

    python3 -m traci.tests.e2e.escenario_cierre --salida traci/salidas/cierre.json

Cinco autos de búsqueda de la demanda base (estadías de 4-8 min), todos con peatones de
diligencia que se alejan a pie y vuelven. Las sesiones se abren y cierran en el núcleo
(`PuenteNucleo`) y `KPIsSistema` marca cada cierre: `falsa` si el auto seguía estacionado y
`retardo_cierre_s` = cierre − salida real del parkingArea.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ESTADIAS_S = (240, 300, 360, 420, 480)


def _clase(trip) -> str:
    return next((p.get("value") for p in trip.findall("param") if p.get("key") == "clase"), "")


def escenario_mini(sumo: Path, carpeta: Path, n: int = 5, fin_s: int = 16000) -> Path:
    """`.sumocfg` con `n` autos de búsqueda de `demanda/demanda.rou.xml` y estadías cortas."""
    raiz = ET.parse(sumo / "demanda" / "demanda.rou.xml").getroot()
    busca = [v for v in raiz.findall("trip") if _clase(v) == "busca"][:n]
    rutas = ET.Element("routes")
    rutas.append(raiz.find("vType"))
    for trip, estadia in zip(busca, ESTADIAS_S):
        trip.find("stop").set("duration", str(estadia))
        rutas.append(trip)
    (carpeta / "demanda").mkdir(parents=True, exist_ok=True)
    ET.ElementTree(rutas).write(carpeta / "demanda" / "mini.rou.xml")
    cfg = carpeta / "mini.sumocfg"
    cfg.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{sumo / 'red' / 'centro.net.xml'}"/>
        <route-files value="{carpeta / 'demanda' / 'mini.rou.xml'}"/>
        <additional-files value="{sumo / 'red' / 'centro.poly.xml'},{sumo / 'parqueos' / 'parqueos.add.xml'}"/>
    </input>
    <time><begin value="0"/><end value="{fin_s}"/></time>
    <processing><time-to-teleport value="300"/><ignore-route-errors value="true"/></processing>
    <report><no-step-log value="true"/></report>
</configuration>
""", encoding="utf-8")
    return cfg


def correr(hasta_s: float = 3000) -> dict:
    from traci.clasificacion import buscar_proyecto
    from traci.controlador import ConfigControlador, Controlador
    from traci.correr_kpis import SUMO
    from traci.estados import ControlSesiones
    from traci.gps import EmuladorGPS
    from traci.kpis_sistema import KPIsSistema
    from traci.peatones import GestorPeatones
    from traci.puente_nucleo import PuenteNucleo

    if not (SUMO / "parqueos" / "puestos.csv").exists():
        shutil.copytree(buscar_proyecto() / "sumo", SUMO, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("salidas"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = escenario_mini(SUMO, tmp)
        puente = PuenteNucleo(SUMO / "parqueos" / "puestos.csv", semilla=1)
        peatones = GestorPeatones(SUMO / "demanda" / "destinos.csv", semilla=1, p_regreso_corto=0.0,
                                  p_espera_en_auto=0.0)
        sesiones = ControlSesiones(EmuladorGPS(semilla=1), tmp, "e2e_cierre", puente=puente)
        try:
            with Controlador(ConfigControlador(cfg=cfg, etiqueta="s4_e2e_cierre")) as ctrl:
                ctrl.agregar_hook(peatones.on_paso)
                ctrl.agregar_hook(sesiones.on_paso)
                kpis = KPIsSistema(ctrl, puente, intervalo_mapa_s=60)
                ctrl.correr(hasta_s)
                parados = [v for v in ctrl.traci.vehicle.getIDList() if ctrl.traci.vehicle.isStoppedParking(v)]
                filas = kpis._filas()
        finally:
            sesiones.cerrar()

    def limpio(x):
        return None if isinstance(x, float) and math.isnan(x) else x

    return {
        "peatones": peatones.resumen(),
        "sesiones_maquina": sesiones.resumen(),
        "abiertas_al_final": len(puente.abiertas),
        "parados_al_final": parados,
        "cierres": [{k: limpio(f.get(k)) for k in ("sesion_id", "veh", "motivo", "falsa", "t_fin",
                                                   "t_llegada_real", "t_salida_real", "retardo_cierre_s")}
                    for f in filas],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--hasta", type=float, default=3000)
    args = ap.parse_args()
    r = correr(args.hasta)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(r, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("peatones", "abiertas_al_final")}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
