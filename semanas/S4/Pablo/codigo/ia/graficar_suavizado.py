"""
Gráfica de evidencia: falsas liberaciones por 100 sesiones (barras con IC 95 %), retardo mediano
de cierre y porcentaje de cierres correctos, para k = 1, 3 y 5, umbral vs rf.

    python3 -m ia.graficar_suavizado [--csv ia/reportes/suavizado_k.csv] [--png RUTA]

Dos columnas: la máquina de estados de Freddy tal como está (`suavizado_k.csv`) y la que sigue
literalmente la tabla del contrato §3 (`suavizado_k_contrato.csv`). El retardo va en su propio
panel (no en un segundo eje) para no mezclar dos escalas en un mismo eje.
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ_IA = Path(__file__).resolve().parent
INK, MUTED, GRID = "#222222", "#666666", "#DDDDDD"
SERIES = [  # (sistema, método, etiqueta, color)
    ("rf", "mayoria", "RF · mayoría", "#1F5FA6"),
    ("rf", "prob_media", "RF · prob. media", "#7FB0E0"),
    ("umbral", "mayoria", "Umbral · mayoría", "#6B6F78"),
    ("umbral", "prob_media", "Umbral · prob. media", "#B9BCC4"),
]
KS = (1, 3, 5)
LIMITE_RETARDO_S = 60


def _fila(tb, sistema, metodo, k):
    return tb[(tb["sistema"] == sistema) & (tb["metodo"] == metodo) & (tb["k"] == k)].iloc[0]


def graficar(csv_freddy: Path, csv_contrato: Path, png: Path) -> None:
    tablas = [("Máquina de Freddy (tal como está)", pd.read_csv(csv_freddy)),
              ("Máquina del contrato §3 (sin REGRESANDO → A_PIE)", pd.read_csv(csv_contrato))]
    fig, ejes = plt.subplots(3, 2, figsize=(12, 9.2), sharex="col")
    ancho = 0.2
    x = np.arange(len(KS))
    for c, (titulo, tb) in enumerate(tablas):
        for j, (sis, met, etq, col) in enumerate(SERIES):
            pos = x + (j - 1.5) * ancho
            filas = [_fila(tb, sis, met, k) for k in KS]
            f = np.array([r["falsas_100"] for r in filas])
            lo = f - np.array([r["falsas_ic95_inf"] for r in filas])
            hi = np.array([r["falsas_ic95_sup"] for r in filas]) - f
            ejes[0, c].bar(pos, f, ancho * 0.9, yerr=[lo, hi], color=col, label=etq,
                           error_kw={"ecolor": INK, "elinewidth": 1, "capsize": 2})
            ret = np.array([r["retardo_mediano_s"] for r in filas])
            ejes[1, c].plot(x + (j - 1.5) * 0.06, ret, marker="o", color=col, lw=2, ms=6,
                            markeredgecolor="white")
            ok = np.array([r["cierre_correcto_pct"] for r in filas])
            ejes[2, c].bar(pos, ok, ancho * 0.9, color=col)
        ejes[0, c].set_title(titulo, color=INK, fontsize=11, loc="left")
        ejes[1, c].axhline(LIMITE_RETARDO_S, color=INK, ls="--", lw=1.2)
        ejes[1, c].text(len(KS) - 0.55, LIMITE_RETARDO_S + 2, "límite 60 s", ha="right", color=INK, fontsize=9)
    ejes[1, 0].text(0.02, 0.9, "solo cuenta el 1–4 % de sesiones que cierran", transform=ejes[1, 0].transAxes,
                    color=INK, fontsize=9, va="top")
    ejes[0, 0].set_ylabel("Falsas liberaciones\npor 100 sesiones", color=INK)
    ejes[1, 0].set_ylabel("Retardo mediano\nde cierre (s)", color=INK)
    ejes[2, 0].set_ylabel("Sesiones cerradas\ncorrectamente (%)", color=INK)
    for ax in ejes.ravel():
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(colors=MUTED)
    for c in range(2):
        ejes[2, c].set_xticks(x)
        ejes[2, c].set_xticklabels([f"k = {k}" for k in KS], color=INK)
        ejes[1, c].set_ylim(0, 75)
        ejes[2, c].set_ylim(0, 100)
    h, l = ejes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, fontsize=10, labelcolor=INK)
    fig.suptitle("Efecto del suavizado temporal en las falsas liberaciones (σ = 5, 10 y 15 m)",
                 color=INK, fontsize=13, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=RAIZ_IA / "reportes" / "suavizado_k.csv")
    ap.add_argument("--csv-contrato", type=Path, default=None)
    ap.add_argument("--png", type=Path,
                    default=RAIZ_IA.parent.parent / "evidencias" / "s2_suavizado-falsas-liberaciones.png")
    a = ap.parse_args()
    contrato = a.csv_contrato or a.csv.with_name(a.csv.stem + "_contrato.csv")
    graficar(a.csv, contrato, a.png)
    print("PNG ->", a.png)


if __name__ == "__main__":
    main()
