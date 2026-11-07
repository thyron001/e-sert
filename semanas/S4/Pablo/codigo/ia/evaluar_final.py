"""
Evaluación final de `rf_final` (S4-1): umbral, `rf_v1` (referencia) y `rf_final` sobre las MISMAS ventanas.

    python3 -m ia.evaluar_final [--solo-geolife] [--tope-sumo 60000]

Fuentes (todas de prueba, nunca vistas en el entrenamiento):
  * geolife_prueba: usuarios de `ia/particion_usuarios.json` (caracteristicas de `ventanas_prueba_geolife.parquet`).
  * sumo_normal / sumo_trafico_lento / sumo_peaton_rapido: semillas 101-105 con sigma = 5 m
    (`ia/datos/escenarios/`). Las etiquetas se calculan por tramos de modo constante (el sesgo de S2-3, donde
    `remuestrear` etiquetaba toda la traza con el modo de su primera fila, esta corregido).
  * curvas frente a sigma (0, 3, 5, 8, 10, 15 m) con escenario normal y semillas 101 y 103.

Usa `bootstrap_agrupado` de `evaluar_generalizacion.py` (usuario o trayectoria como grupo). Escribe
ia/reportes/metricas_rf_final.json, ia/reportes/curvas_sigma_final.csv y vuelca los resumenes a
`metricas` de ia/modelos/rf_final.json.
"""
import argparse
import gc
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

from ia import inferencia
from ia.analisis_errores import cargar_sumo, predecir
from ia.caracteristicas import NOMBRES_FEATURES
from ia.evaluar_generalizacion import bootstrap_agrupado, bootstrap_pareado
from ia.umbral import predecir_lote

AQUI = Path(__file__).resolve().parent
REPORTES = AQUI / "reportes"
META_FINAL = AQUI / "modelos" / "rf_final.json"
PROCESADOS = AQUI.parents[3] / "S2/Pablo/codigo/ia/datos/procesados"
RF_V1 = AQUI.parents[3] / "S3/Pablo/codigo/ia/modelos/rf_v1.joblib"
CLASES = ["a_pie", "quieto", "vehiculo"]
SEMILLAS = [101, 102, 103, 104, 105]
SIGMAS = [0, 3, 5, 8, 10, 15]
ESCENARIOS = ["normal", "trafico_lento", "peaton_rapido"]
N_BOOT = 1000


def usar_modelo(ruta: Path | None):
    """Selecciona el RF que usa `ia.inferencia` (None = rf_final por defecto)."""
    if ruta is None:
        os.environ.pop("ESERT_MODELO", None)
    else:
        os.environ["ESERT_MODELO"] = str(ruta)
    inferencia._reset_cache()
    modelo = inferencia._cargar_modelo()
    if modelo is None:
        raise SystemExit(f"No se pudo cargar el modelo {ruta or 'rf_final'} (hash o archivo)")
    return modelo


def metricas(y, p) -> dict:
    prec, rec, f1, sup = precision_recall_fscore_support(y, p, labels=CLASES, zero_division=0)
    return {
        "macro_f1": float(f1_score(y, p, labels=CLASES, average="macro", zero_division=0)),
        "por_clase": {c: {"precision": float(prec[i]), "recall": float(rec[i]), "f1": float(f1[i]),
                          "support": int(sup[i])} for i, c in enumerate(CLASES)},
        "confusion_normalizada": confusion_matrix(y, p, labels=CLASES, normalize="true").tolist(),
        "confusion_conteos": confusion_matrix(y, p, labels=CLASES).tolist(),
    }


def f1_por_clase_ic(y, p, grupos, n_boot: int = N_BOOT, semilla: int = 2026) -> dict:
    """IC 95 % del F1 de cada clase por bootstrap agrupado (mismos remuestreos que `bootstrap_agrupado`)."""
    idx = {c: i for i, c in enumerate(CLASES)}
    yt = np.array([idx[v] for v in y])
    yp = np.array([idx[v] for v in p])
    g = np.asarray(grupos)
    ids = np.unique(g)
    por_grupo = [np.flatnonzero(g == i) for i in ids]
    rng = np.random.default_rng(semilla)
    f1s = np.zeros((n_boot, 3))
    for b in range(n_boot):
        sel = rng.integers(0, len(ids), len(ids))
        k = np.concatenate([por_grupo[i] for i in sel])
        a, q = yt[k], yp[k]
        for c in range(3):
            tp = np.sum((a == c) & (q == c))
            fp = np.sum((a != c) & (q == c))
            fn = np.sum((a == c) & (q != c))
            f1s[b, c] = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    return {c: [float(np.percentile(f1s[:, i], 2.5)), float(np.percentile(f1s[:, i], 97.5))] for c, i in idx.items()}


