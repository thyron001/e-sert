"""
Analisis de errores del clasificador (S3-2, paso 1): donde se equivocan umbral y RF.

    python3 -m ia.analisis_errores [--geolife-filas 80000] [--cap-sumo 15000]

Genera (en ia/reportes/ y evidencias/):
  errores_contexto.csv   recall y precision por clase, contexto y sistema
  errores_confusion.csv  matriz de confusion por contexto y sistema
  peores_errores.csv     los 20 errores del RF con mayor confianza, con su tipo
  s2_errores-contexto.png, s2_peores-errores.png

Contextos
  velocidad    velocidad media suavizada de la ventana (km/h): [0,3) [3,8) [8,15) [15,inf)
  precision    precision_m media de la ventana: <10, 10-25, >25 m (solo SUMO; GeoLife no la trae)
  transicion   Las ventanas nunca mezclan modos (remuestrear etiqueta cada tramo con
               un solo modo), asi que "transicion" = ventana a <= 10 s del borde de su segmento
               cuando el segmento vecino del mismo usuario (hueco <= 10 s) tiene otro modo. En SUMO los
               segmentos son los tramos de modo constante de cada usuario (_segmentar_por_modo).
  sigma        nivel de ruido GPS del escenario (SUMO, semilla 101, escenario normal)
  escenario    normal, trafico_lento, peaton_rapido (SUMO, sigma = 5 m, semillas 101-105)

Sistemas: "umbral" = ia.umbral sobre la velocidad media de la ventana; "rf" = ia.inferencia.clasificar_lote.
"""
from __future__ import annotations

import argparse
import gc
import json
import re
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from ia.datos.ventanas_prueba import DIR_ESCENARIOS, PARQUET, RAIZ_IA
from ia.inferencia import _extraer_features_lote, _orden_features, clasificar_lote
from ia.umbral import clasificar_umbral
from ia.ventanas import remuestrear, ventanear

CLASES = ["a_pie", "quieto", "vehiculo"]
BINS_VEL = [(0.0, 3.0, "0-3"), (3.0, 8.0, "3-8"), (8.0, 15.0, "8-15"), (15.0, np.inf, ">15")]
BINS_PREC = [(0.0, 10.0, "<10"), (10.0, 25.0, "10-25"), (25.0, np.inf, ">25")]
ETIQ_VEL = [b[2] for b in BINS_VEL]
ETIQ_PREC = [b[2] for b in BINS_PREC]
SIGMAS = [3, 5, 8, 10, 15]
SEMILLAS = [101, 102, 103, 104, 105]
ESCENARIOS = ["normal", "trafico_lento", "peaton_rapido"]

REPORTES = RAIZ_IA / "reportes"
EVIDENCIAS = RAIZ_IA.parent.parent / "evidencias"
SIN_DATO = "sin_dato"


# ── Contextos ───────────────────────────────────────────────────────────────


def _bin(valor: float, bins: list) -> str:
    if valor is None or not np.isfinite(valor):
        return SIN_DATO
    for lo, hi, etiqueta in bins:
        if lo <= valor < hi:
            return etiqueta
    return SIN_DATO


def bin_velocidad(kmh: float) -> str:
    """Rango de velocidad media (km/h); limite inferior inclusivo."""
    return _bin(kmh, BINS_VEL)


def bin_precision(metros: float) -> str:
    """Rango de precision_m (m); limite inferior inclusivo."""
    return _bin(metros, BINS_PREC)


def matriz_confusion(real, pred) -> pd.DataFrame:
    """Matriz (filas = real, columnas = predicho) con las 3 clases siempre presentes."""
    real, pred = np.asarray(real), np.asarray(pred)
    m = pd.DataFrame(0, index=CLASES, columns=CLASES)
    for r in CLASES:
        for p in CLASES:
            m.loc[r, p] = int(np.sum((real == r) & (pred == p)))
    return m


def metricas_por_clase(real, pred) -> pd.DataFrame:
    """n (soporte real), recall y precision por clase. NaN si no hay datos para calcularlos."""
    m = matriz_confusion(real, pred)
    filas = []
    for c in CLASES:
        n = int(m.loc[c].sum())
        pred_c = int(m[c].sum())
        tp = int(m.loc[c, c])
        filas.append({"clase": c, "n_clase": n,
                      "recall": tp / n if n else np.nan,
                      "precision": tp / pred_c if pred_c else np.nan})
    return pd.DataFrame(filas)


