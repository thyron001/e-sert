"""Figuras finales del informe (S4-2), solo desde `resultados/final/resumen.csv` (no corre SUMO).

    python kpis/figuras_finales.py            # o: python -m kpis.figuras_finales

- `informe/figuras/tyrone/*.png` a 300 dpi (para el informe y las diapositivas);
- `../evidencias/s2_kpis-finales.png` y `../evidencias/s2_falsas-liberaciones.png` a 150 dpi.

Colores del equipo (`docs/EQUIPO.md`): rf_final en el azul de Tyrone `#1E63D6`, umbral en el tomate
de Freddy `#FF7043` (par distinguible con daltonismo y en gris por luminosidad), búsqueda a ciegas en
gris discontinuo con su banda IC. Ejes y textos en español, coma decimal.
"""
from __future__ import annotations

import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parent
if str(CODIGO) not in sys.path:
    sys.path.insert(0, str(CODIGO))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RESUMEN = AQUI / "resultados" / "final" / "resumen.csv"
INFORME = CODIGO / "informe" / "figuras" / "tyrone"
EVIDENCIAS = CODIGO.parent / "evidencias"
COLOR = {"rf_final": "#1E63D6", "umbral": "#FF7043", "ciegas": "#6E6E6E", "oraculo": "#0B2540"}
ETQ = {"rf_final": "rf_final (RF de Pablo)", "umbral": "Umbral", "ciegas": "Búsqueda a ciegas (0 %)",
       "oraculo": "Oráculo: guiado con la ocupación real (sensibilidad)"}
DESPLAZ = {"umbral": -1.5, "rf_final": 1.5}

plt.rcParams.update({
    "font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10, "legend.fontsize": 9,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#DDDDDD",
    "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.edgecolor": "#888888", "axes.formatter.use_locale": False,
    "savefig.bbox": "tight",
})
COMA = mticker.FuncFormatter(lambda x, _: f"{x:g}".replace(".", ","))

PANELES = [
    ("busqueda", "Tiempo de búsqueda medio", "s", 1),
    ("distancia", "Distancia de búsqueda media", "m", 1),
    ("co2", "CO₂ de búsqueda por vehículo", "g", 1),
    ("ocupacion", "Ocupación media en la hora pico", "%", 100),
]


def _cols(k):
    if k == "ocupacion":
        return "ocupacion_media", "ocupacion_ic_lo", "ocupacion_ic_hi"
    return f"{k}_media", f"{k}_ic_lo", f"{k}_ic_hi"


def _err(media, lo, hi, escala):
    """Barras asimétricas; sin IC (n = 1) o con el redondeo invertido, la barra es 0."""
    abajo = np.clip(np.nan_to_num((np.asarray(media, float) - np.asarray(lo, float)) * escala), 0, None)
    arriba = np.clip(np.nan_to_num((np.asarray(hi, float) - np.asarray(media, float)) * escala), 0, None)
    return np.vstack([abajo, arriba])


def panel_vs_penetracion(ax, res, k, titulo, unidad, escala):
    m, lo, hi = _cols(k)
    base = res[res["escenario"] == "ciegas"].iloc[0]
    ax.axhline(base[m] * escala, color=COLOR["ciegas"], ls="--", lw=1.5, label=ETQ["ciegas"])
    ax.axhspan(base[lo] * escala, base[hi] * escala, color=COLOR["ciegas"], alpha=0.13, lw=0)
    for clf in ("umbral", "rf_final"):
        g = res[res["clasificador"] == clf].sort_values("penetracion")
        if g.empty:
            continue
        x = g["penetracion"] + DESPLAZ[clf]
        y = g[m] * escala
        err = _err(g[m], g[lo], g[hi], escala)
        ax.errorbar(x, y, yerr=err, fmt="-o", ms=6, lw=2, capsize=4, color=COLOR[clf], mec="white", mew=1.2,
                    label=ETQ[clf])
    o = res[res["escenario"] == "p50_oraculo"]
    if len(o) and not pd.isna(o[m].iloc[0]):
        r = o.iloc[0]
        ax.errorbar([r["penetracion"]], [r[m] * escala], yerr=_err(o[m], o[lo], o[hi], escala),
                    fmt="D", ms=7, capsize=4, color=COLOR["oraculo"], mec="white", mew=1.2, label=ETQ["oraculo"])
    ax.set_xticks([0, 20, 50, 80])
    ax.set_xlim(-6, 86)
    ax.set_xlabel("Penetración de la app (%)")
    ax.set_ylabel(f"{titulo} ({unidad})")
    ax.set_title(titulo, loc="left")
    ax.yaxis.set_major_formatter(COMA)