def evaluar_sistemas(y, preds: dict, grupos) -> dict:
    """Metricas + IC 95 % agrupado de cada sistema y diferencias pareadas frente al umbral."""
    out = {"n_ventanas": int(len(y)), "n_grupos": int(len(set(grupos)))}
    for nombre, p in preds.items():
        m = metricas(y, p)
        m["bootstrap"] = bootstrap_agrupado(y, p, grupos, N_BOOT)
        m["bootstrap"]["f1_por_clase_ic95"] = f1_por_clase_ic(y, p, grupos)
        out[nombre] = m
    for nombre in preds:
        if nombre != "umbral":
            out.setdefault("vs_umbral", {})[nombre] = bootstrap_pareado(y, preds[nombre], preds["umbral"], grupos, N_BOOT)
    return out


def predecir_geolife(modelo):
    df = pd.read_parquet(PROCESADOS / "ventanas_prueba_geolife.parquet")
    part = json.loads((AQUI / "particion_usuarios.json").read_text())
    df = df[df["usuario_id"].isin(part["usuarios_prueba"])]
    X = df[NOMBRES_FEATURES].to_numpy(np.float64)
    proba = np.vstack([modelo.predict_proba(X[i:i + 50_000]) for i in range(0, len(X), 50_000)])
    return df, np.asarray(modelo.classes_)[proba.argmax(axis=1)]


def importancia_permutacion(modelo, df, n: int = 30_000, repeticiones: int = 3, semilla: int = 2026) -> pd.DataFrame:
    """Caida del macro-F1 al permutar cada caracteristica, sobre ventanas de usuarios no vistos."""
    rng = np.random.default_rng(semilla)
    d = df.iloc[rng.choice(len(df), min(n, len(df)), replace=False)]
    X, y = d[NOMBRES_FEATURES].to_numpy(np.float64), d["modo_real"].to_numpy()
    clases = np.asarray(modelo.classes_)

    def f1(M):
        return f1_score(y, clases[modelo.predict_proba(M).argmax(axis=1)], labels=CLASES, average="macro", zero_division=0)

    base = f1(X)
    filas = []
    for j, nombre in enumerate(NOMBRES_FEATURES):
        caidas = []
        for _ in range(repeticiones):
            M = X.copy()
            M[:, j] = rng.permutation(M[:, j])
            caidas.append(base - f1(M))
        filas.append({"caracteristica": nombre, "importancia_media": float(np.mean(caidas)),
                      "importancia_std": float(np.std(caidas)), "f1_base": float(base), "n_ventanas": len(d)})
    return pd.DataFrame(filas)


def histograma_velocidad(vel_kmh, modos, fuente: str, tope: float = 40.0) -> pd.DataFrame:
    """Conteo de ventanas por clase y bin de 1 km/h (el ultimo bin agrupa >= tope)."""
    v = np.clip(np.asarray(vel_kmh, float), 0, tope)
    bins = np.minimum(np.floor(v).astype(int), int(tope))
    filas = []
    for c in CLASES:
        cont = np.bincount(bins[np.asarray(modos) == c], minlength=int(tope) + 1)
        filas += [{"fuente": fuente, "clase": c, "vel_kmh_inicio": b, "n": int(n)} for b, n in enumerate(cont)]
    return pd.DataFrame(filas)