# ── Carga de ventanas ───────────────────────────────────────────────────────


def _ventanas(df: pd.DataFrame, meta: dict) -> tuple[list[dict], list[np.ndarray]]:
    """ventanear(remuestrear(df)) -> filas de metadatos y arrays (t, lat, lon, precision)."""
    filas, arrs = [], []
    re_df = remuestrear(df)
    if re_df.empty:
        return filas, arrs
    vs = ventanear(re_df)
    for v in vs:
        s = v["_ventana"]
        prec = s["precision_m"].to_numpy(float) if "precision_m" in s.columns else np.full(len(s), np.nan)
        arrs.append(np.column_stack([s["t"].to_numpy(float), s["lat"].to_numpy(float),
                                     s["lon"].to_numpy(float), prec]))
        filas.append({**meta, "usuario_id": str(v["usuario_id"]), "segmento_id": str(v["segmento_id"]),
                      "t_inicio": float(v["t_inicio"]), "t_fin": float(v["t_fin"]),
                      "modo_real": v["modo_real"]})
    return filas, arrs


def _elegir_filas(df: pd.DataFrame, col_grupo: str, tope: int, clave: list) -> pd.DataFrame:
    """Submuestrea por grupos (usuarios/segmentos) hasta ~tope filas; igual seleccion en cada sigma."""
    conteo = df[col_grupo].value_counts().sort_index()
    rng = np.random.default_rng(clave)
    elegidos, total = [], 0
    for g in rng.permutation(conteo.index.to_numpy()):
        elegidos.append(g)
        total += int(conteo[g])
        if total >= tope:
            break
    return df[df[col_grupo].isin(elegidos)]


def _marcar_transiciones(df: pd.DataFrame, filas: list[dict], col_usuario: str) -> None:
    """Pone fila["transicion"] = la ventana esta a <= 10 s del borde de su segmento y el segmento vecino
    del mismo usuario (hueco <= 10 s) tiene otro modo. df necesita segmento_id, modo_real y t."""
    seg = (df.groupby("segmento_id").agg(usuario=(col_usuario, "first"), modo=("modo_real", "first"),
                                          t0=("t", "min"), t1=("t", "max")).reset_index()
           .sort_values(["usuario", "t0"]).reset_index(drop=True))
    mismo = seg["usuario"].eq(seg["usuario"].shift(1))
    seg["cambio_prev"] = mismo & (seg["t0"] - seg["t1"].shift(1) <= 10) & seg["modo"].ne(seg["modo"].shift(1))
    mismo_s = seg["usuario"].eq(seg["usuario"].shift(-1))
    seg["cambio_sig"] = mismo_s & (seg["t0"].shift(-1) - seg["t1"] <= 10) & seg["modo"].ne(seg["modo"].shift(-1))
    info = seg.set_index("segmento_id")
    for f in filas:
        s_ = info.loc[re.sub(r"_r\d+$", "", f["segmento_id"])]
        f["transicion"] = bool((s_["cambio_prev"] and f["t_inicio"] - s_["t0"] <= 10)
                               or (s_["cambio_sig"] and s_["t1"] - f["t_fin"] <= 10))


def _segmentar_por_modo(d: pd.DataFrame) -> pd.DataFrame:
    """segmento_id = tramo continuo (hueco <= 10 s) de un usuario con el mismo modo_real.
    Sin esto, remuestrear etiqueta toda la traza con el modo de su primera fila."""
    d = d.sort_values(["usuario_id", "t"]).copy()
    cambio = (d["usuario_id"].ne(d["usuario_id"].shift()) | d["modo_real"].ne(d["modo_real"].shift())
              | (d["t"] - d["t"].shift() > 10))
    d["segmento_id"] = d["usuario_id"] + "_s" + cambio.cumsum().astype(str)
    return d


