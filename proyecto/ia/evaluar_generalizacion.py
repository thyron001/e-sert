"""
Evaluación de generalización: rf_v1, umbral y rf_v1+suavizado
sobre usuarios no vistos (GeoLife prueba) y escenarios SUMO (semillas 101-105).

Memory-safe: n_jobs=1, submuestreo, gc.collect.
"""
from __future__ import annotations

import gc
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

from .caracteristicas import NOMBRES_FEATURES, extraer
from .suavizado import Suavizador
from .umbral import predecir_lote

CLASES = ["a_pie", "quieto", "vehiculo"]
AQUI = Path(__file__).resolve().parent
DIR_DATOS = AQUI / "datos"
DIR_REPORTES = AQUI / "reportes"
DIR_MODELOS = AQUI / "modelos"
DIR_ESCENARIOS = DIR_DATOS / "escenarios"

SIGMAS = [0, 3, 5, 8, 10, 15]


def cargar_modelo():
    from joblib import load
    pipe = load(DIR_MODELOS / "rf_v1.joblib")
    with (DIR_MODELOS / "rf_v1.json").open() as f:
        meta = json.load(f)
    return pipe, meta


def cargar_particion():
    with (AQUI / "particion_usuarios.json").open() as f:
        return json.load(f)


def preparar_geolife_prueba() -> pd.DataFrame:
    ruta = DIR_DATOS / "procesados" / "ventanas_prueba_geolife.parquet"
    df = pd.read_parquet(ruta)
    for col in df.columns:
        if hasattr(df[col], "to_numpy"):
            try:
                df[col] = df[col].to_numpy()
            except Exception:
                pass
    return df


def preparar_sumo_escenarios(sigma: int = 0) -> pd.DataFrame | None:
    """Carga escenarios SUMO para un σ dado. Retorna None si no existen."""
    from .ventanas import remuestrear, ventanear

    dfs = []
    for semilla in [101, 102, 103, 104, 105]:
        dir_sem = DIR_ESCENARIOS / f"semilla_{semilla}"
        archivo = dir_sem / f"trazas_sigma{sigma}.csv"
        if not archivo.exists():
            return None
        df_raw = pd.read_csv(archivo)
        df_raw["fuente"] = "sumo"
        df_raw["usuario_id"] = df_raw["usuario_id"].astype(str)

        for escenario in df_raw["escenario"].unique():
            df_esc = df_raw[df_raw["escenario"] == escenario].copy()
            if len(df_esc) < 30:
                continue
            df_re = remuestrear(df_esc)
            if df_re.empty:
                continue
            ventanas = ventanear(df_re)
            for v in ventanas:
                feats = extraer(v["_ventana"])
                feats["modo_real"] = v["modo_real"]
                feats["usuario_id"] = v["usuario_id"]
                feats["grupo"] = f"sumo_{semilla}_{v['usuario_id']}"
                feats["fuente_eval"] = f"sumo_{escenario}"
                feats["escenario"] = escenario
                feats["semilla"] = semilla
                feats["sigma"] = sigma
                dfs.append(feats)
            del df_re, ventanas
        del df_raw
    gc.collect()

    if not dfs:
        return None
    return pd.DataFrame(dfs)


