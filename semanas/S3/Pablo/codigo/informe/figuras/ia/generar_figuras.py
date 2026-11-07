"""
Figuras de la sección de IA del informe (PNG a 300 dpi y PDF), ancho de columna 6,5 in.

Regenerar, desde `semanas/S3/Pablo/codigo`:

    python3 informe/figuras/ia/generar_figuras.py              # figuras 1 a 5 (segundos)
    python3 informe/figuras/ia/generar_figuras.py --latencia   # además la 6 (≈2 min: corre el benchmark)

Fuentes (todas en `ia/`): reportes/metricas_generalizacion.json (fig 1), reportes/curvas_sigma.csv
(fig 2), modelos/rf_v1.json (fig 3), reportes/errores_contexto.csv (fig 4),
reportes/suavizado_k.csv y suavizado_k_contrato.csv (fig 5), ia/bench_inferencia.py (fig 6).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parents[2]
IA = CODIGO / "ia"
DPI = 300

INK, MUTED, GRID = "#222222", "#666666", "#DDDDDD"
AZUL, AZUL_CLARO, GRIS, GRIS_CLARO = "#1F5FA6", "#7FB0E0", "#6B6F78", "#B9BCC4"
CLASES = ["a_pie", "quieto", "vehiculo"]
ETQ = {"a_pie": "a pie", "quieto": "quieto", "vehiculo": "vehículo"}

plt.rcParams.update({
    "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5, "xtick.labelsize": 8,
    "ytick.labelsize": 8, "legend.fontsize": 8, "text.color": INK, "axes.labelcolor": INK,
    "axes.edgecolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "pdf.fonttype": 42, "font.family": "DejaVu Sans",
})


def limpiar(ax, grid="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if grid:
        ax.grid(axis=grid, color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def guardar(fig, nombre):
    fig.savefig(AQUI / f"{nombre}.png", dpi=DPI, bbox_inches="tight")
    fig.savefig(AQUI / f"{nombre}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("OK", nombre)


# ── Figura 1: matriz de confusión del RF en usuarios no vistos ─────────────


def fig1():
    rf = json.loads((IA / "reportes/metricas_generalizacion.json").read_text())["fuentes"]["geolife_prueba"]["rf"]
    cm = np.array(rf["confusion_matrix"])  # normalizada por fila, orden CLASES (evaluar_generalizacion.py)
    soporte = np.array([rf["por_clase"][c]["support"] for c in CLASES])
    cuentas = np.rint(cm * soporte[:, None]).astype(int)
    fig, ax = plt.subplots(figsize=(4.6, 3.7))
    im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            col = "white" if cm[i, j] > 0.5 else INK
            ax.text(j, i, f"{cm[i, j]:.2f}\n({cuentas[i, j]:,})".replace(",", " "), ha="center", va="center",
                    color=col, fontsize=8.5)
    ax.set_xticks(range(3), [ETQ[c] for c in CLASES])
    ax.set_yticks(range(3), [ETQ[c] for c in CLASES])
    ax.set_xlabel("Clase predicha")
    ax.set_ylabel("Clase real")
    ax.set_title("Random Forest, 10 usuarios no vistos de GeoLife", loc="left")
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Proporción de la fila")
    cb.ax.tick_params(labelsize=8)
    guardar(fig, "fig1_matriz-confusion-rf")


# ── Figura 2: macro-F1 frente a σ ──────────────────────────────────────────


def fig2():
    d = pd.read_csv(IA / "reportes/curvas_sigma.csv")
    series = [("umbral", "Umbral", GRIS, "-", "s"), ("rf", "Random Forest", AZUL, "-", "o"),
              ("rf_suavizado", "RF + suavizado", AZUL_CLARO, "--", "^")]
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    for clave, etq, col, ls, mk in series:
        s = d[d.sistema == clave].sort_values("sigma")
        ax.fill_between(s.sigma, s.macro_f1_ic_lo, s.macro_f1_ic_hi, color=col, alpha=0.18, lw=0)
        ax.plot(s.sigma, s.macro_f1, color=col, ls=ls, marker=mk, ms=4.5, lw=1.8, label=etq,
                markeredgecolor="white", markeredgewidth=0.6)
        ax.annotate(etq, (s.sigma.iloc[-1], s.macro_f1.iloc[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8, color=INK)
    ax.set_xlim(-0.5, 19)
    ax.set_ylim(0, 1)
    ax.set_xticks([0, 3, 5, 8, 10, 15])
    ax.set_xlabel("σ del ruido GPS (m); 0 = traza limpia")
    ax.set_ylabel("macro-F1 en SUMO")
    ax.set_title("Escenarios SUMO con ruido AR(1); banda: IC 95 %", loc="left")
    limpiar(ax)
    ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(1.0, 1.0))
    guardar(fig, "fig2_curvas-sigma")


# ── Figura 3: importancia por permutación ──────────────────────────────────


def fig3():
    imp = json.loads((IA / "modelos/rf_v1.json").read_text())["importancia_features"]
    s = pd.Series(imp).sort_values()
    fig, ax = plt.subplots(figsize=(6.5, 4.4))
    ax.barh(s.index, s.values, color=AZUL, height=0.7)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_xscale("symlog", linthresh=1e-3)
    ax.set_xticks([-1e-3, 0, 1e-3, 1e-2, 1e-1], ["−0,001", "0", "0,001", "0,01", "0,1"])
    ax.set_xlim(-3e-3, 0.7)
    for nombre in ("desplazamiento_neto", "rectitud", "jerk_medio_abs"):
        v = s[nombre]
        ax.text(v * 1.25, nombre, f"{v:.3f}".replace(".", ","), va="center", ha="left", fontsize=8, color=INK)
    ax.set_xlabel("Importancia por permutación (escala logarítmica simétrica)")
    ax.set_title("Valores ≤ 0 indican ruido: permutar la característica no empeora el modelo", loc="left")
    limpiar(ax, grid="x")
    guardar(fig, "fig3_importancia")


# ── Figura 4: recall por contexto ──────────────────────────────────────────


def fig4():
    t = pd.read_csv(IA / "reportes/errores_contexto.csv")
    columnas = [("geolife", "velocidad", ["0-3", "3-8", "8-15", ">15"], "GeoLife: velocidad media (km/h)"),
                ("sumo", "velocidad", ["0-3", "3-8", "8-15", ">15"], "SUMO: velocidad media (km/h)"),
                ("sumo", "precision", ["<10", "10-25", ">25"], "SUMO: precisión (m)")]
    fig, ejes = plt.subplots(2, 3, figsize=(6.5, 4.8), sharey=True, gridspec_kw={"width_ratios": [4, 4, 3]})
    ancho = 0.38
    for r, clase in enumerate(("vehiculo", "quieto")):
        for c, (fuente, tipo, valores, titulo) in enumerate(columnas):
            ax = ejes[r, c]
            x = np.arange(len(valores))
            etiquetas = []
            for i, v in enumerate(valores):
                n = 0
                for j, (sis, col) in enumerate((("umbral", GRIS), ("rf", AZUL))):
                    f = t[(t.fuente == fuente) & (t.contexto_tipo == tipo) & (t.contexto_valor == v)
                          & (t.sistema == sis) & (t.clase == clase)]
                    n = int(f.n_clase.iloc[0]) if len(f) else 0
                    pos = x[i] + (j - 0.5) * ancho
                    if n == 0:
                        ax.text(pos, 2, "s/d", ha="center", va="bottom", fontsize=7.5, color=MUTED, rotation=90)
                        continue
                    val = 100 * float(f.recall.iloc[0])
                    ax.bar(pos, val, ancho * 0.92, color=col, label=("Umbral" if sis == "umbral" else "Random Forest"))
                    ax.text(pos + (0.06 if sis == "umbral" else -0.06), val + 1.5, f"{val:.0f}", ha=("right" if sis == "umbral" else "left"), va="bottom", fontsize=8)
                etiquetas.append(f"{v}\n{n / 1000:.1f} k".replace(".", ",") if n >= 1000 else f"{v}\n{n}")
            ax.set_xticks(x, etiquetas)
            ax.set_ylim(0, 112)
            limpiar(ax)
            if r == 0:
                ax.set_title(titulo, fontsize=8, loc="left")
            if c == 0:
                ax.set_ylabel(f"Recall de {ETQ[clase]} (%)")
    h, l = ejes[0, 0].get_legend_handles_labels()
    por = dict(zip(l, h))
    fig.legend(por.values(), por.keys(), loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.text(0.5, 0.075, "Bajo cada rango: número de ventanas de la clase (k = miles); s/d = sin datos", ha="center", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    guardar(fig, "fig4_recall-contexto")


# ── Figura 5: suavizado vs falsas liberaciones ─────────────────────────────

SERIES5 = [("rf", "mayoria", "RF · mayoría", AZUL), ("rf", "prob_media", "RF · prob. media", AZUL_CLARO),
           ("umbral", "mayoria", "Umbral · mayoría", GRIS), ("umbral", "prob_media", "Umbral · prob. media", GRIS_CLARO)]
KS = (1, 3, 5)


def fig5():
    tablas = [("Máquina de Freddy", pd.read_csv(IA / "reportes/suavizado_k.csv")),
              ("Máquina del contrato §3", pd.read_csv(IA / "reportes/suavizado_k_contrato.csv"))]
    fila = lambda tb, s, m, k: tb[(tb.sistema == s) & (tb.metodo == m) & (tb.k == k)].iloc[0]
    fig, ejes = plt.subplots(3, 2, figsize=(6.5, 7.0), sharex="col")
    ancho, x = 0.2, np.arange(len(KS))
    for c, (titulo, tb) in enumerate(tablas):
        for j, (s, m, etq, col) in enumerate(SERIES5):
            filas = [fila(tb, s, m, k) for k in KS]
            f = np.array([r.falsas_100 for r in filas])
            err = [f - np.array([r.falsas_ic95_inf for r in filas]), np.array([r.falsas_ic95_sup for r in filas]) - f]
            pos = x + (j - 1.5) * ancho
            ejes[0, c].bar(pos, f, ancho * 0.9, yerr=err, color=col, label=etq,
                           error_kw={"ecolor": INK, "elinewidth": 0.8, "capsize": 1.5})
            ejes[1, c].plot(x + (j - 1.5) * 0.06, [r.retardo_mediano_s for r in filas], marker="o", color=col,
                            lw=1.6, ms=4.5, markeredgecolor="white")
            ejes[2, c].bar(pos, [r.cierre_correcto_pct for r in filas], ancho * 0.9, color=col)
        ejes[0, c].set_title(titulo, loc="left", fontsize=9)
        ejes[1, c].axhline(60, color=INK, ls="--", lw=1)
        ejes[1, c].text(len(KS) - 0.55, 62, "límite 60 s", ha="right", fontsize=8)
        ejes[1, c].set_ylim(0, 75)
        ejes[2, c].set_ylim(0, 100)
        ejes[2, c].set_xticks(x, [f"k = {k}" for k in KS])
    ejes[1, 0].text(0.03, 0.93, "solo cuenta el 1–4 % que cierra", transform=ejes[1, 0].transAxes, fontsize=8, va="top")
    ejes[0, 0].set_ylabel("Falsas liberaciones\npor 100 sesiones")
    ejes[1, 0].set_ylabel("Retardo mediano\nde cierre (s)")
    ejes[2, 0].set_ylabel("Sesiones cerradas\ncorrectamente (%)")
    for ax in ejes.ravel():
        limpiar(ax)
    h, l = ejes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    guardar(fig, "fig5_suavizado-falsas")


def fig6():
    subprocess.run([sys.executable, "-m", "ia.bench_inferencia", "--png", str(AQUI / "fig6_latencia.png"),
                    "--dpi", str(DPI), "--pdf", "--figsize", "6.5", "3.8", "--titulo", "RF v1, 200 árboles"],
                   cwd=CODIGO, check=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--latencia", action="store_true", help="también corre el benchmark y genera la fig 6")
    a = ap.parse_args()
    for f in (fig1, fig2, fig3, fig4, fig5):
        f()
    if a.latencia:
        fig6()
