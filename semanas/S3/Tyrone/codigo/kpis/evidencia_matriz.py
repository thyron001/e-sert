"""Evidencia S3-1: mapa de calor 4 × 2 (penetración × clasificador) del tiempo de búsqueda medio.

    kpis/.venv/bin/python -m kpis.evidencia_matriz

Cada celda: media entre semillas y `n/3` corridas terminadas. Título: duración total y procesos
(de `resultados/metadatos.json`).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

AQUI = Path(__file__).resolve().parent
RES = AQUI / "resultados"
DESTINO = AQUI.parent.parent / "evidencias" / "s1_matriz-progreso.png"


def main(csv: Path = RES / "experimentos.csv", meta: Path = RES / "metadatos.json", destino: Path = DESTINO) -> Path:
    df = pd.read_csv(csv)
    m = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
    n_sem = len(m.get("matriz", {}).get("semillas", [1, 2, 3]))
    pens, clfs = [0, 20, 50, 80], ["umbral", "rf"]
    medias = np.full((4, 2), np.nan)
    ns = np.zeros((4, 2), dtype=int)
    for i, p in enumerate(pens):
        for j, c in enumerate(clfs):
            g = df[(df.penetracion == p) & (df.clasificador == c)]["busqueda_media_s"].dropna()
            ns[i, j] = len(g)
            if len(g):
                medias[i, j] = g.mean()
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    im = ax.imshow(medias, cmap="Blues", aspect="auto")
    for i in range(4):
        for j in range(2):
            v = medias[i, j]
            oscuro = not np.isnan(v) and v > np.nanmean(medias)
            texto = "—" if np.isnan(v) else f"{v:.0f} s"
            ax.text(j, i, f"{texto}\n{ns[i, j]}/{n_sem}", ha="center", va="center", fontsize=11,
                    color="white" if oscuro else "#0b2540", fontweight="bold")
    ax.set_xticks([0, 1], ["umbral", "rf (rf_final)"])
    ax.set_yticks(range(4), [f"{p} %" for p in pens])
    ax.set_xlabel("Clasificador")
    ax.set_ylabel("Penetración de la app")
    dur = m.get("duracion_matriz_s") or m.get("duracion_total_s")
    proc = m.get("procesos", "?")
    tit = f"Matriz S3-1: búsqueda media por celda ({len(df)}/{4 * 2 * n_sem} corridas)"
    sub = (f"duración total {dur / 3600:.1f} h con {proc} procesos" if dur else "en curso").replace(".", ",")
    ax.set_title(f"{tit}\n{sub}; fallidas: {len(m.get('corridas_fallidas', []))}", fontsize=10.5, loc="left")
    cb = fig.colorbar(im, ax=ax, fraction=0.05)
    cb.set_label("Tiempo de búsqueda medio (s)")
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    return destino


if __name__ == "__main__":
    print(main())
