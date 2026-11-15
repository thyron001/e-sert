"""Corre los escenarios de escenarios.json en paralelo con el Controlador TraCI de Freddy.

Uso (dentro del contenedor van3twin, desde esta carpeta):
    python3 correr_escenarios.py                     # las 8 corridas, en segundo plano
    python3 correr_escenarios.py --uno app50_s1      # una sola corrida (lo que lanza el pool)

Cada corrida usa `Controlador` (proyecto/traci/controlador.py) con dos hooks:
    - kpis.registrar_ocupacion.RegistradorOcupacion: ocupación real cada 60 s;
    - guiado_oraculo.GuiadoOraculo (# MOCK), solo si el escenario tiene app.
Las corridas se lanzan como procesos con subprocess.Popen, como máximo os.cpu_count() - 1 a la
vez; cada una deja su log en ../salidas/<escenario>/correr.log.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent
DIR_CODIGO = DIR.parents[1]
RAIZ = next(p for p in DIR.parents if (p / "proyecto" / "traci").is_dir())
sys.path.insert(0, str(DIR_CODIGO))  # kpis/ de esta semana
sys.path.insert(1, str(RAIZ / "proyecto"))  # traci/ (Controlador de Freddy) y comun/
sys.path.insert(0, str(DIR))


def correr_uno(nombre):
    from guiado_oraculo import GuiadoOraculo
    from kpis.registrar_ocupacion import RegistradorOcupacion
    from traci.controlador import ConfigControlador, Controlador

    esc = next(e for e in json.loads((DIR / "escenarios.json").read_text())["escenarios"]
               if e["escenario"] == nombre)
    config = ConfigControlador(cfg=DIR / esc["sumocfg"], semilla=esc["semilla"],
                               filtro_vehiculos=lambda v: v.startswith("busca_"),
                               seguir_personas=False, etiqueta=nombre)
    registrador = RegistradorOcupacion(nombre, periodo_s=60)
    oraculo = GuiadoOraculo() if esc["porc_app"] > 0 else None
    inicio = time.perf_counter()
    with Controlador(config) as ctrl:
        if oraculo:
            ctrl.agregar_hook(oraculo)
        ctrl.agregar_hook(registrador)
        ctrl.correr(4500)
    registrador.cerrar()
    resumen = {"escenario": nombre, "t_final": ctrl.t, "registros_ocupacion": registrador.registros,
               "segundos": round(time.perf_counter() - inicio, 1)}
    if oraculo:
        resumen.update(asignaciones=oraculo.asignaciones, reasignaciones=oraculo.reasignaciones)
    print(json.dumps(resumen, ensure_ascii=False), flush=True)


def correr_todos(nombres, max_paralelo):
    pendientes, activos, codigos = list(nombres), {}, {}
    while pendientes or activos:
        while pendientes and len(activos) < max_paralelo:
            nombre = pendientes.pop(0)
            carpeta = DIR.parent / "salidas" / nombre
            carpeta.mkdir(parents=True, exist_ok=True)
            log = open(carpeta / "correr.log", "w", encoding="utf-8")
            activos[nombre] = (subprocess.Popen([sys.executable, __file__, "--uno", nombre],
                                                cwd=DIR, stdout=log, stderr=subprocess.STDOUT), log)
            print(f"lanzada {nombre}", flush=True)
        for nombre, (proc, log) in list(activos.items()):
            if proc.poll() is not None:
                log.close()
                codigos[nombre] = proc.returncode
                del activos[nombre]
                print(f"terminó {nombre} (código {proc.returncode})", flush=True)
        time.sleep(5)
    return codigos


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--uno", default=None)
    ap.add_argument("--escenarios", nargs="*", default=None)
    ap.add_argument("--max-paralelo", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()
    if args.uno:
        correr_uno(args.uno)
        return
    nombres = args.escenarios or [e["escenario"] for e in
                                  json.loads((DIR / "escenarios.json").read_text())["escenarios"]]
    codigos = correr_todos(nombres, args.max_paralelo)
    print("FIN", json.dumps(codigos))
    sys.exit(1 if any(codigos.values()) else 0)


if __name__ == "__main__":
    main()
