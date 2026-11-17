"""Figuras finales de KPIs (S3-2): `python -m kpis.figuras` regenera todo desde el CSV.

Corre en la computadora, desde `semanas/S3/Tyrone/codigo`:

    kpis/.venv/bin/python -m kpis.figuras [--csv kpis/resultados/experimentos.csv] [--destino kpis/figuras]

Cada figura va en PNG (dpi=150) y PDF vectorial. Estilo único: 6,4 × 4 in, 10 pt, paleta fija
apta para daltónicos (Okabe-Ito: rf azul, umbral naranja; la búsqueda a ciegas, gris discontinuo
con su banda IC). Cada punto lleva su IC 95 % (t de Student entre semillas). Si una columna está
toda en NaN (KPIs de sistema pendientes), la figura sale igual con la leyenda "pendiente".
"""
from __future__ import annotations

import argparse
import gzip
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from kpis import analisis as an  # noqa: E402

AQUI = Path(__file__).resolve().parent
COLORES = {"rf": "#0072B2", "umbral": "#E69F00", "base": "#6E6E6E", "texto": "#222222", "rejilla": "#DDDDDD"}
ETIQUETAS = {"rf": "RF (Pablo)", "umbral": "Umbral", "base": "Búsqueda a ciegas (0 %)"}
DESPLAZ = {"umbral": -1.4, "rf": 1.4}
PENS = [0, 20, 50, 80]
CDF_COLORES = {0: "#6E6E6E", 20: "#9ECAE1", 50: "#4292C6", 80: "#08519C"}  # secuencial, un tono

plt.rcParams.update({
    "figure.figsize": (6.4, 4.0), "font.size": 10, "axes.titlesize": 10.5, "axes.labelsize": 10,
    "legend.fontsize": 9, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": COLORES["rejilla"], "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.edgecolor": "#888888", "text.color": COLORES["texto"], "axes.labelcolor": COLORES["texto"],
    "savefig.bbox": "tight", "pdf.fonttype": 42,
})


def _guardar(fig, destino: Path, nombre: str) -> list:
    destino.mkdir(parents=True, exist_ok=True)
    rutas = [destino / f"{nombre}.png", destino / f"{nombre}.pdf"]
    fig.savefig(rutas[0], dpi=150)
    fig.savefig(rutas[1])
    plt.close(fig)
    return rutas


def _pendiente(ax, texto="pendiente: KPI de sistema sin datos (mock de Freddy)"):
    ax.text(0.5, 0.5, texto, transform=ax.transAxes, ha="center", va="center", color=COLORES["base"],
            fontsize=10, style="italic", bbox=dict(fc="white", ec=COLORES["rejilla"]))


def _nota_n(ax, df):
    n = df.groupby(["penetracion", "clasificador"]).size()
    ax.annotate(f"IC 95 % t de Student entre semillas (n = {n.min() if n.min() == n.max() else f'{n.min()}–{n.max()}'} por punto)",
                xy=(0, -0.2), xycoords="axes fraction", fontsize=8, color="#555555")


def figura_vs_penetracion(df, kpi, titulo, ylabel, escala=1.0, nombre="", destino=None):
    """KPI frente a penetración: rf y umbral con IC 95 %, y la línea base gris con su banda."""
    fig, ax = plt.subplots()
    res = an.resumen(df, kpi)
    if res["media"].notna().sum() == 0:
        _pendiente(ax)
    base = an.ic95(an.linea_base(df, kpi).tolist())
    if not np.isnan(base["media"]):
        ax.axhline(base["media"] * escala, color=COLORES["base"], ls="--", lw=1.5, label=ETIQUETAS["base"])
        if base["n"] >= 2:
            ax.axhspan(base["lo"] * escala, base["hi"] * escala, color=COLORES["base"], alpha=0.12, lw=0)
    for clf in ("umbral", "rf"):
        r = res[(res["clasificador"] == clf) & (res["penetracion"] > 0)].sort_values("penetracion")
        if r.empty or r["media"].notna().sum() == 0:
            continue
        x = r["penetracion"] + DESPLAZ[clf]
        ax.errorbar(x, r["media"] * escala, yerr=r["semiancho"].fillna(0) * escala, fmt="-o", ms=6, lw=2,
                    capsize=4, color=COLORES[clf], label=ETIQUETAS[clf], mec="white", mew=1.2)
    ax.set_xticks(PENS)
    ax.set_xlim(-6, 86)
    ax.set_xlabel("Penetración de la app (% de autos que buscan con app)")
    ax.set_ylabel(ylabel)
    ax.set_title(titulo, loc="left")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(frameon=False, loc="best")
    _nota_n(ax, df)
    return _guardar(fig, destino, nombre)