def predecir_rf(pipe, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Predicción RF en lotes pequeños para no saturar RAM."""
    BATCH = 50_000
    preds = []
    probas_list = []
    for i in range(0, len(X), BATCH):
        batch_X = X[i:i + BATCH]
        preds.append(pipe.predict(batch_X))
        probas_list.append(pipe.predict_proba(batch_X))
        gc.collect()
    return np.concatenate(preds), np.vstack(probas_list)


def predecir_rf_suavizado(pipe, X: np.ndarray, grupos: np.ndarray,
                          metodo: str = "histeresis", k: int = 1) -> np.ndarray:
    """RF + suavizado por grupo (usuario/trayectoria)."""
    _, probas = predecir_rf(pipe, X)
    clases = pipe.classes_
    preds = []

    for grupo in np.unique(grupos):
        mask = grupos == grupo
        probas_g = probas[mask]
        suav = Suavizador(metodo=metodo, k=k)
        for p in probas_g:
            modo = suav.paso(p)
            preds.append(modo)
    return np.array(preds)


def metricas_fuente(y_true, y_pred, fuente: str) -> dict:
    macro_f1 = f1_score(y_true, y_pred, labels=CLASES, average="macro", zero_division=0)
    prec, rec, f1, sup = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASES, zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=CLASES, normalize="true")

    y_t = np.array(y_true)
    y_p = np.array(y_pred)
    n_veh = np.sum(y_t == "vehiculo")
    tasa_veh_apie = (
        np.sum((y_t == "vehiculo") & (y_p == "a_pie")) / n_veh if n_veh > 0 else 0.0
    )

    return {
        "fuente": fuente,
        "n_ventanas": len(y_true),
        "macro_f1": float(macro_f1),
        "por_clase": {
            c: {"precision": float(prec[i]), "recall": float(rec[i]),
                "f1": float(f1[i]), "support": int(sup[i])}
            for i, c in enumerate(CLASES)
        },
        "confusion_matrix": cm.tolist(),
        "tasa_veh_como_apie": float(tasa_veh_apie),
    }


def _f1_macro_rapido(y_true_int, y_pred_int, n_clases=3):
    """Macro-F1 rápido con arrays de ints (0,1,2) en vez de strings."""
    f1s = np.zeros(n_clases)
    for c in range(n_clases):
        tp = np.sum((y_true_int == c) & (y_pred_int == c))
        fp = np.sum((y_true_int != c) & (y_pred_int == c))
        fn = np.sum((y_true_int == c) & (y_pred_int != c))
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1s[c] = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return float(np.mean(f1s))


_CLASE_A_INT = {"a_pie": 0, "quieto": 1, "vehiculo": 2}


def bootstrap_agrupado(y_true, y_pred, grupos, n_boot: int = 1000,
                       semilla: int = 2026) -> dict:
    """IC 95% por bootstrap agrupado. Precomputa índices por grupo para velocidad."""
    rng = np.random.default_rng(semilla)
    y_t = np.array([_CLASE_A_INT.get(str(v), 0) for v in y_true])
    y_p = np.array([_CLASE_A_INT.get(str(v), 0) for v in y_pred])
    g = np.array(grupos)

    grupos_unicos = np.unique(g)
    n_g = len(grupos_unicos)
    grupo_a_idx = {gid: np.where(g == gid)[0] for gid in grupos_unicos}
    grupo_ids = list(grupo_a_idx.keys())
    idx_arrays = [grupo_a_idx[gid] for gid in grupo_ids]

    VEH_INT = _CLASE_A_INT["vehiculo"]
    APIE_INT = _CLASE_A_INT["a_pie"]

    f1s = np.empty(n_boot)
    tasas = np.empty(n_boot)
    for b in range(n_boot):
        sel = rng.integers(0, n_g, size=n_g)
        indices = np.concatenate([idx_arrays[s] for s in sel])
        yt_b = y_t[indices]
        yp_b = y_p[indices]
        f1s[b] = _f1_macro_rapido(yt_b, yp_b)
        n_veh = np.sum(yt_b == VEH_INT)
        tasas[b] = (
            np.sum((yt_b == VEH_INT) & (yp_b == APIE_INT)) / n_veh
            if n_veh > 0 else 0.0
        )

    return {
        "macro_f1_media": float(np.mean(f1s)),
        "macro_f1_ic95": [float(np.percentile(f1s, 2.5)), float(np.percentile(f1s, 97.5))],
        "tasa_veh_apie_media": float(np.mean(tasas)),
        "tasa_veh_apie_ic95": [float(np.percentile(tasas, 2.5)),
                               float(np.percentile(tasas, 97.5))],
        "n_bootstrap": n_boot,
        "n_grupos": n_g,
    }


def bootstrap_pareado(y_true, y_pred_a, y_pred_b, grupos,
                      n_boot: int = 1000, semilla: int = 2026) -> dict:
    """Bootstrap pareado: mismos remuestreos para dos sistemas."""
    rng = np.random.default_rng(semilla)
    y_t = np.array([_CLASE_A_INT.get(str(v), 0) for v in y_true])
    y_a = np.array([_CLASE_A_INT.get(str(v), 0) for v in y_pred_a])
    y_b = np.array([_CLASE_A_INT.get(str(v), 0) for v in y_pred_b])
    g = np.array(grupos)

    grupos_unicos = np.unique(g)
    n_g = len(grupos_unicos)
    grupo_a_idx = {gid: np.where(g == gid)[0] for gid in grupos_unicos}
    idx_arrays = [grupo_a_idx[gid] for gid in grupos_unicos]

    deltas = np.empty(n_boot)
    for b in range(n_boot):
        sel = rng.integers(0, n_g, size=n_g)
        indices = np.concatenate([idx_arrays[s] for s in sel])
        yt_b = y_t[indices]
        ya_b = y_a[indices]
        yb_b = y_b[indices]
        deltas[b] = _f1_macro_rapido(yt_b, ya_b) - _f1_macro_rapido(yt_b, yb_b)

    ic = [float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))]
    significativo = ic[0] > 0 or ic[1] < 0
    return {
        "delta_media": float(np.mean(deltas)),
        "delta_ic95": ic,
        "significativo": significativo,
    }


def evaluar_fuente(pipe, df: pd.DataFrame, fuente: str, meta: dict) -> dict:
    """Evalúa los 3 sistemas sobre una fuente."""
    features = meta["features"]
    X = df[features].values.astype(np.float64)
    y_true = df["modo_real"].values
    grupos = df["grupo"].values if "grupo" in df.columns else df["usuario_id"].values

    pred_umbral = np.array(predecir_lote(X[:, features.index("vel_media")]))
    pred_rf, probas_rf = predecir_rf(pipe, X)

    suav_config = meta.get("suavizado", {"metodo": "histeresis", "k": 1})
    pred_suav = []
    for grupo_id in np.unique(grupos):
        mask = grupos == grupo_id
        probas_g = probas_rf[mask]
        s = Suavizador(metodo=suav_config["metodo"], k=suav_config["k"])
        for p in probas_g:
            pred_suav.append(s.paso(p))
    pred_suav = np.array(pred_suav)

    gc.collect()

    met_umbral = metricas_fuente(y_true, pred_umbral, fuente)
    met_rf = metricas_fuente(y_true, pred_rf, fuente)
    met_suav = metricas_fuente(y_true, pred_suav, fuente)

    boot_umbral = bootstrap_agrupado(y_true, pred_umbral, grupos)
    boot_rf = bootstrap_agrupado(y_true, pred_rf, grupos)
    boot_suav = bootstrap_agrupado(y_true, pred_suav, grupos)
    boot_pareado_rf_umb = bootstrap_pareado(y_true, pred_rf, pred_umbral, grupos)
    boot_pareado_suav_umb = bootstrap_pareado(y_true, pred_suav, pred_umbral, grupos)

    gc.collect()

    return {
        "fuente": fuente,
        "n_ventanas": len(y_true),
        "n_grupos": int(len(np.unique(grupos))),
        "umbral": {**met_umbral, "bootstrap": boot_umbral},
        "rf": {**met_rf, "bootstrap": boot_rf},
        "rf_suavizado": {**met_suav, "bootstrap": boot_suav},
        "comparacion": {
            "rf_vs_umbral": boot_pareado_rf_umb,
            "rf_suav_vs_umbral": boot_pareado_suav_umb,
        },
    }


def evaluar_curvas_sigma(pipe, meta: dict) -> list[dict]:
    """F1 y tasa vehiculo→a_pie por σ para los 3 sistemas."""
    resultados = []
    for sigma in SIGMAS:
        df_sumo = preparar_sumo_escenarios(sigma)
        if df_sumo is None:
            print(f"  σ={sigma}: sin datos SUMO, saltando")
            continue

        features = meta["features"]
        X = df_sumo[features].values.astype(np.float64)
        y_true = df_sumo["modo_real"].values
        grupos = df_sumo["grupo"].values

        pred_umbral = np.array(predecir_lote(X[:, features.index("vel_media")]))
        pred_rf, probas_rf = predecir_rf(pipe, X)

        suav_config = meta.get("suavizado", {"metodo": "histeresis", "k": 1})
        pred_suav = []
        for g_id in np.unique(grupos):
            mask = grupos == g_id
            s = Suavizador(metodo=suav_config["metodo"], k=suav_config["k"])
            for p in probas_rf[mask]:
                pred_suav.append(s.paso(p))
        pred_suav = np.array(pred_suav)

        y_t = np.array(y_true)
        n_veh = np.sum(y_t == "vehiculo")

        for sistema, pred in [("umbral", pred_umbral), ("rf", pred_rf),
                              ("rf_suavizado", pred_suav)]:
            y_p = np.array(pred)
            f1 = f1_score(y_t, y_p, labels=CLASES, average="macro", zero_division=0)
            tasa = (
                np.sum((y_t == "vehiculo") & (y_p == "a_pie")) / n_veh
                if n_veh > 0 else 0.0
            )
            boot = bootstrap_agrupado(y_t, y_p, grupos, n_boot=500, semilla=2026)
            resultados.append({
                "sigma": sigma,
                "sistema": sistema,
                "macro_f1": float(f1),
                "macro_f1_ic_lo": boot["macro_f1_ic95"][0],
                "macro_f1_ic_hi": boot["macro_f1_ic95"][1],
                "tasa_veh_apie": float(tasa),
                "tasa_veh_apie_ic_lo": boot["tasa_veh_apie_ic95"][0],
                "tasa_veh_apie_ic_hi": boot["tasa_veh_apie_ic95"][1],
                "n_ventanas": len(y_t),
            })

        del df_sumo, X, y_true, grupos, pred_umbral, pred_rf, probas_rf, pred_suav
        gc.collect()

    return resultados


def analizar_trafico_lento(pipe, meta: dict) -> dict | None:
    """Analiza ventanas de vehículo con vel_media < 8 km/h (tráfico lento)."""
    df_sumo = preparar_sumo_escenarios(sigma=5)
    if df_sumo is None:
        return None

    mask_veh = df_sumo["modo_real"] == "vehiculo"
    mask_lento = df_sumo["vel_media"] < (8.0 / 3.6)
    df_lento = df_sumo[mask_veh & mask_lento].copy()

    if len(df_lento) == 0:
        return {"n_ventanas": 0, "mensaje": "No hay ventanas de vehículo lento"}

    features = meta["features"]
    X = df_lento[features].values.astype(np.float64)
    y_true = df_lento["modo_real"].values
    grupos = df_lento["grupo"].values if "grupo" in df_lento.columns else df_lento["usuario_id"].values

    pred_umbral = np.array(predecir_lote(X[:, features.index("vel_media")]))
    pred_rf, probas_rf = predecir_rf(pipe, X)

    suav_config = meta.get("suavizado", {"metodo": "histeresis", "k": 1})
    pred_suav = []
    for g_id in np.unique(grupos):
        mask = grupos == g_id
        s = Suavizador(metodo=suav_config["metodo"], k=suav_config["k"])
        for p in probas_rf[mask]:
            pred_suav.append(s.paso(p))
    pred_suav = np.array(pred_suav)

    minutos = len(df_lento) * 5 / 60.0

    resultado = {
        "n_ventanas": len(df_lento),
        "minutos": round(minutos, 1),
        "vel_media_kmh": round(float(df_lento["vel_media"].mean()) * 3.6, 2),
    }

    for sistema, pred in [("umbral", pred_umbral), ("rf", pred_rf),
                          ("rf_suavizado", pred_suav)]:
        y_p = np.array(pred)
        recall_veh = np.sum(y_p == "vehiculo") / len(y_p) if len(y_p) > 0 else 0.0
        cm = confusion_matrix(y_true, y_p, labels=CLASES, normalize="true")
        resultado[sistema] = {
            "recall_vehiculo": float(recall_veh),
            "confusion": {
                f"predicho_{CLASES[j]}": float(cm[CLASES.index("vehiculo"), j])
                for j in range(len(CLASES))
            },
        }

    del df_sumo, df_lento
    gc.collect()
    return resultado


def ejecutar():
    print("Cargando modelo y partición...")
    pipe, meta = cargar_modelo()
    particion = cargar_particion()
    DIR_REPORTES.mkdir(parents=True, exist_ok=True)

    resultados = {"fuentes": {}, "curvas_sigma": [], "trafico_lento": None,
                  "brecha_generalizacion": {}}

    # 1. GeoLife prueba
    print("\n=== GeoLife prueba ===")
    df_geo = preparar_geolife_prueba()
    usuarios_prueba = set(particion["usuarios_prueba"])
    df_geo = df_geo[df_geo["usuario_id"].isin(usuarios_prueba)]
    print(f"  {len(df_geo)} ventanas, {df_geo['usuario_id'].nunique()} usuarios")
    if len(df_geo) > 0:
        res_geo = evaluar_fuente(pipe, df_geo, "geolife_prueba", meta)
        resultados["fuentes"]["geolife_prueba"] = res_geo
        print(f"  RF macro-F1: {res_geo['rf']['macro_f1']:.4f}")
        print(f"  Umbral macro-F1: {res_geo['umbral']['macro_f1']:.4f}")
    del df_geo
    gc.collect()

    # 2. SUMO escenarios (σ=5 como referencia)
    hay_sumo = False
    for escenario_tipo in ["normal", "trafico_lento", "peaton_rapido"]:
        print(f"\n=== SUMO {escenario_tipo} ===")
        df_sumo = preparar_sumo_escenarios(sigma=5)
        if df_sumo is None:
            print("  Sin datos SUMO (contenedor no corrió)")
            break
        hay_sumo = True
        df_esc = df_sumo[df_sumo["escenario"] == escenario_tipo]
        if len(df_esc) == 0:
            print(f"  Sin ventanas para {escenario_tipo}")
            continue

        fuente = f"sumo_{escenario_tipo}"
        res = evaluar_fuente(pipe, df_esc.copy(), fuente, meta)
        resultados["fuentes"][fuente] = res
        print(f"  {res['n_ventanas']} ventanas, RF macro-F1: {res['rf']['macro_f1']:.4f}")
        del df_esc
    if df_sumo is not None:
        del df_sumo
    gc.collect()

    # 3. Grabaciones caseras
    caseras_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "proyecto" / "datos"
    if caseras_dir.exists():
        csvs = list(caseras_dir.glob("*.csv"))
        if csvs:
            print("\n=== Grabaciones caseras ===")
            print(f"  Encontrados {len(csvs)} archivos — evaluación pendiente")
        else:
            resultados["fuentes"]["caseras"] = "no disponibles"
    else:
        resultados["fuentes"]["caseras"] = "no disponibles"

    # 4. Curvas σ
    if hay_sumo:
        print("\n=== Curvas F1 vs σ ===")
        curvas = evaluar_curvas_sigma(pipe, meta)
        resultados["curvas_sigma"] = curvas
        df_curvas = pd.DataFrame(curvas)
        df_curvas.to_csv(DIR_REPORTES / "curvas_sigma.csv", index=False)
        print(f"  {len(curvas)} puntos guardados en curvas_sigma.csv")

    # 5. Tráfico lento
    if hay_sumo:
        print("\n=== Tráfico lento ===")
        tl = analizar_trafico_lento(pipe, meta)
        resultados["trafico_lento"] = tl
        if tl:
            print(f"  {tl['n_ventanas']} ventanas, {tl['minutos']} min")

    # 6. Brecha de generalización
    cv_f1 = meta["metricas_cv"]["rf_v1_macro_f1"]
    for fuente, res in resultados["fuentes"].items():
        if isinstance(res, str):
            continue
        test_f1 = res["rf"]["macro_f1"]
        resultados["brecha_generalizacion"][fuente] = {
            "cv_macro_f1": cv_f1,
            "test_macro_f1": test_f1,
            "brecha": round(cv_f1 - test_f1, 4),
        }

    # Guardar JSON
    with (DIR_REPORTES / "metricas_generalizacion.json").open("w") as f:
        json.dump(resultados, f, indent=2, default=str)
    print(f"\nResultados: {DIR_REPORTES / 'metricas_generalizacion.json'}")

    return resultados


if __name__ == "__main__":
    ejecutar()
