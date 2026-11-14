"""Corrida final de experimentos (S4-2): matriz 4 × 2 × 5 con `rf_final` y el controlador de `proyecto/traci/`.

Se ejecuta **dentro del contenedor** `van3twin`, desde `semanas/S4/Tyrone/codigo` (o `proyecto/`):

    python3 -m kpis.corrida_final                  # corre lo que falte y escribe manifiesto y resumen
    python3 -m kpis.corrida_final --procesos 4
    python3 -m kpis.corrida_final --solo-resumen   # sin SUMO: recalcula resumen.csv/.md y manifiesto

Matriz: penetración {0, 20, 50, 80} % × clasificador {umbral, rf_final} × semillas {1…5}. El 0 % es
la búsqueda a ciegas y corre una vez por semilla (`p00_umbral_s<N>`): 5 + 3·2·5 = 35 corridas.
Además, 5 corridas de sensibilidad `p50_rf_s<N>_oraculo` (guiado con la ocupación real de SUMO).

Encima del ejecutor de S3 (`kpis.experimentos` y `kpis.correr_una`), sin duplicarlo:

- cada corrida en `kpis/resultados/final/<id>/kpis.json` (`<id>` = `p50_rf_s3`); si existe, se salta;
- si `kpis/resultados/corridas/<id>.json` (matriz de S3-1) tiene el **mismo `hash_config`** (mismo
  cfg, red, parqueos, demanda y modelo), se reutiliza y se marca `"origen": "S3-1 (mismo hash)"`;
- las corridas nuevas van en paralelo con `ProcessPoolExecutor(max_workers=cpu−1)`; cada tarea abre
  un intérprete nuevo (TraCI/libsumo guardan estado por proceso y Python 3.10 no tiene
  `max_tasks_per_child`), con su propio puerto TraCI y su carpeta de salidas;
- las salidas crudas de SUMO quedan en `sumo/salidas/final/` (ignoradas); se versionan los `kpis.json`,
  `resumen.csv`, `resumen.md` y `manifiesto.json`.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parent
sys.path.insert(0, str(CODIGO))

from kpis import experimentos as ex  # noqa: E402
from kpis.correr_una import nombre_escenario, raiz_repo, sha256_archivo  # noqa: E402

FINAL = AQUI / "resultados" / "final"
MATRIZ = {
    "escenario": "centro_base",
    "penetracion": [0, 20, 50, 80],
    "clasificador": ["umbral", "rf"],      # "rf" = rf_final de Pablo (origin/pablo/s4, congelado)
    "semillas": [1, 2, 3, 4, 5],
    "duracion_s": 4500,
    "warmup_s": 900,
    "modelo_rf": "kpis/externo/rf_final.plano.npz",
    "modelo_rf_joblib": "kpis/externo/ia/modelos/rf_final.joblib",
    "libsumo": True,
    "timeout_corrida_s": 3600,
    "veh_hora": 1800,                       # --veh-hora calibrado en S1 (ocupación 85–95 %)
}
NOMBRE_CLF = {"umbral": "umbral", "rf": "rf_final"}
# Sensibilidad (no es parte de las 35): el guiado ve la ocupación REAL de SUMO (`Guia` con fuente
# "verdad"). El mapa del sistema solo conoce a los usuarios con app; el oráculo da la cota superior
# de lo que podría ganar la app con información perfecta de ocupación.
ORACULO = {"penetracion": 50, "clasificador": "rf", "semillas": [1, 2, 3, 4, 5]}


def configuraciones() -> list:
    """Las 35 corridas: el 0 % una sola vez por semilla (con umbral: no hay usuarios que clasificar)."""
    cfgs = ex.configuraciones(MATRIZ)
    cfgs = [c for c in cfgs if not (c["penetracion"] == 0 and c["clasificador"] == "rf")]
    for c in cfgs:
        c["dir_resultados"] = "kpis/resultados/final"
        c["subdir_salidas"] = "final"
    return cfgs


def configuraciones_oraculo() -> list:
    """Las 5 corridas de sensibilidad con guiado por la ocupación real (`<id>_oraculo`)."""
    m = dict(MATRIZ, penetracion=[ORACULO["penetracion"]], clasificador=[ORACULO["clasificador"]],
             semillas=ORACULO["semillas"])
    cfgs = ex.configuraciones(m)
    for c in cfgs:
        c["id"] += "_oraculo"
        c["guia_fuente"] = "verdad"
        c["dir_resultados"] = "kpis/resultados/final"
        c["subdir_salidas"] = "final"
    return cfgs


def todas() -> list:
    return configuraciones() + configuraciones_oraculo()


def _tarea(cfg: dict, h: str) -> dict:
    """En un proceso del pool: lanza la corrida en un intérprete nuevo y mueve el JSON a <id>/kpis.json."""
    destino = FINAL / cfg["id"]
    destino.mkdir(parents=True, exist_ok=True)
    codigo = ("import json,sys; from kpis.experimentos import trabajo; "
              "print(json.dumps(trabajo(json.loads(sys.argv[1]), sys.argv[2], sys.argv[3])))")
    t0 = time.time()
    with open(destino / "corrida.log", "w", encoding="utf-8") as log:
        r = subprocess.run([sys.executable, "-c", codigo, json.dumps(cfg), h, str(destino)], cwd=CODIGO,
                           stdout=log, stderr=subprocess.STDOUT, timeout=MATRIZ["timeout_corrida_s"])
    hecho = destino / f"{cfg['id']}.json"
    if r.returncode == 0 and hecho.exists():
        datos = json.loads(hecho.read_text(encoding="utf-8"))
        datos["origen"] = "S4-2"
        ex.escribir_atomico(destino / "kpis.json", datos)
        hecho.unlink()
        return {"id": cfg["id"], "ok": True, "s": time.time() - t0}
    return {"id": cfg["id"], "ok": False, "s": time.time() - t0, "codigo": r.returncode}


def reutilizar_s3(cfg: dict, h: str) -> bool:
    """Copia la corrida de S3-1 si tiene el mismo hash de configuración."""
    previa = AQUI / "resultados" / "corridas" / f"{cfg['id']}.json"
    if not previa.exists():
        return False
    datos = json.loads(previa.read_text(encoding="utf-8"))
    if datos.get("hash_config") != h:
        return False
    destino = FINAL / cfg["id"]
    destino.mkdir(parents=True, exist_ok=True)
    datos["origen"] = "S3-1 (mismo hash)"
    ex.escribir_atomico(destino / "kpis.json", datos)
    for sub in ("vehiculos", "sesiones"):
        o = AQUI / "resultados" / sub / f"{cfg['id']}.csv.gz"
        if o.exists():
            (FINAL / sub).mkdir(parents=True, exist_ok=True)
            shutil.copy2(o, FINAL / sub / o.name)
    return True


def ejecutar(procesos: int) -> dict:
    FINAL.mkdir(parents=True, exist_ok=True)
    cfgs = todas()
    hashes = ex.hashes_entradas(MATRIZ)
    pendientes, reutilizadas = [], []
    for c in cfgs:
        h = ex.hash_config(c, hashes)
        if (FINAL / c["id"] / "kpis.json").exists():
            continue
        if reutilizar_s3(c, h):
            reutilizadas.append(c["id"])
            continue
        pendientes.append((c, h))
    ex.log(FINAL, f"inicio: {len(cfgs)} corridas, {len(reutilizadas)} reutilizadas de S3-1, "
                  f"{len(pendientes)} pendientes, {procesos} procesos")
    t0 = time.time()
    fallidas = []
    for intento in (1, 2):
        if not pendientes:
            break
        with ProcessPoolExecutor(max_workers=procesos) as pool:
            futuros = {pool.submit(_tarea, c, h): (c, h) for c, h in pendientes}
            pendientes = []
            for f in as_completed(futuros):
                c, h = futuros[f]
                try:
                    r = f.result()
                except Exception as e:  # noqa: BLE001
                    r = {"id": c["id"], "ok": False, "s": 0, "error": repr(e)}
                if r["ok"]:
                    ex.log(FINAL, f"fin {r['id']} {r['s']:.0f} s")
                else:
                    ex.log(FINAL, f"error {r['id']} intento {intento} {r}")
                    pendientes.append((c, h))
    fallidas = [c["id"] for c, _ in pendientes]
    ex.recolectar_sesiones(FINAL, cfgs)  # detalle por sesión de las corridas nuevas
    total = time.time() - t0
    ex.log(FINAL, f"listo {len(cfgs) - len(fallidas)}/{len(cfgs)} en {total:.0f} s")
    return {"duracion_s": round(total, 1), "fallidas": fallidas, "reutilizadas": reutilizadas,
            "procesos": procesos}


def manifiesto(info: dict) -> Path:
    """Todo lo necesario para repetir la corrida exacta."""
    raiz = raiz_repo()
    previo = {}
    if (FINAL / "manifiesto.json").exists():
        previo = json.loads((FINAL / "manifiesto.json").read_text(encoding="utf-8"))
    cfgs = todas()
    hashes = ex.hashes_entradas(MATRIZ)
    corridas = {}
    for c in cfgs:
        k = FINAL / c["id"] / "kpis.json"
        if k.exists():
            d = json.loads(k.read_text(encoding="utf-8"))
            corridas[c["id"]] = {"hash_config": d["hash_config"], "origen": d.get("origen"),
                                 "fin_utc": d.get("fin_utc"), "duracion_real_s": d["fila"]["duracion_real_s"]}
    modelo_json = AQUI / "externo" / "ia" / "modelos" / "rf_final.json"
    sha_modelo = json.loads(modelo_json.read_text())["sha256_modelo"] if modelo_json.exists() else None
    datos = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head": ex._git_head(),
        "proyecto_usado": {"traci": "proyecto/traci (controlador de Freddy, unificado en S3)",
                           "ia": "origin/pablo/s4:semanas/S4/Pablo/codigo/ia (rf_final congelado)",
                           "git_rev_proyecto": ex._git_head()},
        "modelo": {"nombre": "rf_final", "sha256_joblib": hashes.get("modelo_rf_joblib"),
                   "sha256_esperado_json": sha_modelo,
                   "coincide": sha_modelo == hashes.get("modelo_rf_joblib"),
                   "sha256_npz": hashes.get("modelo_rf")},
        "sumo": ex._sumo_version(),
        "python_contenedor": platform.python_version(),
        "sistema": platform.platform(),
        "cpu": {"nucleos": os.cpu_count(), "modelo": _cpu()},
        "sumocfg": "sumo/escenarios/<base|app20|app50|app80>_s<N>.sumocfg (generar_escenarios.py)",
        "veh_hora": MATRIZ["veh_hora"],
        "semillas": MATRIZ["semillas"],
        "matriz": MATRIZ,
        "oraculo": {**ORACULO, "guia_fuente": "verdad", "ids": [c["id"] for c in configuraciones_oraculo()]},
        "hashes_entradas": hashes,
        "demandas_sha256": {f"s{s}": {p: sha256_archivo(CODIGO / "sumo" / "escenarios" / f"{nombre_escenario(p, s)}.rou.xml")
                                      for p in MATRIZ["penetracion"]
                                      if (CODIGO / "sumo" / "escenarios" / f"{nombre_escenario(p, s)}.rou.xml").exists()}
                            for s in MATRIZ["semillas"]},
        "repetir": ["docker exec -w /home/vanet/results/e-sert/<codigo> van3twin bash -lc "
                    "\"python3 sumo/escenarios/generar_escenarios.py --semillas 1 2 3 4 5\" (desde sumo/escenarios)",
                    "python -m kpis.modelo_plano exportar --joblib kpis/externo/ia/modelos/rf_final.joblib "
                    "--salida kpis/externo/rf_final.plano.npz (en la computadora, con sklearn 1.9.1)",
                    "python3 -m kpis.corrida_final --procesos 4 (en el contenedor)"],
        "corridas": corridas,
        "n_corridas": len(corridas),
        "ejecucion": {**previo.get("ejecucion", {}), **info} if info else previo.get("ejecucion", {}),
    }
    ex.escribir_atomico(FINAL / "manifiesto.json", datos)
    return FINAL / "manifiesto.json"


def _cpu() -> str:
    try:
        for linea in Path("/proc/cpuinfo").read_text().splitlines():
            if linea.startswith("model name"):
                return linea.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--procesos", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--solo-resumen", action="store_true", help="no corre SUMO: solo manifiesto y resumen")
    args = ap.parse_args(argv)
    info = {} if args.solo_resumen else ejecutar(args.procesos)
    m = manifiesto(info)
    print(f"manifiesto: {m}")
    from kpis import estadistica_final as ef

    print(ef.main([]))


if __name__ == "__main__":
    main()
