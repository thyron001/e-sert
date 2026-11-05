"""Corre una configuración `p{pen:02d}_{clf}_s{sem}` con guiado, sesiones y `KPIsSistema` (S3-1).

Usa los escenarios unificados de Tyrone (`proyecto/sumo/escenarios/generar_escenarios.py`, con
`--porc-app`), copiados a `traci/escenario/tyrone/sumo/` (ignorada por git). Reemplaza el MOCK de
`escenario_app.py` de S2-3.

Se ejecuta **dentro del contenedor** `van3twin`, desde `semanas/S3/Freddy/codigo`:

    python3 -m traci.correr_kpis --id p50_rf_s1 --hasta 900            # ejemplo para Tyrone
    python3 -m traci.correr_kpis --id p50_umbral_s1 --hasta 900
    python3 -m traci.correr_kpis --id p50_rf_s1 --hasta 900 --medir-costo 2   # con y sin KPIs
    python3 -m traci.correr_kpis --id p50_rf_s1 --publicar http://<host>:8000

Escribe `traci/salidas_kpi/ejemplo_<id>.json` (resumen; se sube al repo) y, en `traci/salidas/`
(ignorada), `kpis_sesiones_<id>.csv` y `kpis_mapa_<id>.csv`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

from .clasificacion import ClasificadorUsuario, buscar_proyecto
from .controlador import ConfigControlador, Controlador
from .estados import ControlSesiones
from .gps import EmuladorGPS
from .guiado import Guia, RegistroBusqueda
from .kpis_sistema import KPIsSistema
from .peatones import GestorPeatones
from .puente_nucleo import Publicador, PuenteNucleo

AQUI = Path(__file__).resolve().parent
SUMO = AQUI / "escenario" / "tyrone" / "sumo"
SALIDAS = AQUI / "salidas"
SALIDAS_KPI = AQUI / "salidas_kpi"
NOMBRES = {0: "base", 20: "app20", 50: "app50", 80: "app80"}  # los de generar_escenarios.py
PATRON_ID = re.compile(r"^p(\d{2})_(umbral|rf)_s(\d+)$")


def interpretar_id(id_corrida: str) -> tuple:
    """`p50_rf_s1` → `(50, "rf", 1)`."""
    m = PATRON_ID.match(id_corrida)
    if not m:
        raise ValueError(f"ID de corrida inválido: {id_corrida} (se espera p50_rf_s1)")
    return int(m.group(1)), m.group(2), int(m.group(3))


def preparar_escenario(pen: int, semilla: int, sumo: Path = SUMO) -> Path:
    """Copia `proyecto/sumo` (si falta) y genera la demanda del escenario. Devuelve el `.sumocfg`."""
    if not (sumo / "escenarios" / "generar_escenarios.py").exists():
        origen = buscar_proyecto() / "sumo"
        shutil.copytree(origen, sumo, dirs_exist_ok=True, ignore=shutil.ignore_patterns("salidas"))
    nombre = f"{NOMBRES.get(pen, f'app{pen}')}_s{semilla}"
    cfg = sumo / "escenarios" / f"{nombre}.sumocfg"
    if not (sumo / "escenarios" / f"{nombre}.rou.xml").exists() or not cfg.exists():
        subprocess.run([sys.executable, "generar_escenarios.py", "--semillas", str(semilla),
                        "--porcentajes", str(pen)], cwd=sumo / "escenarios", check=True)
    return cfg


def _progreso(ctrl, t: float) -> None:
    if int(t) % 300 == 0 and int(t) != _progreso.ultimo:
        _progreso.ultimo = int(t)
        print(f"progreso t={int(t)} s, autos en red={len(ctrl.vehiculos)}", flush=True)


_progreso.ultimo = -1


def correr(id_corrida: str, hasta: float = 900, con_kpis: bool = True, publicar: Optional[str] = None,
           gps_semilla: int = 1, sufijo: str = "") -> dict:
    """Una corrida. Devuelve el resumen (con `kpis` si `con_kpis`) y el tiempo por paso."""
    pen, clf, semilla = interpretar_id(id_corrida)
    os.environ["ESERT_CLASIFICADOR"] = clf  # lo lee proyecto/ia/inferencia.py al cargar el modelo
    cfg = preparar_escenario(pen, semilla)
    puente = PuenteNucleo(SUMO / "parqueos" / "puestos.csv", semilla=semilla)
    guia = Guia(puente, SUMO / "demanda" / "destinos.csv", "mapa")
    peatones = GestorPeatones(SUMO / "demanda" / "destinos.csv", semilla=semilla, registrar_trayectorias=False)
    clasificador = ClasificadorUsuario()
    sesiones = ControlSesiones(EmuladorGPS(semilla=gps_semilla), SALIDAS, id_corrida, clasificador=clasificador,
                               puente=puente, solo_con_app=True)
    registro = RegistroBusqueda()
    pub_kpi = Publicador(publicar, token=os.environ.get("ESERT_TOKEN_SIM"), ruta="/api/v1/sim/kpi") if publicar else None
    pub_paso = Publicador(publicar, token=os.environ.get("ESERT_TOKEN_SIM")) if publicar else None

    config = ConfigControlador(cfg=cfg, semilla=semilla, etiqueta=f"kpis_{id_corrida}_{int(con_kpis)}")
    kpis = None
    reloj = {"s": 0.0}
    inicio = time.perf_counter()
    try:
        with Controlador(config) as ctrl:
            ctrl.agregar_hook(peatones.on_paso)
            ctrl.agregar_hook(guia.on_paso)
            ctrl.agregar_hook(sesiones.on_paso)
            ctrl.agregar_hook(registro.on_paso)
            if con_kpis:
                kpis = KPIsSistema(ctrl, puente, intervalo_mapa_s=60, publicador_kpi=pub_kpi)
                # Sobrecosto medido en la misma corrida: se cronometran los hooks de KPIs
                # (verdad + KPIs; los dos últimos registrados) y el oyente de cierres.
                ctrl.hooks[-2:] = [_cronometrar(h, reloj) for h in ctrl.hooks[-2:]]
                puente.al_cerrar[:] = [_cronometrar(h, reloj) for h in puente.al_cerrar]
            if pub_paso is not None:
                from .correr_guiado import PublicadorSnapshots
                from .sumo import cargar_sumolib

                net = cargar_sumolib().net.readNet(str(SUMO / "red" / "centro.net.xml"))
                ctrl.agregar_hook(PublicadorSnapshots(pub_paso, sesiones, guia, registro, peatones, net,
                                                      kpis=kpis).on_paso)
            ctrl.agregar_hook(_progreso)
            ctrl.correr(hasta)
            t_final, pasos = ctrl.t, ctrl.pasos
    finally:
        sesiones.cerrar()
        for pub in (pub_kpi, pub_paso):
            if pub is not None:
                pub.cerrar()
    tiempo_real = time.perf_counter() - inicio
    fuentes = dict(sesiones.fuentes)
    salida = {
        "id": id_corrida,
        "porc_app": pen,
        "clasificador_pedido": clf,
        "clasificador_usado": "rf" if fuentes.get("rf") else "umbral",
        "ventanas_por_fuente": fuentes,
        "t_sim_final": t_final,
        "pasos": pasos,
        "tiempo_real_s": round(tiempo_real, 2),
        "ms_por_paso": round(1000 * tiempo_real / max(1, pasos), 3),
        "sesiones_maquina": sesiones.resumen(),
    }
    if kpis is not None:
        resto = tiempo_real - reloj["s"]
        salida["costo_kpis"] = {"s_en_kpis": round(reloj["s"], 3), "s_resto": round(resto, 3),
                                "sobrecosto_pct": round(100 * reloj["s"] / resto, 2)}
        salida["kpis"] = kpis.resumen()
        SALIDAS.mkdir(parents=True, exist_ok=True)
        nombre = id_corrida + sufijo
        kpis.detalle_sesiones().to_csv(SALIDAS / f"kpis_sesiones_{nombre}.csv", index=False)
        kpis.serie_mapa().to_csv(SALIDAS / f"kpis_mapa_{nombre}.csv", index=False)
    return salida


def _cronometrar(funcion, reloj: dict):
    """Envuelve un hook u oyente y suma su tiempo de pared en `reloj["s"]`."""
    def envuelta(*args):
        t0 = time.perf_counter()
        try:
            return funcion(*args)
        finally:
            reloj["s"] += time.perf_counter() - t0
    return envuelta


def _json(obj) -> str:
    """JSON sin `NaN` (no es JSON válido): los NaN se escriben como `null`."""
    def limpiar(x):
        if isinstance(x, float) and math.isnan(x):
            return None
        if isinstance(x, dict):
            return {k: limpiar(v) for k, v in x.items()}
        return x
    return json.dumps(limpiar(obj), indent=2, ensure_ascii=False)


def main(argv: Optional[Sequence[str]] = None) -> dict:
    ap = argparse.ArgumentParser(description="Corrida con KPIs de sistema (S3-1)")
    ap.add_argument("--id", default="p50_rf_s1", help="p{pen:02d}_{umbral|rf}_s{semilla}")
    ap.add_argument("--hasta", type=float, default=900, help="Segundo de simulación final")
    ap.add_argument("--publicar", default=None, help="URL del backend (sin ruta)")
    ap.add_argument("--sufijo", default="", help="Sufijo de los archivos de salida (p. ej. _3600)")
    ap.add_argument("--medir-costo", type=int, default=0, metavar="N",
                    help="Corre N pares (sin KPIs, con KPIs) y escribe costo_<id>.json")
    args = ap.parse_args(argv)
    SALIDAS_KPI.mkdir(parents=True, exist_ok=True)

    if args.medir_costo:
        sin, con = [], []
        for _ in range(args.medir_costo):
            sin.append(correr(args.id, args.hasta, con_kpis=False)["ms_por_paso"])
            con.append(correr(args.id, args.hasta, con_kpis=True)["ms_por_paso"])
        costo = {"id": args.id, "hasta": args.hasta, "ms_por_paso_sin_kpis": sin, "ms_por_paso_con_kpis": con,
                 "sobrecosto_pct": round(100 * (min(con) / min(sin) - 1), 2)}
        (SALIDAS_KPI / f"costo_{args.id}.json").write_text(_json(costo), encoding="utf-8")
        print(_json(costo))
        return costo

    salida = correr(args.id, args.hasta, publicar=args.publicar, sufijo=args.sufijo)
    (SALIDAS_KPI / f"ejemplo_{args.id}{args.sufijo}.json").write_text(_json(salida), encoding="utf-8")
    print(_json(salida))
    return salida


if __name__ == "__main__":
    main()
