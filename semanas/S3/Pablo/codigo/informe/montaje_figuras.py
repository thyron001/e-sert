"""
Montaje de las figuras de la sección de IA -> evidencias/s3_informe-ia-figuras.png

    python3 informe/montaje_figuras.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parents[1] / "evidencias" / "s3_informe-ia-figuras.png"
FIGURAS = [
    ("Figura 1", "Matriz de confusión del RF (GeoLife, usuarios no vistos)", "fig1_matriz-confusion-rf.png"),
    ("Figura 2", "Macro-F1 frente a σ en SUMO", "fig2_curvas-sigma.png"),
    ("Figura 3", "Importancia por permutación", "fig3_importancia.png"),
    ("Figura 4", "Recall por contexto, umbral vs RF", "fig4_recall-contexto.png"),
    ("Figura 5", "Falsas liberaciones y retardo frente a k", "fig5_suavizado-falsas.png"),
    ("Figura 6", "Latencia del servicio de inferencia", "fig6_latencia.png"),
]


def main():
    fig, ejes = plt.subplots(3, 2, figsize=(13, 15))
    for ax, (num, pie, archivo) in zip(ejes.ravel(), FIGURAS):
        ax.imshow(mpimg.imread(AQUI / "figuras/ia" / archivo))
        ax.set_title(f"{num}. {pie}", fontsize=11, color="#222222", loc="left")
        ax.axis("off")
    fig.suptitle("Sección de IA del informe: figuras (borrador S3)", fontsize=14, color="#222222", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(SALIDA, dpi=150)
    print("PNG ->", SALIDA)


if __name__ == "__main__":
    main()
