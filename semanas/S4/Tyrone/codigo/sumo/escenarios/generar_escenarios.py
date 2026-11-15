"""Genera los escenarios comparables {base,app20,app50,app80}_s{1,2}.

Uso (dentro del contenedor van3twin, desde esta carpeta):
    python3 generar_escenarios.py [--semillas 1 2] [--porcentajes 0 20 50 80]

Por cada semilla y porcentaje de app escribe <escenario>_s<N>.rou.xml (con
generar_demanda.generar y --porc-app) y <escenario>_s<N>.sumocfg (salidas en
../salidas/<escenario>_s<N>/), más escenarios.json con la semilla, el porcentaje, los conteos
y el SHA-256 de cada demanda. Comprueba que, dentro de una semilla, los 4 escenarios tienen los
mismos vehículos con las mismas horas de salida (solo cambia con_app), y que los usuarios con
app están anidados: app20 ⊂ app50 ⊂ app80.
"""
import argparse
import hashlib
import json
import re
import sys
from argparse import Namespace
from pathlib import Path

DIR = Path(__file__).resolve().parent
DIR_SUMO = DIR.parent
sys.path.insert(0, str(DIR_SUMO / "demanda"))
import generar_demanda as gd  # noqa: E402

NOMBRES = {0: "base", 20: "app20", 50: "app50", 80: "app80"}
PATRON_VEH = re.compile(r'<(?:trip|vehicle) id="([^"]+)"[^>]*depart="([^"]+)"')

CFG = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Escenario {nombre}: semilla {semilla}, {porc} % de buscadores con app (generar_escenarios.py) -->
<configuration>
    <input>
        <net-file value="../red/centro.net.xml"/>
        <route-files value="{nombre}.rou.xml"/>
        <additional-files value="../red/centro.poly.xml,../parqueos/parqueos.add.xml,../demanda/rerouters.add.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{fin}"/>
    </time>
    <output>
        <tripinfo-output value="../salidas/{nombre}/tripinfo.xml"/>
        <stop-output value="../salidas/{nombre}/stops.xml"/>
        <stop-output.write-unfinished value="true"/>
        <vehroute-output value="../salidas/{nombre}/vehroutes.xml"/>
        <vehroute-output.exit-times value="true"/>
        <vehroute-output.route-length value="true"/>
        <vehroute-output.write-unfinished value="true"/>
        <emission-output value="../salidas/{nombre}/emisiones.xml"/>
        <statistic-output value="../salidas/{nombre}/estadisticas.xml"/>
    </output>
    <emissions>
        <device.emissions.probability value="1"/>
        <device.emissions.period value="10"/>
    </emissions>
    <processing>
        <time-to-teleport value="300"/>
        <ignore-route-errors value="true"/>
    </processing>
    <random_number>
        <seed value="{semilla}"/>
    </random_number>
    <report>
        <no-step-log value="true"/>
        <duration-log.statistics value="true"/>
    </report>
</configuration>
"""


def vehiculos_y_app(ruta):
    """{id: depart} de toda la demanda y el conjunto de ids con con_app=1."""
    salidas, con_app, actual = {}, set(), None
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        m = PATRON_VEH.search(linea)
        if m:
            actual = m.group(1)
            salidas[actual] = m.group(2)
        elif '<param key="con_app" value="1"/>' in linea and actual:
            con_app.add(actual)
    return salidas, con_app


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--semillas", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--porcentajes", type=int, nargs="+", default=[0, 20, 50, 80])
    args = ap.parse_args()
    net = gd.sumolib.net.readNet(str(gd.RED))
    escenarios, errores = [], []
    for semilla in args.semillas:
        referencia, previos = None, set()
        for porc in sorted(args.porcentajes):
            nombre = f"{NOMBRES.get(porc, f'app{porc}')}_s{semilla}"
            rou = DIR / f"{nombre}.rou.xml"
            p = Namespace(veh_hora=1800.0, porc_paso=40.0, duracion_s=3600, warmup_s=900,
                          ocupacion_fondo=0.80, semilla=semilla, porc_app=float(porc),
                          salida=str(rou))
            info = gd.generar(net, p)
            (DIR / f"{nombre}.sumocfg").write_text(
                CFG.format(nombre=nombre, semilla=semilla, porc=porc,
                           fin=p.warmup_s + p.duracion_s), encoding="utf-8")
            salidas, con_app = vehiculos_y_app(rou)
            if referencia is None:
                referencia = salidas
            elif salidas != referencia:
                errores.append(f"{nombre}: la demanda no coincide con la del 0 % de la semilla {semilla}")
            if not previos <= con_app:
                errores.append(f"{nombre}: los usuarios con app no contienen a los del escenario anterior")
            previos = con_app
            escenarios.append({
                "escenario": nombre, "semilla": semilla, "porc_app": porc,
                "rou": rou.name, "sumocfg": f"{nombre}.sumocfg", "salidas": f"../salidas/{nombre}",
                "vehiculos": len(salidas), "buscadores": info["busca"], "con_app": len(con_app),
                "sha256_demanda": hashlib.sha256(rou.read_bytes()).hexdigest(),
            })
            print(f"{nombre}: {len(salidas)} vehículos, {info['busca']} buscan, "
                  f"{len(con_app)} con app", flush=True)
    resumen = {"escenarios": escenarios, "comprobaciones": {
        "demanda_identica_por_semilla": not any("no coincide" in e for e in errores),
        "usuarios_app_anidados": not any("contienen" in e for e in errores),
        "errores": errores}}
    (DIR / "escenarios.json").write_text(json.dumps(resumen, indent=1, ensure_ascii=False),
                                         encoding="utf-8")
    print("comprobaciones:", json.dumps(resumen["comprobaciones"], ensure_ascii=False))
    if errores:
        sys.exit(1)


if __name__ == "__main__":
    main()