def figura_2x2(res, ruta_png, dpi):
    fig, ejes = plt.subplots(2, 2, figsize=(10, 7.2))
    for ax, (k, t, u, e) in zip(ejes.flat, PANELES):
        panel_vs_penetracion(ax, res, k, t, u, e)
    h, l = ejes.flat[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.03))
    n = int(res[res["escenario"] != "p50_oraculo"]["n_semillas"].min())
    o = res[res["escenario"] == "p50_oraculo"]["n_semillas"]
    extra = f"; oráculo: {int(o.iloc[0])} semilla{'s' if int(o.iloc[0]) != 1 else ''}" if len(o) else ""
    fig.suptitle(f"KPIs frente a la penetración de la app (media e IC 95 %, {n} semillas{extra})", x=0.02, ha="left",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    fig.savefig(ruta_png, dpi=dpi)
    plt.close(fig)


def figura_simple(res, k, t, u, e, ruta_png, dpi):
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    panel_vs_penetracion(ax, res, k, t, u, e)
    ax.legend(frameon=False)
    fig.savefig(ruta_png, dpi=dpi)
    plt.close(fig)


def figura_falsas(res, ruta_png, dpi):
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    pens = [20, 50, 80]
    ancho = 0.36
    for i, clf in enumerate(("umbral", "rf_final")):
        g = res[res["clasificador"] == clf].set_index("penetracion").reindex(pens)
        x = np.arange(len(pens)) + (i - 0.5) * (ancho + 0.04)
        err = _err(g["falsas_100"], g["falsas_100_wilson_lo"], g["falsas_100_wilson_hi"], 1)
        ax.bar(x, g["falsas_100"], ancho, yerr=err, capsize=4, color=COLOR[clf], label=ETQ[clf], edgecolor="white",
               linewidth=2, error_kw=dict(ecolor="#333333", lw=1.2))
        for xi, v, n in zip(x, g["falsas_100"], g["n_sesiones"]):
            if not np.isnan(v):
                ax.annotate(f"{v:.1f}".replace(".", ","), (xi, v), xytext=(0, 3), textcoords="offset points",
                            ha="center", va="bottom", fontsize=8.5, color="#222222")
    ax.set_xticks(np.arange(len(pens)), [f"{p} %" for p in pens])
    ax.set_xlabel("Penetración de la app")
    ax.set_ylabel("Falsas liberaciones por 100 sesiones")
    ax.set_title("Falsas liberaciones: umbral frente a rf_final (IC de Wilson 95 %)", loc="left")
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(COMA)
    ax.legend(frameon=False)
    fig.savefig(ruta_png, dpi=dpi)
    plt.close(fig)


def figura_precision(res, ruta_png, dpi):
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for clf in ("umbral", "rf_final"):
        g = pd.concat([res[res["escenario"] == "ciegas"], res[res["clasificador"] == clf]]).sort_values("penetracion")
        x = g["penetracion"] + DESPLAZ[clf]
        err = np.vstack([g["precision_mapa"] - g["precision_mapa_ic_lo"], g["precision_mapa_ic_hi"] - g["precision_mapa"]])
        ax.errorbar(x, 100 * g["precision_mapa"], yerr=100 * np.nan_to_num(err), fmt="-o", ms=6, lw=2, capsize=4,
                    color=COLOR[clf], mec="white", mew=1.2, label=ETQ[clf])
    ax.set_xticks([0, 20, 50, 80])
    ax.set_xlabel("Penetración de la app (%)")
    ax.set_ylabel("Precisión del mapa de ocupación (%)")
    ax.set_title("Precisión del mapa de ocupación (media e IC 95 % t)", loc="left")
    ax.yaxis.set_major_formatter(COMA)
    ax.legend(frameon=False)
    fig.savefig(ruta_png, dpi=dpi)
    plt.close(fig)


def generar(resumen: Path = RESUMEN, informe: Path = INFORME, evidencias: Path = EVIDENCIAS) -> list:
    res = pd.read_csv(resumen)
    informe.mkdir(parents=True, exist_ok=True)
    evidencias.mkdir(parents=True, exist_ok=True)
    rutas = []
    figura_2x2(res, informe / "f01_kpis_vs_penetracion.png", 300)
    figura_simple(res, "busqueda", "Tiempo de búsqueda medio", "s", 1, informe / "f02_busqueda_vs_penetracion.png", 300)
    figura_simple(res, "co2", "CO₂ de búsqueda por vehículo", "g", 1, informe / "f03_co2_busqueda.png", 300)
    figura_falsas(res, informe / "f04_falsas_liberaciones.png", 300)
    figura_precision(res, informe / "f05_precision_mapa.png", 300)
    rutas += sorted(informe.glob("f0*.png"))
    figura_2x2(res, evidencias / "s2_kpis-finales.png", 150)
    figura_falsas(res, evidencias / "s2_falsas-liberaciones.png", 150)
    rutas += [evidencias / "s2_kpis-finales.png", evidencias / "s2_falsas-liberaciones.png"]
    return rutas


if __name__ == "__main__":
    for r in generar():
        print(r)