def cargar_ventanas_sumo(tope: int, solo_sigma5: bool = False):
    """{(grupo): (filas, arrs)} con etiquetas por tramos de modo constante."""
    ventanas = {}
    for sem in SEMILLAS:
        ventanas[("sigma5", sem)] = cargar_sumo(sem, 5, tope)
        print(f"  semilla {sem} sigma 5: {len(ventanas[('sigma5', sem)][0])} ventanas", flush=True)
    if not solo_sigma5:
        for sg in SIGMAS:
            if sg == 5:
                continue
            for sem in (101, 103):
                ventanas[(f"sigma{sg}", sem)] = cargar_sumo(sem, sg, tope)
        print("  curvas sigma cargadas", flush=True)
    return ventanas


def predecir_sumo(ventanas) -> pd.DataFrame:
    dfs = []
    for (grupo, sem), (filas, arrs) in ventanas.items():
        if not filas:
            continue
        d = predecir(filas, arrs)
        d["grupo_carga"] = grupo
        dfs.append(d)
    return pd.concat(dfs, ignore_index=True)


def latencia(n: int = 10_000) -> dict:
    from ia.bench_inferencia import medir_individual, reunir

    geo, sumo = reunir(n)
    ventanas = geo + sumo
    ms = medir_individual(ventanas)
    p50, p95, p99 = np.percentile(ms, (50, 95, 99))
    return {"n_llamadas": int(len(ms)), "p50_ms": float(p50), "p95_ms": float(p95), "p99_ms": float(p99),
            "cumple_p99_lt_5ms": bool(p99 < 5.0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-geolife", action="store_true")
    ap.add_argument("--tope-sumo", type=int, default=60_000)
    ap.add_argument("--sin-latencia", action="store_true")
    ap.add_argument("--sin-v1", action="store_true", help="no compara con rf_v1")
    a = ap.parse_args()
    t0 = time.time()
    REPORTES.mkdir(exist_ok=True)

    sistemas = [("rf_final", None)]
    if not a.sin_v1 and RF_V1.exists():
        sistemas.insert(0, ("rf_v1", RF_V1))

    ventanas = None if a.solo_geolife else cargar_ventanas_sumo(a.tope_sumo)
    print(f"ventanas SUMO cargadas ({time.time() - t0:.0f} s)", flush=True)

    pred_geo, pred_sumo, df_geo = {}, {}, None
    for nombre, ruta in sistemas:
        modelo = usar_modelo(ruta)
        df_geo, pred_geo[nombre] = predecir_geolife(modelo)
        if ventanas is not None:
            pred_sumo[nombre] = predecir_sumo(ventanas)
        print(f"  {nombre} predicho ({time.time() - t0:.0f} s)", flush=True)
        gc.collect()

    resultados = {"fuentes": {}, "curvas_sigma": [], "trafico_lento": {}}
    usar_modelo(None)
    imp = importancia_permutacion(inferencia._cargar_modelo(), df_geo)
    imp.to_csv(REPORTES / "importancia_permutacion_final.csv", index=False)
    print(f"  importancia por permutacion lista ({time.time() - t0:.0f} s)", flush=True)
    hist = [histograma_velocidad(df_geo["vel_media"] * 3.6, df_geo["modo_real"], "geolife_prueba")]
    y = df_geo["modo_real"].to_numpy()
    preds = {"umbral": np.array(predecir_lote(df_geo["vel_media"].to_numpy())),
             **{n: p for n, p in pred_geo.items()}}
    resultados["fuentes"]["geolife_prueba"] = evaluar_sistemas(y, preds, df_geo["usuario_id"].to_numpy())

    if ventanas is not None:
        base = next(iter(pred_sumo.values()))
        for esc in ESCENARIOS:
            m_ = ((base["grupo_carga"] == "sigma5") & (base["escenario"] == esc)).to_numpy()
            if m_.any():
                hist.append(histograma_velocidad(base.loc[m_, "vel_kmh"].fillna(0), base.loc[m_, "modo_real"], f"sumo_{esc}"))
        pd.concat(hist, ignore_index=True).to_csv(REPORTES / "velocidad_por_clase.csv", index=False)
        for esc in ESCENARIOS:
            sel = ((base["grupo_carga"] == "sigma5") & (base["escenario"] == esc)).to_numpy()
            if not sel.any():
                continue
            preds = {"umbral": base.loc[sel, "pred_umbral"].to_numpy(),
                     **{n: d.loc[sel, "pred_rf"].to_numpy() for n, d in pred_sumo.items()}}
            resultados["fuentes"][f"sumo_{esc}"] = evaluar_sistemas(
                base.loc[sel, "modo_real"].to_numpy(), preds, base.loc[sel, "usuario_id"].to_numpy())
        # tráfico lento: F1 y recall de vehiculo, global y con velocidad < 8 km/h
        sel = ((base["grupo_carga"] == "sigma5") & (base["escenario"] == "trafico_lento")).to_numpy()
        lento = sel & (base["vel_kmh"] < 8).to_numpy()
        tl = {"n_ventanas": int(sel.sum()), "n_ventanas_lt_8kmh": int(lento.sum())}
        for nombre in ["umbral"] + list(pred_sumo):
            col = "pred_umbral" if nombre == "umbral" else "pred_rf"
            d = base if nombre == "umbral" else pred_sumo[nombre]
            yt, yp = base.loc[sel, "modo_real"].to_numpy(), d.loc[sel, col].to_numpy()
            tl[nombre] = {"f1_vehiculo": float(f1_score(yt, yp, labels=["vehiculo"], average="macro", zero_division=0)),
                          "recall_vehiculo": float(((yt == "vehiculo") & (yp == "vehiculo")).sum() / max((yt == "vehiculo").sum(), 1)),
                          "recall_vehiculo_lt_8kmh": float(((base.loc[lento, "modo_real"] == "vehiculo")
                                                            & (d.loc[lento, col] == "vehiculo")).sum()
                                                           / max((base.loc[lento, "modo_real"] == "vehiculo").sum(), 1))}
        resultados["trafico_lento"] = tl
        # curvas frente a sigma (escenario normal, semillas 101 y 103)
        for sg in SIGMAS:
            g = "sigma5" if sg == 5 else f"sigma{sg}"
            sel = ((base["grupo_carga"] == g) & (base["escenario"] == "normal") & base["semilla"].isin([101, 103])).to_numpy()
            if not sel.any():
                continue
            yt, gr = base.loc[sel, "modo_real"].to_numpy(), base.loc[sel, "usuario_id"].to_numpy()
            sist = {"umbral": base.loc[sel, "pred_umbral"].to_numpy(),
                    **{n: d.loc[sel, "pred_rf"].to_numpy() for n, d in pred_sumo.items()}}
            for nombre, p in sist.items():
                bs = bootstrap_agrupado(yt, p, gr, 300)
                resultados["curvas_sigma"].append({
                    "sigma": sg, "sistema": nombre, "macro_f1": metricas(yt, p)["macro_f1"],
                    "macro_f1_ic_lo": bs["macro_f1_ic95"][0], "macro_f1_ic_hi": bs["macro_f1_ic95"][1],
                    "tasa_veh_apie": bs["tasa_veh_apie_media"], "n_ventanas": int(sel.sum())})
        pd.DataFrame(resultados["curvas_sigma"]).to_csv(REPORTES / "curvas_sigma_final.csv", index=False)

    if not a.sin_latencia:
        usar_modelo(None)
        resultados["latencia"] = latencia()
    resultados["caseras"] = "no disponibles"
    resultados["segundos"] = round(time.time() - t0)
    (REPORTES / "metricas_rf_final.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False))

    # resumen en rf_final.json (el modelo no cambia: solo se documentan sus metricas)
    if META_FINAL.exists():
        meta = json.loads(META_FINAL.read_text())
        res = {}
        for fuente, r in resultados["fuentes"].items():
            res[fuente] = {"f1_macro": r["rf_final"]["macro_f1"], "ic95": r["rf_final"]["bootstrap"]["macro_f1_ic95"],
                           "f1_macro_umbral": r["umbral"]["macro_f1"], "n_ventanas": r["n_ventanas"]}
        res["f1_macro"] = res["geolife_prueba"]["f1_macro"]
        if "latencia" in resultados:
            res["latencia_ms"] = {"p50": resultados["latencia"]["p50_ms"], "p99": resultados["latencia"]["p99_ms"]}
        meta["metricas"] = res
        META_FINAL.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    for fuente, r in resultados["fuentes"].items():
        print(fuente, {k: round(r[k]["macro_f1"], 4) for k in ("umbral", "rf_v1", "rf_final") if k in r})
    print(f"listo en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