def f4_falsas(df, destino):
    """Falsas liberaciones por 100 sesiones, umbral vs rf, barras agrupadas con IC."""
    fig, ax = plt.subplots()
    res = an.resumen(df, "falsas_lib_100")
    res = res[res["penetracion"] > 0]
    pens = [p for p in PENS if p > 0]
    ancho = 0.36
    if res["media"].notna().sum() == 0:
        _pendiente(ax)
    for i, clf in enumerate(("umbral", "rf")):
        r = res[res["clasificador"] == clf].set_index("penetracion").reindex(pens)
        x = np.arange(len(pens)) + (i - 0.5) * (ancho + 0.03)
        ax.bar(x, r["media"].fillna(0), ancho, yerr=r["semiancho"].fillna(0), capsize=4, color=COLORES[clf],
               label=ETIQUETAS[clf], edgecolor="white", linewidth=2, error_kw=dict(ecolor="#333333", lw=1.2))
        for xi, m in zip(x, r["media"]):
            if not np.isnan(m):
                bajo = m < 8  # barra casi nula: la cifra va encima, en color de texto
                ax.text(xi, m + 1 if bajo else 0.5, f"{m:.1f}".replace(".", ","), ha="center", va="bottom",
                        fontsize=8.5, color=COLORES["texto"] if bajo else "white", fontweight="bold")
    ax.set_xticks(np.arange(len(pens)), [f"{p} %" for p in pens])
    ax.set_xlabel("Penetración de la app")
    ax.set_ylabel("Falsas liberaciones por 100 sesiones")
    ax.set_title("F4 · Falsas liberaciones: umbral frente a RF", loc="left")
    ax.legend(frameon=False)
    ax.grid(axis="x", visible=False)
    _nota_n(ax, df)
    return _guardar(fig, destino, "F4_falsas_liberaciones")


def _sesiones(dir_ses: Path) -> pd.DataFrame:
    partes = []
    for ruta in sorted(Path(dir_ses).glob("*.csv.gz")):
        try:
            with gzip.open(ruta, "rt", encoding="utf-8") as f:
                d = pd.read_csv(f)
        except pd.errors.EmptyDataError:  # al 0 % no hay sesiones: archivo vacío
            continue
        if d.empty:
            continue
        pen, clf, sem = ruta.name[:-7].split("_")[:3]
        d["penetracion"], d["clasificador"], d["semilla"] = int(pen[1:]), clf, int(sem[1:])
        partes.append(d)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def f5_retardo(df, destino, dir_ses):
    """Retardo de cierre: caja por sesión (todas las semillas) + media de medianas con IC 95 %."""
    fig, ax = plt.subplots()
    ses = _sesiones(dir_ses)
    res = an.resumen(df, "retardo_cierre_mediana_s")
    pens = [p for p in PENS if p > 0]
    hay = False
    for i, clf in enumerate(("umbral", "rf")):
        pos = np.arange(len(pens)) + (i - 0.5) * 0.4
        if not ses.empty and "retardo_cierre_s" in ses:
            datos = [ses[(ses.penetracion == p) & (ses.clasificador == clf)]["retardo_cierre_s"].dropna().to_numpy()
                     for p in pens]
            if any(len(d) for d in datos):
                hay = True
                bp = ax.boxplot([d if len(d) else [np.nan] for d in datos], positions=pos, widths=0.32,
                                patch_artist=True, showfliers=False, manage_ticks=False)
                for caja in bp["boxes"]:
                    caja.set(facecolor=COLORES[clf], alpha=0.35, edgecolor=COLORES[clf])
                for parte in ("whiskers", "caps", "medians"):
                    for l in bp[parte]:
                        l.set(color=COLORES[clf])
        r = res[res.clasificador == clf].set_index("penetracion").reindex(pens)
        if r["media"].notna().any():
            hay = True
            ax.errorbar(pos, r["media"], yerr=r["semiancho"].fillna(0), fmt="D", ms=6, color=COLORES[clf],
                        mec="white", capsize=4, label=f"{ETIQUETAS[clf]} (media de medianas ± IC 95 %)")
    if not hay:
        _pendiente(ax)
    ax.set_xticks(np.arange(len(pens)), [f"{p} %" for p in pens])
    ax.set_xlabel("Penetración de la app")
    ax.set_ylabel("Retardo de cierre de la sesión (s)")
    ax.set_title("F5 · Retardo de cierre (cajas: sesiones de todas las semillas)", loc="left")
    if hay:
        ax.legend(frameon=False, fontsize=8)
    _nota_n(ax, df)
    return _guardar(fig, destino, "F5_retardo_cierre")


