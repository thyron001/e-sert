"""Corre el escenario base con peatones de diligencia y sesiones de parqueo (S2, sesión 2).

Se ejecuta **dentro del contenedor** `van3twin`, desde `semanas/S2/Freddy/codigo`:

    python3 -m traci.correr_sesiones --hasta 1800                  # 30 min, en segundo plano
    python3 -m traci.correr_sesiones --hasta 1800 --gui            # sumo-gui por VNC (:5901)

Escribe en `traci/salidas/` (ignorada por git): transiciones, ventanas, falsas liberaciones,
trayectorias de peatones y un `resumen_<escenario>.json`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from .controlador import ConfigControlador, Controlador
from .estados import ControlSesiones
from .gps import EmuladorGPS
from .peatones import GestorPeatones

AQUI = Path(__file__).resolve().parent
CFG_POR_DEFECTO = AQUI / "escenario" / "tyrone" / "sumo" / "centro_base.sumocfg"
SALIDAS = AQUI / "salidas"


def main(argv: Optional[Sequence[str]] = None) -> dict:
    ap = argparse.ArgumentParser(description="Peatones y sesiones de parqueo sobre el escenario base")
    ap.add_argument("--cfg", type=Path, default=CFG_POR_DEFECTO, help="Archivo .sumocfg")
    ap.add_argument("--gui", action="store_true", help="Usa sumo-gui (pantalla :99, VNC 5901)")
    ap.add_argument("--hasta", type=float, default=1800, help="Segundo de simulación final")
    ap.add_argument("--semilla", type=int, default=1, help="Semilla de SUMO y de los peatones")
    ap.add_argument("--gps-semilla", type=int, default=1, help="Semilla del ruido del GPS")
    ap.add_argument("--p-regreso-corto", type=float, default=0.15)
    ap.add_argument("--p-espera-en-auto", type=float, default=0.10)
    args, extra = ap.parse_known_args(argv)

    cfg = args.cfg.resolve()
    escenario = cfg.stem
    carpeta = cfg.parent
    gps = EmuladorGPS(semilla=args.gps_semilla)
    peatones = GestorPeatones(carpeta / "demanda" / "destinos.csv", semilla=args.semilla,
                              p_regreso_corto=args.p_regreso_corto,
                              p_espera_en_auto=args.p_espera_en_auto, registrar_trayectorias=True)
    sesiones = ControlSesiones(gps, SALIDAS, escenario)
    config = ConfigControlador(cfg=cfg, gui=args.gui, semilla=args.semilla, args_extra=extra,
                               etiqueta=f"s2_{escenario}")
    try:
        with Controlador(config) as ctrl:
            ctrl.agregar_hook(peatones.on_paso)
            ctrl.agregar_hook(sesiones.on_paso)
            ctrl.correr(args.hasta)
            t_final = ctrl.t
        peatones.escribir_trayectorias(SALIDAS / f"trayectorias_{escenario}.csv")
    finally:
        sesiones.cerrar()

    resumen = {
        "escenario": escenario,
        "t_sim_final": t_final,
        "peatones": peatones.resumen(),
        "sesiones": sesiones.resumen(),
    }
    (SALIDAS / f"resumen_{escenario}.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False),
                                                       encoding="utf-8")
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    return resumen


if __name__ == "__main__":
    main()
