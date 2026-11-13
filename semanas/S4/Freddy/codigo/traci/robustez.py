"""Robustez del GPS y del teléfono (S3-2): rejilla de corridas con 50 % de autos con app.

Familias (cada una con clasificador `umbral` y `rf`, semillas 1 y 2, 1 800 s simulados):

- `perdida`: pérdida independiente `p_perdida` ∈ {0,02; 0,10; 0,30} (σ = 5 m);
- `rafaga`: ráfagas Gilbert-Elliott de 30, 60 y 120 s de media, 30 % del tiempo sin señal;
- `ruido`: `sigma_m` ∈ {5, 15, 30} m (multitrayecto);
- `apagado`: 10 % de los teléfonos se apagan al pasar a `A_PIE` (condición base de GPS);
- `sin_politica`: ráfagas de 60 s **sin** la política de datos pobres (control de la política).

La condición base (p = 0,02, σ = 5 m) es la misma en `perdida` y `ruido`: se corre una vez y se
escribe en las dos familias. Cada corrida va en su propio proceso (`multiprocessing`, contexto
`spawn`, `maxtasksperchild=1`), porque `libsumo` es uno por proceso.

Se ejecuta **dentro del contenedor** `van3twin`, desde `semanas/S3/Freddy/codigo`, en segundo plano:

    python3 -m traci.robustez --procesos 6
    python3 -m traci.robustez --solo-contar     # cuántas filas tiene robustez.csv

Escribe una fila por corrida en `traci/salidas_kpi/robustez.csv` a medida que terminan; si se
relanza, salta las que ya están.
"""

from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .correr_kpis import SALIDAS_KPI, preparar_escenario

CSV = SALIDAS_KPI / "robustez.csv"
HASTA_S = 1800
SEMILLAS = (1, 2)
CLASIFICADORES = ("umbral", "rf")
BASE = {"sigma_m": 5.0, "p_perdida": 0.02, "rafaga_s": None, "frac_apagado": 0.0, "politica": True}

COLUMNAS = ["familia", "valor", "clasificador", "clasificador_usado", "semilla", "sigma_m", "p_perdida",
            "rafaga_s", "frac_apagado", "politica", "sesiones", "n_sesiones", "n_falsas", "falsas_lib_100",
            "falsas_por_100_llegadas", "retardo_cierre_mediana_s", "retardo_cierre_p90_s", "sin_cierre",
            "ventanas_retenidas", "falsas_con_datos_pobres", "apagados_efectivos", "marcadas_sin_senal",
            "esperando_tope_al_final", "error_proyectado_medio_usd", "falsas_entre_apagados",
            "tiempo_real_s"]


def condiciones() -> List[dict]:
    """Condiciones únicas de GPS/teléfono; cada una sabe en qué familias se reporta."""
    conds: Dict[tuple, dict] = {}

    def agregar(familia: str, valor, **cambios):
        c = {**BASE, **cambios}
        clave = (c["sigma_m"], c["p_perdida"], c["rafaga_s"], c["frac_apagado"], c["politica"])
        conds.setdefault(clave, {**c, "familias": []})["familias"].append((familia, valor))

    for p in (0.02, 0.10, 0.30):
        agregar("perdida", p, p_perdida=p)
    for r in (30, 60, 120):
        agregar("rafaga", r, rafaga_s=float(r))
    for s in (5, 15, 30):
        agregar("ruido", s, sigma_m=float(s))
    agregar("apagado", 0.10, frac_apagado=0.10)
    agregar("sin_politica", 60, rafaga_s=60.0, politica=False)
    return list(conds.values())


def tareas() -> List[dict]:
    return [{**c, "clasificador": clf, "semilla": sem} for c in condiciones()
            for clf in CLASIFICADORES for sem in SEMILLAS]


def _clave(t: dict) -> str:
    return f"{t['clasificador']}_s{t['semilla']}_{t['sigma_m']}_{t['p_perdida']}_{t['rafaga_s']}_" \
           f"{t['frac_apagado']}_{int(t['politica'])}"


