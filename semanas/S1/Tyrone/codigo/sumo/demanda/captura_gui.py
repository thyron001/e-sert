"""Captura de sumo-gui del escenario base en la hora pico (evidencia s3_escenario-base.png).

Uso (dentro del contenedor van3twin, desde esta carpeta):
    python3 captura_gui.py --carpeta ../salidas/base_1 [--t 2700] [--salida ruta.png]

Corre sumo-gui con centro_base.sumocfg y la demanda de la carpeta hasta el instante --t,
colorea los vehículos por clase (busca naranja, paso azul, fondo gris) y guarda la captura
con traci.gui.screenshot. No escribe salidas de simulación.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import sumolib  # noqa: E402
import traci  # noqa: E402

DIR = Path(__file__).resolve().parent
DIR_SUMO = DIR.parent
COLORES = {"busca": (255, 140, 0, 255), "paso": (30, 99, 214, 255), "fondo": (150, 150, 150, 255)}
# Zona central (lat/lon) que se muestra: alrededor del Parque Calderón
VISTA = (-2.9005, -79.0080, -2.8945, -78.9995)
# Vehículos exagerados para que se vean a esta escala
VISTA_GUI = DIR / "vista_gui.xml"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--carpeta", default=str(DIR_SUMO / "salidas" / "base_1"))
    ap.add_argument("--t", type=float, default=2700.0)
    ap.add_argument("--salida", default=str(DIR_SUMO / "salidas" / "s3_escenario-base.png"))
    args = ap.parse_args()
    carpeta = Path(args.carpeta).resolve()
    net = sumolib.net.readNet(str(DIR_SUMO / "red" / "centro.net.xml"))
    traci.start(["sumo-gui", "-c", str(DIR_SUMO / "centro_base.sumocfg"),
                 "--route-files", str(carpeta / "demanda.rou.xml"),
                 "--tripinfo-output", "/dev/null", "--stop-output", "/dev/null",
                 "--vehroute-output", "/dev/null", "--emission-output", "/dev/null",
                 "--statistic-output", "/dev/null",
                 "--gui-settings-file", str(VISTA_GUI),
                 "--start", "--quit-on-end", "--delay", "0", "--window-size", "1600,1200"])
    vista = traci.gui.DEFAULT_VIEW
    s, w, n, e = VISTA
    x0, y0 = net.convertLonLat2XY(w, s)
    x1, y1 = net.convertLonLat2XY(e, n)
    traci.gui.setBoundary(vista, x0, y0, x1, y1)
    while traci.simulation.getTime() < args.t:
        traci.simulationStep()
        for vid in traci.simulation.getDepartedIDList():
            clase = vid.split("_")[0]
            if clase in COLORES:
                traci.vehicle.setColor(vid, COLORES[clase])
    traci.gui.screenshot(vista, str(Path(args.salida).resolve()))
    traci.simulationStep()
    traci.close()
    print(f"Captura sumo-gui (t={args.t:.0f} s) -> {args.salida}")


if __name__ == "__main__":
    main()