def cargar_geolife(max_filas: int):
    """Ventanas de los usuarios GeoLife de prueba, con marca de adyacencia a cambio de modo."""
    usuarios = json.loads((RAIZ_IA / "particion_usuarios.json").read_text())["usuarios_prueba"]
    df = pd.read_parquet(PARQUET, filters=[("usuario_id", "in", usuarios)],
                         columns=["usuario_id", "t", "lat", "lon", "modo_real", "segmento_id"])
    df = _elegir_filas(df, "segmento_id", max_filas, [2026, 7])
    df["fuente"] = "geolife"
    filas, arrs = _ventanas(df, {"fuente": "geolife", "escenario": "geolife", "sigma": np.nan, "semilla": -1})
    _marcar_transiciones(df, filas, "usuario_id")
    del df
    gc.collect()
    return filas, arrs


def cargar_sumo(semilla: int, sigma: int, tope: int):
    """Ventanas de un archivo trazas_sigma<sigma>.csv de una semilla, por escenario."""
    ruta = DIR_ESCENARIOS / f"semilla_{semilla}" / f"trazas_sigma{sigma}.csv"
    if not ruta.exists():
        return [], []
    df = pd.read_csv(ruta)
    filas, arrs = [], []
    for esc in df["escenario"].unique():
        d = df[df["escenario"] == esc].copy()
        d["usuario_id"] = f"{semilla}_{esc}_" + d["usuario_id"].astype(str)
        d = _elegir_filas(d, "usuario_id", tope, [2026, semilla, zlib.crc32(esc.encode())])
        d["fuente"] = "sumo"
        d = _segmentar_por_modo(d)
        f, a = _ventanas(d, {"fuente": "sumo", "escenario": esc, "sigma": sigma, "semilla": semilla})
        _marcar_transiciones(d, f, "usuario_id")
        filas += f
        arrs += a
    del df
    gc.collect()
    return filas, arrs


# ── Predicciones ────────────────────────────────────────────────────────────


def _puntos(a: np.ndarray) -> list[dict]:
    return [{"t": float(t), "lat": float(la), "lon": float(lo),
             "precision_m": None if np.isnan(p) else float(p)} for t, la, lo, p in a]


def predecir(filas: list[dict], arrs: list[np.ndarray], bloque: int = 2000) -> pd.DataFrame:
    """Anade vel_kmh, precision_m, pred_umbral, pred_rf y conf_rf a las filas."""
    i_vel = _orden_features().index("vel_media")
    vel = np.full(len(arrs), np.nan)
    for i0 in range(0, len(arrs), bloque):
        trozo = arrs[i0:i0 + bloque]
        for j, f in enumerate(_extraer_features_lote(trozo)):
            if f is not None:
                vel[i0 + j] = f[i_vel]
    rf = []
    for i0 in range(0, len(arrs), bloque):
        rf += clasificar_lote([_puntos(a) for a in arrs[i0:i0 + bloque]])
    df = pd.DataFrame(filas)
    df["vel_kmh"] = vel * 3.6
    prec = [np.nanmean(a[:, 3]) if np.isfinite(a[:, 3]).any() else np.nan for a in arrs]
    df["precision_m"] = prec
    df["pred_umbral"] = [clasificar_umbral(v) if np.isfinite(v) else "quieto" for v in vel]
    df["pred_rf"] = [r["modo"] for r in rf]
    df["conf_rf"] = [r["confianza"] for r in rf]
    df["fuente_rf"] = [r["fuente"] for r in rf]
    return df


# ── Tablas ──────────────────────────────────────────────────────────────────


def _contextos(df: pd.DataFrame):
    """Genera (fuente, tipo, valor, subconjunto) segun las definiciones de la cabecera."""
    geo = df[df.fuente == "geolife"]
    s5 = df[(df.fuente == "sumo") & (df.sigma == 5)]
    yield "geolife", "global", "todo", geo
    yield "sumo", "global", "todo", s5
    for fuente, d in (("geolife", geo), ("sumo", s5)):
        etiquetas = d["vel_kmh"].map(bin_velocidad)
        for v in ETIQ_VEL:
            yield fuente, "velocidad", v, d[etiquetas == v]
    etiquetas = s5["precision_m"].map(bin_precision)
    for v in ETIQ_PREC:
        yield "sumo", "precision", v, s5[etiquetas == v]
    for fuente, d in (("geolife", geo), ("sumo", s5)):
        for v, nombre in ((True, "adyacente_a_cambio"), (False, "interior")):
            yield fuente, "transicion", nombre, d[d["transicion"] == v]
    sg = df[(df.fuente == "sumo") & (df.semilla == 101) & (df.escenario == "normal")]
    for s in SIGMAS:
        yield "sumo", "sigma", str(s), sg[sg.sigma == s]
    for e in ESCENARIOS:
        yield "sumo", "escenario", e, s5[s5.escenario == e]