def correr_tarea(t: dict) -> List[dict]:
    """Una corrida (en un proceso nuevo). Devuelve una fila por familia en la que se reporta."""
    from .correr_kpis import correr

    salida = correr(f"p50_{t['clasificador']}_s{t['semilla']}", HASTA_S, gps_semilla=t["semilla"],
                    sufijo=f"_rob_{_clave(t)}", sigma_m=t["sigma_m"], p_perdida=t["p_perdida"],
                    rafaga_s=t["rafaga_s"], frac_apagado=t["frac_apagado"],
                    politica_datos_pobres=t["politica"], libsumo=True, guardar_csv=False)
    k, m, ap = salida["kpis"], salida["sesiones_maquina"], salida.get("apagados", {})
    comun = {
        "clasificador": t["clasificador"], "clasificador_usado": salida["clasificador_usado"],
        "semilla": t["semilla"], "sigma_m": t["sigma_m"], "p_perdida": t["p_perdida"],
        "rafaga_s": t["rafaga_s"] or "", "frac_apagado": t["frac_apagado"], "politica": int(t["politica"]),
        "sesiones": m["sesiones"], "n_sesiones": k["n_sesiones"], "n_falsas": k["n_falsas"],
        "falsas_lib_100": k["falsas_lib_100"], "falsas_por_100_llegadas": m["falsas_por_100_sesiones"],
        "retardo_cierre_mediana_s": k["retardo_cierre_mediana_s"], "retardo_cierre_p90_s": k["retardo_cierre_p90_s"],
        "sin_cierre": k["sin_cierre"], "ventanas_retenidas": m["ventanas_retenidas"],
        "falsas_con_datos_pobres": m["falsas_con_datos_pobres"], "apagados_efectivos": m["apagados_efectivos"],
        "marcadas_sin_senal": m["marcadas_sin_senal"], "esperando_tope_al_final": m["esperando_tope_al_final"],
        "error_proyectado_medio_usd": ap.get("error_proyectado_medio_usd", ""),
        "falsas_entre_apagados": ap.get("falsas_entre_apagados", ""),
        "tiempo_real_s": salida["tiempo_real_s"],
    }
    return [{"familia": f, "valor": v, **comun} for f, v in t["familias"]]


def hechas() -> set:
    """Claves de las corridas que ya están en el CSV (para reanudar)."""
    if not CSV.exists():
        return set()
    with CSV.open(encoding="utf-8") as f:
        return {_clave({"clasificador": r["clasificador"], "semilla": int(r["semilla"]),
                        "sigma_m": float(r["sigma_m"]), "p_perdida": float(r["p_perdida"]),
                        "rafaga_s": float(r["rafaga_s"]) if r["rafaga_s"] else None,
                        "frac_apagado": float(r["frac_apagado"]), "politica": bool(int(r["politica"]))})
                for r in csv.DictReader(f)}


def contar() -> dict:
    total = len(tareas())
    filas = 0
    if CSV.exists():
        with CSV.open(encoding="utf-8") as f:
            filas = sum(1 for _ in csv.DictReader(f))
    return {"corridas_hechas": len(hechas()), "corridas_total": total, "filas_csv": filas}


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Rejilla de robustez del GPS (S3-2)")
    ap.add_argument("--procesos", type=int, default=4)
    ap.add_argument("--solo-contar", action="store_true")
    args = ap.parse_args(argv)
    if args.solo_contar:
        print(contar())
        return
    for sem in SEMILLAS:  # los escenarios se generan antes, no en paralelo
        preparar_escenario(50, sem)
    ya = hechas()
    pendientes = [t for t in tareas() if _clave(t) not in ya]
    print(f"corridas: {len(pendientes)} pendientes de {len(tareas())}", flush=True)
    SALIDAS_KPI.mkdir(parents=True, exist_ok=True)
    nuevo = not CSV.exists()
    inicio = time.time()
    ctx = mp.get_context("spawn")
    with CSV.open("a", newline="", encoding="utf-8") as f, \
            ctx.Pool(args.procesos, maxtasksperchild=1) as pool:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        for filas in pool.imap_unordered(correr_tarea, pendientes):
            for fila in filas:
                w.writerow(fila)
            f.flush()
            print(f"{time.strftime('%H:%M:%S')} fin {filas[0]['clasificador']} s{filas[0]['semilla']} "
                  f"{[fi['familia'] + '=' + str(fi['valor']) for fi in filas]} "
                  f"falsas/100={filas[0]['falsas_lib_100']} ({time.time() - inicio:.0f} s)", flush=True)
    print(contar(), flush=True)


if __name__ == "__main__":
    sys.exit(main())
