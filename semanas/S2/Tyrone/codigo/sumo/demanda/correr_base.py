"""Corre el escenario base con una o varias semillas y analiza cada corrida.

Uso (dentro del contenedor van3twin, desde esta carpeta):
    python3 correr_base.py --semillas 1 2 [--veh-hora 1800] [--ocupacion-fondo 0.80]
                           [--escenario base]

Por cada semilla: genera la demanda en salidas/<escenario>_<semilla>/demanda.rou.xml, corre
sumo -c centro_base.sumocfg cambiando la demanda, la semilla y las rutas de salida, y deja
resumen.json con analizar_base.py. Las corridas de distintas semillas van en paralelo.
"""
import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DIR = Path(__file__).resolve().parent
DIR_SUMO = DIR.parent
SALIDAS = DIR_SUMO / "salidas"


def correr(semilla, args):
    nombre = f"{args.escenario}_{semilla}"
    carpeta = SALIDAS / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    rel = f"salidas/{nombre}"
    subprocess.run([sys.executable, str(DIR / "generar_demanda.py"), "--semilla", str(semilla),
                    "--veh-hora", str(args.veh_hora), "--porc-paso", str(args.porc_paso),
                    "--ocupacion-fondo", str(args.ocupacion_fondo),
                    "--salida", str(carpeta / "demanda.rou.xml")],
                   check=True, capture_output=True, text=True)
    cmd = ["sumo", "-c", "centro_base.sumocfg", "--seed", str(semilla),
           "--route-files", f"{rel}/demanda.rou.xml",
           "--tripinfo-output", f"{rel}/tripinfo.xml",
           "--stop-output", f"{rel}/stops.xml",
           "--vehroute-output", f"{rel}/vehroutes.xml",
           "--emission-output", f"{rel}/emisiones.xml",
           "--statistic-output", f"{rel}/estadisticas.xml"]
    with open(carpeta / "sumo.log", "w", encoding="utf-8") as log:
        res = subprocess.run(cmd, cwd=DIR_SUMO, stdout=log, stderr=subprocess.STDOUT)
    if res.returncode != 0:
        return nombre, f"sumo terminó con código {res.returncode} (ver {rel}/sumo.log)"
    res = subprocess.run([sys.executable, str(DIR / "analizar_base.py"), str(carpeta)],
                         capture_output=True, text=True)
    return nombre, (res.stdout or res.stderr).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--semillas", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--veh-hora", type=float, default=1800.0)
    ap.add_argument("--porc-paso", type=float, default=40.0)
    ap.add_argument("--ocupacion-fondo", type=float, default=0.80)
    ap.add_argument("--escenario", default="base")
    args = ap.parse_args()
    with ThreadPoolExecutor(max_workers=len(args.semillas)) as ex:
        for nombre, texto in ex.map(lambda s: correr(s, args), args.semillas):
            print(texto, flush=True)


if __name__ == "__main__":
    main()