def tablas(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metricas, confusion = [], []
    for fuente, tipo, valor, d in _contextos(df):
        for sistema, col in (("umbral", "pred_umbral"), ("rf", "pred_rf")):
            met = metricas_por_clase(d["modo_real"], d[col])
            met.insert(0, "n_ventanas", len(d))
            for k, v in (("contexto_valor", valor), ("contexto_tipo", tipo), ("sistema", sistema),
                         ("fuente", fuente)):
                met.insert(0, k, v)
            metricas.append(met)
            m = matriz_confusion(d["modo_real"], d[col])
            for r in CLASES:
                for p in CLASES:
                    confusion.append({"fuente": fuente, "sistema": sistema, "contexto_tipo": tipo,
                                      "contexto_valor": valor, "real": r, "pred": p, "n": int(m.loc[r, p])})
    return pd.concat(metricas, ignore_index=True), pd.DataFrame(confusion)


# ── Peores errores ──────────────────────────────────────────────────────────

R_TIERRA = 6_371_000.0


def _metros_locales(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = np.radians(a[:, 2] - a[0, 2]) * R_TIERRA * np.cos(np.radians(a[0, 1]))
    y = np.radians(a[:, 1] - a[0, 1]) * R_TIERRA
    return x, y


def _velocidades(a: np.ndarray) -> np.ndarray:
    x, y = _metros_locales(a)
    return np.hypot(np.diff(x), np.diff(y)) / np.maximum(np.diff(a[:, 0]), 1e-6)


def clasificar_error(modo_real: str, a: np.ndarray, sigma: float | None = None) -> tuple[str, str]:
    """
    Separa error de etiqueta de error del modelo con la evidencia fisica de la ventana. Usa el
    desplazamiento neto (robusto al ruido GPS; la velocidad por segundo sobre puntos con sigma >= 10 m
    se infla mucho). `sigma` es el ruido GPS conocido (SUMO); en GeoLife se asume 5 m.
      vehiculo con desplazamiento < 15 m              -> etiqueta (el vehiculo no se movio)
      quieto con desplazamiento > max(40, 4 sigma)    -> etiqueta (se movio mas de lo que explica el ruido)
      a_pie con velocidad neta > 5 m/s (18 km/h)      -> etiqueta (no es una caminata)
    Cualquier otro caso es error del modelo.
    """
    x, y = _metros_locales(a)
    desp = float(np.hypot(x[-1], y[-1]))
    dur = max(float(a[-1, 0] - a[0, 0]), 1.0)
    v_neta = desp / dur
    s_ = 5.0 if sigma is None or not np.isfinite(sigma) else float(sigma)
    if modo_real == "vehiculo" and desp < 15:
        return "error_de_etiqueta", f"vehiculo inmovil: desplazamiento neto {desp:.1f} m en {dur:.0f} s"
    if modo_real == "quieto" and desp > max(40.0, 4 * s_):
        return "error_de_etiqueta", f"quieto con desplazamiento {desp:.1f} m (> {max(40.0, 4 * s_):.0f} m, ruido sigma={s_:.0f} m)"
    if modo_real == "a_pie" and v_neta > 5:
        return "error_de_etiqueta", f"a_pie a {v_neta * 3.6:.0f} km/h de velocidad neta"
    return "error_del_modelo", f"desplazamiento {desp:.1f} m, velocidad neta {v_neta:.2f} m/s: coherente con la etiqueta"


def elegir_peores(df: pd.DataFrame, por_fuente: int = 10, max_por_par: int = 5, max_por_sigma: int = 4) -> pd.DataFrame:
    """Errores del RF con mayor confianza: a lo sumo 1 por segmento original, max_por_par por par
    real->pred y (SUMO) max_por_sigma por nivel de sigma; si no se llega a por_fuente se completa sin
    el tope de par/sigma."""
    err = df[(df.modo_real != df.pred_rf) & (df.fuente_rf == "rf")].copy()
    err["_azar"] = np.random.default_rng(2026).random(len(err))
    err["_seg"] = err["segmento_id"].str.replace(r"_r\d+$", "", regex=True)
    err = err.sort_values(["conf_rf", "_azar"], ascending=[False, True])
    elegidos = []
    for fuente in ("geolife", "sumo"):
        cand = err[err.fuente == fuente]
        usados, pares, sigmas, sel = set(), {}, {}, []
        for estricto in (True, False):
            for idx, r in cand.iterrows():
                if len(sel) >= por_fuente:
                    break
                par = (r.modo_real, r.pred_rf)
                if idx in sel or r._seg in usados:
                    continue
                if estricto and (pares.get(par, 0) >= max_por_par or
                                 (fuente == "sumo" and sigmas.get(r.sigma, 0) >= max_por_sigma)):
                    continue
                usados.add(r._seg)
                pares[par] = pares.get(par, 0) + 1
                sigmas[r.sigma] = sigmas.get(r.sigma, 0) + 1
                sel.append(idx)
        elegidos += sel
    return err.loc[elegidos].drop(columns=["_azar", "_seg"])


# ── Figuras ─────────────────────────────────────────────────────────────────

C_UMBRAL, C_RF, TINTA, APAGADO = "#8A8F98", "#2A6FB0", "#222222", "#666666"


def figura_contexto(met: pd.DataFrame, ruta: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paneles = [("geolife", "velocidad", ETIQ_VEL, "GeoLife: velocidad media (km/h)"),
               ("sumo", "velocidad", ETIQ_VEL, "SUMO: velocidad media (km/h)"),
               ("sumo", "precision", ETIQ_PREC, "SUMO: precision_m (m)")]
    fig, ejes = plt.subplots(2, 3, figsize=(14, 7.2), sharey=True)
    for fila, clase in enumerate(("vehiculo", "quieto")):
        for col, (fuente, tipo, etiquetas, titulo) in enumerate(paneles):
            ax = ejes[fila, col]
            d = met[(met.fuente == fuente) & (met.contexto_tipo == tipo) & (met.clase == clase)]
            x = np.arange(len(etiquetas))
            for k, (sistema, color) in enumerate((("umbral", C_UMBRAL), ("rf", C_RF))):
                vals, ns = [], []
                for e in etiquetas:
                    r = d[(d.sistema == sistema) & (d.contexto_valor == e)]
                    vals.append(float(r.recall.iloc[0]) if len(r) and np.isfinite(r.recall.iloc[0]) else np.nan)
                    ns.append(int(r.n_clase.iloc[0]) if len(r) else 0)
                barras = ax.bar(x + (k - 0.5) * 0.38, np.nan_to_num(vals), 0.36, color=color,
                                label="Umbral" if sistema == "umbral" else "Random Forest")
                for b, v, n in zip(barras, vals, ns):
                    txt = "s/d" if not np.isfinite(v) else f"{v:.2f}"
                    ax.text(b.get_x() + b.get_width() / 2, (0 if not np.isfinite(v) else v) + 0.02, txt,
                            ha="center", va="bottom", fontsize=7.5, color=TINTA)
                if k == 0:
                    for xi, n in zip(x, ns):
                        ax.text(xi, -0.13, f"n={n}", ha="center", va="top", fontsize=7.5, color=APAGADO)
            ax.set_xticks(x)
            ax.set_xticklabels(etiquetas, color=APAGADO)
            ax.set_ylim(0, 1.12)
            ax.set_title(f"{titulo}", fontsize=10, color=TINTA, loc="left")
            if col == 0:
                ax.set_ylabel(f"Recall de {clase}", color=TINTA)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            ax.grid(axis="y", color="#DDDDDD", lw=0.6)
            ax.set_axisbelow(True)
    h, l = ejes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, frameon=False, fontsize=10)
    fig.suptitle("Recall de vehiculo y quieto por contexto (s/d = sin datos en ese rango)", x=0.01, ha="left",
                 fontsize=12, color=TINTA)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(ruta, dpi=140)
    plt.close(fig)


def figura_peores(peores: pd.DataFrame, arrs: list[np.ndarray], ruta: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec

    fig = plt.figure(figsize=(20, 16))
    gs = GridSpec(4, 5, figure=fig, hspace=0.55, wspace=0.28)
    colores = {"error_de_etiqueta": "#C8761F", "error_del_modelo": "#2A6FB0"}
    for k, (_, r) in enumerate(peores.iterrows()):
        sub = GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[k // 5, k % 5], height_ratios=[3, 1.2], hspace=0.35)
        a = arrs[int(r.idx_arr)]
        x, y = _metros_locales(a)
        v = _velocidades(a)
        ax = fig.add_subplot(sub[0])
        ax.plot(x, y, "-", color=colores[r.tipo], lw=1.4)
        ax.plot(x[0], y[0], "o", color=TINTA, ms=5)
        ax.plot(x[-1], y[-1], "s", color=TINTA, ms=5)
        ax.set_aspect("equal", adjustable="datalim")
        ax.tick_params(labelsize=7, colors=APAGADO)
        ax.set_title(f"{r.fuente}/{r.escenario}  {r.modo_real} -> {r.pred_rf} ({r.conf_rf:.2f})\n{r.tipo.replace('_', ' ')}",
                     fontsize=8.5, color=TINTA, loc="left")
        ax2 = fig.add_subplot(sub[1])
        ax2.plot(np.arange(len(v)), v, color=colores[r.tipo], lw=1)
        ax2.axhline(8 / 3.6, color=APAGADO, lw=0.8, ls="--")
        ax2.tick_params(labelsize=7, colors=APAGADO)
        ax2.set_ylabel("m/s", fontsize=7, color=APAGADO)
        for a_ in (ax, ax2):
            for s in ("top", "right"):
                a_.spines[s].set_visible(False)
    fig.suptitle("20 peores errores del RF (mayor confianza). Circulo = inicio, cuadro = fin; "
                 "linea discontinua = 8 km/h (umbral)", x=0.01, ha="left", fontsize=13, color=TINTA)
    fig.savefig(ruta, dpi=100, bbox_inches="tight")
    plt.close(fig)


# ── Principal ───────────────────────────────────────────────────────────────


def ejecutar(geolife_filas: int = 80_000, cap_sumo: int = 15_000) -> dict:
    dfs, todos_arrs = [], []

    def anadir(filas, arrs):
        if not filas:
            return
        d = predecir(filas, arrs)
        d["idx_arr"] = np.arange(len(todos_arrs), len(todos_arrs) + len(arrs))
        dfs.append(d)
        todos_arrs.extend(arrs)

    anadir(*cargar_geolife(geolife_filas))
    for semilla in SEMILLAS:
        anadir(*cargar_sumo(semilla, 5, cap_sumo))
    for sigma in (3, 8, 10, 15):
        anadir(*cargar_sumo(101, sigma, cap_sumo))
    df = pd.concat(dfs, ignore_index=True)
    print(df.groupby(["fuente", "escenario", "sigma"], dropna=False).size().to_string())

    met, conf = tablas(df)
    REPORTES.mkdir(exist_ok=True)
    met.round(4).to_csv(REPORTES / "errores_contexto.csv", index=False)
    conf.to_csv(REPORTES / "errores_confusion.csv", index=False)

    peores = elegir_peores(df)
    tipos = [clasificar_error(r.modo_real, todos_arrs[int(r.idx_arr)], r.sigma) for _, r in peores.iterrows()]
    peores["tipo"] = [t[0] for t in tipos]
    peores["motivo"] = [t[1] for t in tipos]
    cols = ["fuente", "escenario", "sigma", "semilla", "usuario_id", "segmento_id", "t_inicio", "modo_real",
            "pred_rf", "conf_rf", "pred_umbral", "vel_kmh", "precision_m", "tipo", "motivo", "idx_arr"]
    peores[cols].round(3).to_csv(REPORTES / "peores_errores.csv", index=False)

    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    figura_contexto(met, EVIDENCIAS / "s2_errores-contexto.png")
    figura_peores(peores, todos_arrs, EVIDENCIAS / "s2_peores-errores.png")
    print(peores[["fuente", "escenario", "modo_real", "pred_rf", "conf_rf", "tipo"]].to_string())
    return {"n_ventanas": len(df), "tipos": peores["tipo"].value_counts().to_dict()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geolife-filas", type=int, default=80_000)
    ap.add_argument("--cap-sumo", type=int, default=15_000)
    a = ap.parse_args()
    print(ejecutar(a.geolife_filas, a.cap_sumo))


if __name__ == "__main__":
    main()
