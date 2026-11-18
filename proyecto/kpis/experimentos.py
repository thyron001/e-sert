"""Ejecutor de la matriz de experimentos: penetración × clasificador × semillas (S3-1).

Se ejecuta **dentro del contenedor** `van3twin`, desde `semanas/S3/Tyrone/codigo`:

    python3 -m kpis.experimentos --matriz kpis/matriz.yaml [--procesos N] [--solo ID] [--forzar]
                                 [--rapida] [--dry-run]

- Un proceso nuevo por corrida (`spawn` y `maxtasksperchild=1`): TraCI guarda estado por proceso.
- Reanudable: cada corrida deja `resultados/corridas/<id>.json` de forma atómica (`.tmp` +
  `os.replace`); al arrancar se saltan las que ya tienen JSON con el mismo `hash_config`.
- Un fallo deja `<id>.error.json` con el *traceback*, se reintenta una vez y no frena a las demás.
- `resultados/progreso.log`: una línea por evento (`2026-11-02T15:04Z fin p20_rf_s1 312 s`).
- Al final consolida `resultados/experimentos.csv` y `resultados/metadatos.json`.
- `--rapida`: 600 s de simulación, 120 s de *warm-up* y solo `p00_umbral_s1` y `p50_rf_s1`, en
  `resultados/rapida/` (no se mezcla con la matriz completa).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import multiprocessing as mp
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parent
sys.path.insert(0, str(CODIGO))

from kpis.correr_una import COLUMNAS, id_corrida, nombre_escenario, raiz_repo, ruta_modelo, sha256_archivo  # noqa: E402

RAPIDA = {"duracion_s": 600, "warmup_s": 120, "ids": ["p00_umbral_s1", "p50_rf_s1"]}


# ------------------------------------------------------------------ matriz y hashes

def leer_matriz(ruta: Path) -> dict:
    import yaml

    return yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))


def n_procesos(valor) -> int:
    if valor in (None, "auto"):
        return max(1, min((os.cpu_count() or 2) - 1, 6))
    return max(1, int(valor))


def configuraciones(matriz: dict, rapida: bool = False, solo=None, ids_rapida=None) -> list:
    """Lista de cfg (dict serializable) de la matriz, en orden estable."""
    dur = RAPIDA["duracion_s"] if rapida else matriz["duracion_s"]
    warm = RAPIDA["warmup_s"] if rapida else matriz["warmup_s"]
    cfgs = []
    for sem in matriz["semillas"]:
        for pen in matriz["penetracion"]:
            for clf in matriz["clasificador"]:
                ident = id_corrida(pen, clf, sem)
                if rapida and ident not in (ids_rapida or RAPIDA["ids"]):
                    continue
                if solo and ident not in solo:
                    continue
                cfgs.append({"id": ident, "penetracion": int(pen), "clasificador": clf, "semilla": int(sem),
                             "duracion_s": float(dur), "warmup_s": float(warm),
                             "modelo_rf": matriz.get("modelo_rf"),
                             "dir_resultados": "kpis/resultados/rapida" if rapida else "kpis/resultados",
                             "subdir_salidas": "rapida" if rapida else "",
                             "libsumo": bool(matriz.get("libsumo", False))})
    return cfgs


def hashes_entradas(matriz: dict) -> dict:
    """SHA-256 de la red, los parqueos y el modelo (joblib original y su exportación)."""
    sumo = CODIGO / "sumo"
    h = {"red": sha256_archivo(sumo / "red" / "centro.net.xml"),
         "parqueos": sha256_archivo(sumo / "parqueos" / "parqueos.add.xml")}
    for clave in ("modelo_rf", "modelo_rf_joblib"):
        if matriz.get(clave) and ruta_modelo(CODIGO, matriz[clave]).exists():
            h[clave] = sha256_archivo(ruta_modelo(CODIGO, matriz[clave]))
    info = ruta_modelo(CODIGO, "kpis/externo/rf_final.plano.json")
    if "modelo_rf_joblib" not in h and info.exists():
        h["modelo_rf_joblib"] = json.loads(info.read_text())["joblib_sha256"]
    return h


def hash_config(cfg: dict, hashes: dict) -> str:
    """SHA-256 del cfg canónico + hashes de red, parqueos, modelo y la demanda de la semilla."""
    rou = CODIGO / "sumo" / "escenarios" / f"{nombre_escenario(cfg['penetracion'], cfg['semilla'])}.rou.xml"
    # Las carpetas de salida no cambian el resultado: no entran en el hash
    base = {"cfg": {k: v for k, v in cfg.items() if k not in ("id", "dir_resultados", "subdir_salidas")},
            "hashes": hashes,
            "demanda": sha256_archivo(rou) if rou.exists() else None}
    # El modelo solo influye si hay usuarios clasificados con rf
    if not (cfg["clasificador"] == "rf" and cfg["penetracion"] > 0):
        base["hashes"] = {k: v for k, v in hashes.items() if not k.startswith("modelo")}
        base["cfg"] = {k: v for k, v in base["cfg"].items() if k != "modelo_rf"}
    return hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------ escritura atómica y log

def escribir_atomico(ruta: Path, datos: dict) -> None:
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_text(json.dumps(datos, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, ruta)


def ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def log(dir_res: Path, texto: str) -> None:
    linea = f"{ahora()} {texto}"
    with open(dir_res / "progreso.log", "a", encoding="utf-8") as f:
        f.write(linea + "\n")
    print(linea, flush=True)


def ya_hecha(dir_corr: Path, ident: str, h: str) -> bool:
    ruta = dir_corr / f"{ident}.json"
    if not ruta.exists():
        return False
    try:
        return json.loads(ruta.read_text(encoding="utf-8")).get("hash_config") == h
    except (json.JSONDecodeError, OSError):
        return False


# ------------------------------------------------------------------ trabajo de cada proceso

def trabajo(cfg: dict, h: str, dir_corr: str) -> dict:
    """Corre en un proceso hijo: escribe `<id>.json` o `<id>.error.json` y devuelve el estado."""
    dir_corr = Path(dir_corr)
    ident = cfg["id"]
    t0 = time.time()
    try:
        from kpis.correr_una import correr

        out = correr(cfg)
        datos = {"id": ident, "hash_config": h, "cfg": cfg, **out,
                 "fin_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        escribir_atomico(dir_corr / f"{ident}.json", datos)
        err = dir_corr / f"{ident}.error.json"
        if err.exists():
            err.unlink()
        return {"id": ident, "ok": True, "s": time.time() - t0}
    except BaseException as e:  # noqa: BLE001 (también KeyboardInterrupt de SUMO)
        escribir_atomico(dir_corr / f"{ident}.error.json",
                         {"id": ident, "hash_config": h, "cfg": cfg, "error": repr(e),
                          "traceback": traceback.format_exc(),
                          "fin_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        return {"id": ident, "ok": False, "s": time.time() - t0, "error": repr(e)}


# ------------------------------------------------------------------ consolidación

def recolectar_sesiones(dir_res: Path, cfgs: list) -> None:
    """Copia el detalle por sesión de Freddy (`kpis_sesiones_<id>.csv`, en las salidas ignoradas de
    SUMO) a `resultados/sesiones/<id>.csv.gz`, que usan las figuras de retardo de cierre."""
    import gzip
    import shutil

    destino = dir_res / "sesiones"
    for cfg in cfgs:
        origen = CODIGO / "sumo" / "salidas" / cfg.get("subdir_salidas", "") / cfg["id"] / f"kpis_sesiones_{cfg['id']}.csv"
        if origen.exists():
            destino.mkdir(parents=True, exist_ok=True)
            # GzipFile con mtime=0: el .gz no cambia si el CSV no cambia (Python 3.10 no tiene gzip.open(mtime=))
            with open(origen, "rb") as fi, open(destino / f"{cfg['id']}.csv.gz", "wb") as crudo, \
                    gzip.GzipFile(fileobj=crudo, mode="wb", mtime=0) as fo:
                shutil.copyfileobj(fi, fo)


def consolidar(dir_res: Path, cfgs: list) -> Path:
    """Una fila por corrida con JSON (en el orden de la matriz) en `experimentos.csv`."""
    filas = []
    for cfg in cfgs:
        ruta = dir_res / "corridas" / f"{cfg['id']}.json"
        if ruta.exists():
            filas.append(json.loads(ruta.read_text(encoding="utf-8"))["fila"])
    recolectar_sesiones(dir_res, cfgs)
    destino = dir_res / "experimentos.csv"
    with open(destino, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, lineterminator="\n")
        w.writeheader()
        for fila in filas:
            w.writerow({k: ("" if fila.get(k) is None else fila.get(k)) for k in COLUMNAS})
    return destino


def _git_head() -> str:
    raiz = raiz_repo()
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=raiz, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        head = (raiz / ".git" / "HEAD").read_text().strip()  # el contenedor no tiene git
        if head.startswith("ref: "):
            ref = raiz / ".git" / head[5:]
            if ref.exists():
                return ref.read_text().strip()
            packed = raiz / ".git" / "packed-refs"
            for linea in packed.read_text().splitlines() if packed.exists() else []:
                if linea.endswith(head[5:]):
                    return linea.split()[0]
        return head


def _sumo_version() -> str:
    try:
        return subprocess.run(["sumo", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, IndexError):
        return "desconocida"


def duracion_desde_log(dir_res: Path):
    """Segundos desde el último `inicio` con corridas pendientes hasta la última línea `fin`.

    Al relanzar sin pendientes (solo consolidar), `duracion_total_s` es ~0: esta cifra conserva lo que
    tardó de verdad la matriz.
    """
    ruta = dir_res / "progreso.log"
    if not ruta.exists():
        return None
    t_ini = t_fin = None
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        partes = linea.split(" ", 3)
        if len(partes) < 3:
            continue
        try:
            t = datetime.strptime(partes[0], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
        if partes[1] == "inicio" and not partes[2].startswith("0"):
            t_ini, t_fin = t, None
        elif partes[1] == "fin" and t_ini is not None:
            t_fin = t
    return None if t_ini is None or t_fin is None else round(t_fin - t_ini, 1)


def metadatos(dir_res: Path, matriz: dict, cfgs: list, hashes: dict, procesos: int, inicio: float,
              fallidas: list, rapida: bool) -> Path:
    hechas = [c["id"] for c in cfgs if (dir_res / "corridas" / f"{c['id']}.json").exists()]
    datos = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head": _git_head(),
        "sumo": _sumo_version(),
        "python": platform.python_version(),
        "plataforma": platform.platform(),
        "cpu": os.cpu_count(),
        "matriz": matriz,
        "rapida": rapida,
        "hashes_entradas": hashes,
        "procesos": procesos,
        "duracion_total_s": round(time.time() - inicio, 1),
        "duracion_matriz_s": duracion_desde_log(dir_res),
        "corridas_total": len(cfgs),
        "corridas_hechas": len(hechas),
        "corridas_fallidas": fallidas,
        "errores": sorted(p.name for p in (dir_res / "corridas").glob("*.error.json")),
    }
    escribir_atomico(dir_res / "metadatos.json", datos)
    return dir_res / "metadatos.json"


# ------------------------------------------------------------------ bucle principal

def ejecutar(matriz: dict, procesos: int, rapida=False, solo=None, forzar=False, dry_run=False,
             dir_res: Path = None) -> dict:
    cfgs = configuraciones(matriz, rapida, solo)
    dir_res = dir_res or (CODIGO / cfgs[0]["dir_resultados"] if cfgs else CODIGO / "kpis" / "resultados")
    dir_corr = dir_res / "corridas"
    dir_corr.mkdir(parents=True, exist_ok=True)
    hashes = hashes_entradas(matriz)
    pendientes = []
    for cfg in cfgs:
        h = hash_config(cfg, hashes)
        if not forzar and ya_hecha(dir_corr, cfg["id"], h):
            continue
        pendientes.append((cfg, h))
    print(f"{len(cfgs)} corridas en la matriz, {len(cfgs) - len(pendientes)} ya hechas, "
          f"{len(pendientes)} pendientes, {procesos} procesos", flush=True)
    if dry_run:
        for cfg, h in pendientes:
            print(f"  {cfg['id']}  hash={h[:12]}")
        return {"pendientes": [c["id"] for c, _ in pendientes], "hechas": len(cfgs) - len(pendientes)}

    inicio = time.time()
    log(dir_res, f"inicio {len(pendientes)} pendientes de {len(cfgs)} con {procesos} procesos")
    timeout = float(matriz.get("timeout_corrida_s", 1800))
    fallidas = []
    ctx = mp.get_context("spawn")
    intentos = {cfg["id"]: 0 for cfg, _ in pendientes}
    cola = list(pendientes)
    while cola:
        ronda, cola = cola, []
        with ctx.Pool(processes=min(procesos, len(ronda)), maxtasksperchild=1) as pool:
            tareas = []
            for cfg, h in ronda:
                intentos[cfg["id"]] += 1
                log(dir_res, f"encolada {cfg['id']} intento {intentos[cfg['id']]}")
                tareas.append((cfg, h, pool.apply_async(trabajo, (cfg, h, str(dir_corr)))))
            for cfg, h, tarea in tareas:
                try:
                    r = tarea.get(timeout=timeout)
                except mp.TimeoutError:
                    r = {"id": cfg["id"], "ok": False, "s": timeout, "error": f"timeout {timeout:.0f} s"}
                    escribir_atomico(dir_corr / f"{cfg['id']}.error.json",
                                     {"id": cfg["id"], "hash_config": h, "cfg": cfg, "error": r["error"],
                                      "traceback": "", "fin_utc": datetime.now(timezone.utc).isoformat()})
                if r["ok"]:
                    log(dir_res, f"fin {r['id']} {r['s']:.0f} s")
                else:
                    log(dir_res, f"error {r['id']} {r['s']:.0f} s {r.get('error', '')[:120]}")
                    if intentos[cfg["id"]] < 2:
                        cola.append((cfg, h))
                    else:
                        fallidas.append(cfg["id"])
            if any(not t.ready() for _, _, t in tareas):
                pool.terminate()
    csv_ = consolidar(dir_res, cfgs)
    meta = metadatos(dir_res, matriz, cfgs, hashes, procesos, inicio, fallidas, rapida)
    log(dir_res, f"listo {len(cfgs) - len(fallidas)}/{len(cfgs)} en {time.time() - inicio:.0f} s")
    return {"csv": str(csv_), "metadatos": str(meta), "fallidas": fallidas,
            "duracion_s": time.time() - inicio}


def medir_speedup(matriz: dict, procesos=(1, 4)) -> dict:
    """Las 8 corridas cortas (600 s) de la semilla 1 con 1 y con 4 procesos: tiempo total y speedup."""
    ids = [id_corrida(p, c, 1) for p in matriz["penetracion"] for c in matriz["clasificador"]]
    tiempos = {}
    for n in procesos:
        dir_res = CODIGO / "kpis" / "resultados" / "speedup" / f"n{n}"
        cfgs = configuraciones(matriz, rapida=True, ids_rapida=ids)
        t0 = time.time()
        _ejecutar_cfgs(cfgs, matriz, n, dir_res)
        tiempos[n] = round(time.time() - t0, 1)
    base = tiempos[procesos[0]]
    r = {"corridas": len(ids), "duracion_sim_s": RAPIDA["duracion_s"], "tiempos_s": tiempos,
         "speedup": {n: round(base / t, 2) for n, t in tiempos.items()}, "cpu": os.cpu_count(),
         "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    escribir_atomico(CODIGO / "kpis" / "resultados" / "speedup.json", r)
    return r


def _ejecutar_cfgs(cfgs, matriz, procesos, dir_res):
    """Corre una lista de cfg con forzar (para medir), en `dir_res`."""
    for c in cfgs:
        c["dir_resultados"] = str(dir_res.relative_to(CODIGO))
        c["subdir_salidas"] = "speedup"
    dir_corr = dir_res / "corridas"
    dir_corr.mkdir(parents=True, exist_ok=True)
    hashes = hashes_entradas(matriz)
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=procesos, maxtasksperchild=1) as pool:
        tareas = [pool.apply_async(trabajo, (c, hash_config(c, hashes), str(dir_corr))) for c in cfgs]
        res = [t.get(timeout=float(matriz.get("timeout_corrida_s", 1800))) for t in tareas]
    if not all(r["ok"] for r in res):
        raise RuntimeError(f"fallaron corridas al medir el speedup: {res}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Matriz de experimentos (dentro del contenedor)")
    ap.add_argument("--matriz", default=str(AQUI / "matriz.yaml"))
    ap.add_argument("--procesos", default=None)
    ap.add_argument("--solo", nargs="+", default=None, help="IDs a correr (p. ej. p50_rf_s2)")
    ap.add_argument("--forzar", action="store_true", help="Repite aunque ya haya JSON")
    ap.add_argument("--rapida", action="store_true", help="600 s, 2 corridas, en resultados/rapida/")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--speedup", action="store_true", help="Mide 8 corridas cortas con 1 y 4 procesos")
    ap.add_argument("--resultados", default=None, help="Carpeta de resultados (por defecto la del modo)")
    args = ap.parse_args(argv)
    matriz = leer_matriz(Path(args.matriz))
    procesos = n_procesos(args.procesos if args.procesos is not None else matriz.get("procesos"))
    if args.speedup:
        print(json.dumps(medir_speedup(matriz), indent=1))
        return
    r = ejecutar(matriz, procesos, rapida=args.rapida, solo=args.solo, forzar=args.forzar,
                 dry_run=args.dry_run, dir_res=Path(args.resultados) if args.resultados else None)
    print(json.dumps(r, indent=1, ensure_ascii=False))
    sys.exit(1 if r.get("fallidas") else 0)


if __name__ == "__main__":
    main()
