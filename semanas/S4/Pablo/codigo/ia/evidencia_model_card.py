"""
Evidencia de S4-1: matriz de confusión normalizada de `rf_final` en usuarios no vistos, F1 por clase RF frente a
umbral con IC 95 % y recuadro con la latencia p50/p99.

    python3 -m ia.evidencia_model_card
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parent.parent / "evidencias" / "s1_model-card-metricas.png"
VERDE, GRIS, INK = "#2E9E4F", "#6B6F78", "#222222"
CLASES = ["a_pie", "quieto", "vehiculo"]
ETQ = ["a pie", "quieto", "vehículo"]


def main():
    m = json.loads((AQUI / "reportes/metricas_rf_final.json").read_text())
    g = m["fuentes"]["geolife_prueba"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1, 1.25]})
    cm = np.array(g["rf_final"]["confusion_normalizada"])
    n = np.array(g["rf_final"]["confusion_conteos"])
    a1.imshow(cm, cmap="Greens", vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            a1.text(j, i, f"{cm[i, j]:.2f}\n({n[i, j]:,})".replace(",", " "), ha="center", va="center",
                    color="white" if cm[i, j] > 0.55 else INK)
    a1.set_xticks(range(3), ETQ)
    a1.set_yticks(range(3), ETQ)
    a1.set_xlabel("Clase predicha")
    a1.set_ylabel("Clase real")
    a1.set_title("rf_final en usuarios no vistos (GeoLife)", loc="left", fontsize=11)

    x = np.arange(3)
    for j, (clave, color, etq) in enumerate((("umbral", GRIS, "Umbral"), ("rf_final", VERDE, "Random Forest"))):
        f1 = np.array([g[clave]["por_clase"][c]["f1"] for c in CLASES])
        ic = g[clave]["bootstrap"]["f1_por_clase_ic95"]
        err = np.array([[f1[i] - ic[c][0], ic[c][1] - f1[i]] for i, c in enumerate(CLASES)]).T
        a2.bar(x + (j - 0.5) * 0.36, f1, 0.34, yerr=err, color=color, label=etq,
               error_kw={"ecolor": INK, "elinewidth": 1, "capsize": 3})
        for xi, v in zip(x + (j - 0.5) * 0.36, f1):
            a2.text(xi, 0.03, f"{v:.2f}".replace(".", ","), ha="center", color="white", fontsize=9)
    a2.set_xticks(x, ETQ)
    a2.set_ylim(0, 1.25)
    a2.set_ylabel("F1 por clase (IC 95 %)")
    a2.set_title("F1 por clase: RF frente a umbral", loc="left", fontsize=11)
    a2.legend(frameon=False, loc="upper left", ncol=2)
    for s in ("top", "right"):
        a2.spines[s].set_visible(False)
    lat = m.get("latencia", {})
    fig.text(0.5, 0.02, f"F1 macro: RF {g['rf_final']['macro_f1']:.3f} · umbral {g['umbral']['macro_f1']:.3f}   |   "
             f"Latencia de clasificar: p50 {lat.get('p50_ms', 0):.2f} ms · p99 {lat.get('p99_ms', 0):.2f} ms".replace(".", ","),
             ha="center", fontsize=10, bbox={"boxstyle": "round,pad=0.4", "fc": "white", "ec": "#999999"})
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(SALIDA, dpi=150)
    print("->", SALIDA)


if __name__ == "__main__":
    main()
