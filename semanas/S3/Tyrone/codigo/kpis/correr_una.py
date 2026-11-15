"""Una corrida de la matriz de experimentos: `correr(cfg) -> dict` (S3-1).

Se ejecuta **dentro del contenedor** `van3twin` (importa TraCI). La llama `kpis.experimentos`
en un proceso nuevo por corrida (`spawn`, `maxtasksperchild=1`), pero también sirve sola:

    python3 -m kpis.correr_una --id p50_rf_s1 --duracion 600 --warmup 120

Qué hace, sin estado global entre corridas:

1. ID `p{pen:02d}_{clf}_s{sem}`. La demanda depende solo de la semilla y los usuarios con app
   salen de `sumo/escenarios/generar_escenarios.py` (números aleatorios comunes: un `u_i` por
   buscador, `con_app = u_i < pen/100`, así 20 % ⊂ 50 % ⊂ 80 %).
2. Corre el controlador de Freddy (`proyecto/traci/correr_kpis.correr`: guiado, peatones, GPS,
   clasificación, sesiones y `KPIsSistema`) con las salidas XML de SUMO en
   `sumo/salidas/<id>/`. TraCI elige un puerto libre (`traci.start` usa
   `sumolib.miscutils.getFreeSocketPort()` por defecto) y la etiqueta es única por corrida.
3. `clasificador = rf` usa el RF de Pablo exportado a `.npz` (`kpis/modelo_plano.py`), porque en
   el contenedor no hay sklearn; `umbral` fuerza la regla de umbral (`ESERT_CLASIFICADOR`).
4. Calcula los KPIs de búsqueda con `kpis.kpis.calcular` (S2-1), sin el *warm-up*: cuentan los
   buscadores que estacionan en `[warmup_s, duracion_s]`. Guarda el detalle por vehículo en
   `kpis/resultados/vehiculos/<id>.csv.gz` y devuelve una fila del CSV consolidado.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent          # .../codigo/kpis
CODIGO = AQUI.parent                             # .../codigo
PATRON_ID = re.compile(r"^p(\d{2})_(umbral|rf)_s(\d+)$")
NOMBRES = {0: "base", 20: "app20", 50: "app50", 80: "app80"}

# Columnas del CSV consolidado (orden fijo del prompt S3-1)
COLUMNAS = ["id", "penetracion", "clasificador", "semilla", "n_veh", "n_busca", "busqueda_media_s",
            "busqueda_p90_s", "distancia_busqueda_media_m", "co2_busqueda_kg", "ocupacion_media",
            "falsas_lib_100", "retardo_cierre_mediana_s", "error_fact_medio_usd", "precision_mapa",
            "teleports", "duracion_real_s"]


def raiz_repo(desde: Path = AQUI) -> Path:
    """Sube hasta la carpeta que contiene `CLAUDE.md` (la raíz del repo)."""
    for p in [desde, *desde.parents]:
        if (p / "CLAUDE.md").is_file():
            return p
    raise RuntimeError("No encontré la raíz del repo (CLAUDE.md)")


def id_corrida(pen: int, clf: str, semilla: int) -> str:
    return f"p{int(pen):02d}_{clf}_s{int(semilla)}"


def interpretar_id(ident: str) -> tuple:
    m = PATRON_ID.match(ident)
    if not m:
        raise ValueError(f"ID inválido: {ident} (se espera p50_rf_s1)")
    return int(m.group(1)), m.group(2), int(m.group(3))


def nombre_escenario(pen: int, semilla: int) -> str:
    return f"{NOMBRES.get(pen, f'app{pen}')}_s{semilla}"


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _nan(x):
    return float("nan") if x is None else x


def _limpiar(x):
    """JSON válido: NaN → null, numpy → Python."""
    if isinstance(x, dict):
        return {k: _limpiar(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_limpiar(v) for v in x]
    if hasattr(x, "item") and not isinstance(x, (str, bytes)):
        x = x.item()
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def _teleports(estadisticas: Path) -> int:
    """Total de teletransportes del statistic-output de SUMO."""
    import xml.etree.ElementTree as ET

    if not estadisticas.exists():
        return -1
    tp = ET.parse(estadisticas).getroot().find("teleports")
    return int(tp.get("total", 0)) if tp is not None else 0


def _insertados(estadisticas: Path) -> int:
    import xml.etree.ElementTree as ET

    if not estadisticas.exists():
        return -1
    v = ET.parse(estadisticas).getroot().find("vehicles")
    return int(v.get("inserted", 0)) if v is not None else -1


def _dir_ia(preferida: Path, raiz: Path) -> Path:
    """Carpeta que contiene el paquete `ia` de Pablo: la copia de `kpis/externo` o `proyecto/`."""
    if (preferida / "ia" / "inferencia.py").exists():
        return preferida
    return raiz / "proyecto"


def _preparar_paths(cfg: dict) -> dict:
    """Rutas absolutas de la corrida a partir de rutas relativas a `codigo/` y a la raíz."""
    raiz = raiz_repo()
    codigo = Path(cfg.get("dir_codigo") or CODIGO)
    sumo = codigo / cfg.get("dir_sumo", "sumo")
    return {
        "raiz": raiz,
        "codigo": codigo,
        "sumo": sumo,
        "proyecto": raiz / cfg.get("dir_proyecto", "proyecto"),
        "ia": _dir_ia(codigo / cfg.get("dir_ia", "kpis/externo"), raiz),
        "modelo": codigo / cfg["modelo_rf"] if cfg.get("modelo_rf") else None,
        "resultados": codigo / cfg.get("dir_resultados", "kpis/resultados"),
    }


def correr(cfg: dict) -> dict:
    """Corre una configuración y devuelve su fila de resultados (más detalle en `extra`).

    `cfg` (todo serializable): `penetracion`, `clasificador`, `semilla`, `duracion_s`, `warmup_s`,
    `modelo_rf` (`.npz` relativo a `codigo/`) y opcionales `dir_*`, `libsumo`.
    """
    t0 = time.perf_counter()
    pen, clf, sem = int(cfg["penetracion"]), cfg["clasificador"], int(cfg["semilla"])
    ident = id_corrida(pen, clf, sem)
    rutas = _preparar_paths(cfg)
    esc = nombre_escenario(pen, sem)
    sumocfg = rutas["sumo"] / "escenarios" / f"{esc}.sumocfg"
    rou = rutas["sumo"] / "escenarios" / f"{esc}.rou.xml"
    if not rou.exists():
        raise FileNotFoundError(f"Falta {rou}: corre sumo/escenarios/generar_escenarios.py --semillas {sem}")
    salidas = rutas["sumo"] / "salidas" / cfg.get("subdir_salidas", "") / ident
    salidas.mkdir(parents=True, exist_ok=True)

    # --- importaciones: kpis (esta copia), traci (Freddy, proyecto/) e ia (Pablo, externo) ---
    os.environ["ESERT_CLASIFICADOR"] = clf
    os.environ["ESERT_IA_DIR"] = str(rutas["ia"])
    for p in (rutas["codigo"], rutas["ia"]):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    if str(rutas["proyecto"]) not in sys.path:
        sys.path.append(str(rutas["proyecto"]))  # después de codigo/: `kpis` es esta copia
    from traci import correr_kpis as ck  # noqa: E402  (controlador de Freddy)

    modelo_info = None
    if clf == "rf":
        from kpis.modelo_plano import instalar

        instalar(rutas["modelo"])
        modelo_info = {"npz": rutas["modelo"].name, "sha256": sha256_archivo(rutas["modelo"])}

    # Freddy resuelve su escenario dentro de proyecto/traci/escenario; aquí se usa esta copia.
    ck.SUMO = rutas["sumo"]
    ck.SALIDAS = salidas
    ck.preparar_escenario = lambda _pen, _sem, sumo=None: sumocfg

    duracion = float(cfg["duracion_s"])
    args_sumo = [
        "--end", str(int(duracion)),
        "--duration-log.disable", "true",
        "--tripinfo-output", str(salidas / "tripinfo.xml"),
        "--stop-output", str(salidas / "stops.xml"),
        "--vehroute-output", str(salidas / "vehroutes.xml"),
        "--emission-output", str(salidas / "emisiones.xml"),
        "--statistic-output", str(salidas / "estadisticas.xml"),
    ]
    if cfg.get("gui") and cfg.get("captura_gui"):
        # Captura de sumo-gui a los `captura_t` s simulados (evidencia de la demo, S4-1)
        destino_png = rutas["codigo"] / cfg["captura_gui"]
        destino_png.parent.mkdir(parents=True, exist_ok=True)
        estado_cap = {"hecha": False}

        def _captura(ctrl, t, _d=destino_png, _e=estado_cap, _t=float(cfg.get("captura_t", 60))):
            if not _e["hecha"] and t >= _t:
                ctrl.traci.gui.screenshot("View #0", str(_d))
                _e["hecha"] = True

        base_agregar = ck.Controlador.agregar_hook
        if not getattr(base_agregar, "_con_captura", False):
            def agregar_con_captura(self, hook, _base=base_agregar):
                if not getattr(self, "_captura_puesta", False):
                    self._captura_puesta = True
                    _base(self, _captura)
                _base(self, hook)
            agregar_con_captura._con_captura = True
            ck.Controlador.agregar_hook = agregar_con_captura
        args_sumo += ["--gui-settings-file", str(rutas["sumo"] / "demanda" / "vista_gui.xml")] \
            if (rutas["sumo"] / "demanda" / "vista_gui.xml").exists() else []
    if cfg.get("gui") and cfg.get("delay_ms"):
        args_sumo += ["--delay", str(int(cfg["delay_ms"]))]
    if cfg.get("gui"):
        # `correr_kpis.correr` no expone la GUI: se fuerza en la configuración del controlador
        base_cfg = ck.ConfigControlador
        ck.ConfigControlador = lambda **kw: base_cfg(**dict(kw, gui=True, libsumo=False))
    res = ck.correr(ident, hasta=duracion, con_kpis=True, gps_semilla=sem, args_sumo=args_sumo,
                    libsumo=bool(cfg.get("libsumo", False)) and not cfg.get("gui"), guardar_csv=True,
                    publicar=cfg.get("publicar"), ritmo=cfg.get("ritmo"))
    sistema = res.get("kpis") or {}
    fuentes = res.get("ventanas_por_fuente", {})
    if clf == "rf" and pen > 0 and not fuentes.get("rf"):
        raise RuntimeError(f"{ident}: se pidió rf pero la inferencia usó {fuentes}")

    # --- KPIs de búsqueda (S2-1) sin warm-up ---
    from kpis import kpis as kp

    vehs, serie, info = kp.calcular(salidas, dir_sumo=rutas["sumo"], ruta_demanda=rou)
    warm = float(cfg["warmup_s"])
    if len(vehs):
        vehs = vehs[(vehs["fin_s"] >= warm) & (vehs["fin_s"] <= duracion)].copy()
    vehs.insert(0, "corrida", ident)
    det = rutas["resultados"] / "vehiculos"
    det.mkdir(parents=True, exist_ok=True)
    with gzip.open(det / f"{ident}.csv.gz", "wt", encoding="utf-8", newline="") as f:
        vehs.to_csv(f, index=False)
    ocup = serie[(serie["t"] >= warm) & (serie["t"] < duracion)]["ocupacion"]

    def m(col):
        return float(vehs[col].mean()) if len(vehs) else float("nan")

    horas = max(1e-9, (duracion - warm) / 3600)
    fila = {
        "id": ident, "penetracion": pen, "clasificador": clf, "semilla": sem,
        "n_veh": _insertados(salidas / "estadisticas.xml"),
        "n_busca": int(len(vehs)),
        "busqueda_media_s": m("tiempo_busqueda_s"),
        "busqueda_p90_s": float(vehs["tiempo_busqueda_s"].quantile(0.9)) if len(vehs) else float("nan"),
        "distancia_busqueda_media_m": m("distancia_busqueda_m"),
        "co2_busqueda_kg": float(vehs["co2_busqueda_g"].sum() / 1000 / horas) if len(vehs) else float("nan"),
        "ocupacion_media": float(ocup.mean()) if len(ocup) else float("nan"),
        "falsas_lib_100": _nan(sistema.get("falsas_lib_100")),
        "retardo_cierre_mediana_s": _nan(sistema.get("retardo_cierre_mediana_s")),
        "error_fact_medio_usd": _nan(sistema.get("error_fact_medio_usd")),
        "precision_mapa": _nan(sistema.get("precision_mapa")),
        "teleports": _teleports(salidas / "estadisticas.xml"),
        "duracion_real_s": round(time.perf_counter() - t0, 1),
    }
    extra = {
        "escenario": esc, "duracion_s": duracion, "warmup_s": warm,
        "kpis_sistema": sistema, "ventanas_por_fuente": fuentes,
        "sesiones_maquina": res.get("sesiones_maquina"), "modelo": modelo_info,
        "info_busqueda": {k: info[k] for k in ("buscadores", "buscadores_con_kpi", "buscadores_sin_estacionar",
                                                "buscadores_sin_inicio", "busqueda_censurada_media_s")},
        "con_app_en_kpi": int(vehs["con_app"].astype(int).sum()) if len(vehs) else 0,
        "ms_por_paso": res.get("ms_por_paso"),
    }
    return _limpiar({"fila": fila, "extra": extra})


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Una corrida de la matriz (dentro del contenedor)")
    ap.add_argument("--id", required=True)
    ap.add_argument("--duracion", type=float, default=4500)
    ap.add_argument("--warmup", type=float, default=900)
    ap.add_argument("--modelo", default="kpis/externo/rf_final.plano.npz")
    ap.add_argument("--publicar", default=None, help="URL del backend: publica snapshots, kpi y espejo")
    ap.add_argument("--ritmo", type=float, default=None, help="veces el tiempo real (1 = demo en vivo)")
    ap.add_argument("--gui", action="store_true", help="sumo-gui (pantalla :99 del contenedor, VNC 5901)")
    ap.add_argument("--subdir", default="", help="subcarpeta de sumo/salidas/ (p. ej. demo)")
    ap.add_argument("--captura-gui", default=None, help="PNG de sumo-gui (relativo a codigo/) a los 60 s")
    ap.add_argument("--delay-ms", type=int, default=0, help="--delay de sumo-gui")
    args = ap.parse_args(argv)
    pen, clf, sem = interpretar_id(args.id)
    out = correr({"penetracion": pen, "clasificador": clf, "semilla": sem, "duracion_s": args.duracion,
                  "warmup_s": args.warmup, "modelo_rf": args.modelo, "publicar": args.publicar,
                  "ritmo": args.ritmo, "gui": args.gui, "subdir_salidas": args.subdir,
                  "captura_gui": args.captura_gui, "delay_ms": args.delay_ms,
                  "dir_resultados": f"kpis/resultados/{args.subdir}" if args.subdir else "kpis/resultados"})
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