def f8_cdf(destino, veh):
    """CDF empírica del tiempo de búsqueda por penetración (rf; el 0 % es la búsqueda a ciegas)."""
    fig, ax = plt.subplots()
    if veh.empty:
        _pendiente(ax, "pendiente: falta el detalle por vehículo (kpis/resultados/vehiculos)")
    for p in ([] if veh.empty else PENS):
        clf = "umbral" if p == 0 else "rf"
        x = np.sort(veh[(veh.penetracion == p) & (veh.clasificador == clf)]["tiempo_busqueda_s"].dropna())
        if not len(x):
            continue
        y = np.arange(1, len(x) + 1) / len(x)
        ax.step(x, y, where="post", lw=2, color=CDF_COLORES[p], ls="--" if p == 0 else "-",
                label=f"{p} %" + (" (a ciegas)" if p == 0 else " (RF)") + f", n = {len(x)}")
    ax.set_xscale("symlog", linthresh=10)
    ax.set_xlabel("Tiempo de búsqueda (s, escala log a partir de 10 s)")
    ax.set_ylabel("Fracción de vehículos ≤ x")
    ax.set_ylim(0, 1.01)
    ax.set_title("F8 · CDF del tiempo de búsqueda por penetración", loc="left")
    if not veh.empty:
        ax.legend(frameon=False, loc="lower right")
    return _guardar(fig, destino, "F8_cdf_busqueda")


def generar(csv: Path, destino: Path, dir_veh: Path, dir_ses: Path) -> list:
    df = an.cargar(csv)
    veh = an.cargar_vehiculos(dir_veh) if dir_veh.exists() else pd.DataFrame()
    rutas = []
    rutas += figura_vs_penetracion(df, "busqueda_media_s", "F1 · Tiempo de búsqueda medio frente a penetración",
                                   "Tiempo de búsqueda medio (s)", nombre="F1_busqueda_vs_penetracion",
                                   destino=destino)
    rutas += figura_vs_penetracion(df, "distancia_busqueda_media_m", "F2 · Distancia de búsqueda media",
                                   "Distancia de búsqueda media (m)", nombre="F2_distancia_busqueda",
                                   destino=destino)
    rutas += figura_vs_penetracion(df, "co2_busqueda_kg", "F3 · CO₂ emitido buscando parqueo",
                                   "CO₂ de búsqueda (kg/h, hora pico)", nombre="F3_co2_busqueda", destino=destino)
    rutas += f4_falsas(df, destino)
    rutas += f5_retardo(df, destino, dir_ses)
    rutas += figura_vs_penetracion(df, "error_fact_medio_usd",
                                   "F6 · Error de facturación de la app frente a la tarjeta SERT",
                                   "Error medio por sesión (USD; app − tiempo real)",
                                   nombre="F6_error_facturacion", destino=destino)
    rutas += figura_vs_penetracion(df, "precision_mapa", "F7 · Precisión del mapa de ocupación",
                                   "Precisión del mapa (%)", escala=100, nombre="F7_precision_mapa",
                                   destino=destino)
    rutas += f8_cdf(destino, veh)
    return rutas


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", default=str(an.CSV))
    ap.add_argument("--destino", default=str(AQUI / "figuras"))
    ap.add_argument("--vehiculos", default=str(an.RESULTADOS / "vehiculos"))
    ap.add_argument("--sesiones", default=str(an.RESULTADOS / "sesiones"))
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    rutas = generar(Path(args.csv), Path(args.destino), Path(args.vehiculos), Path(args.sesiones))
    print(f"{len(rutas)} archivos en {time.perf_counter() - t0:.1f} s")
    for r in rutas:
        print(" ", r)


if __name__ == "__main__":
    main()
