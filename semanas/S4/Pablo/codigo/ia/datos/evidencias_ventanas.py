"""
Genera la evidencia PNG de la sesión 2:
s2_caracteristicas-por-clase.png: cuadrícula de boxplots (6 features × 3 clases).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

DIR_SCRIPT = Path(__file__).resolve().parent
DIR_EVIDENCIAS = DIR_SCRIPT.parent.parent.parent / "evidencias"
ARCHIVO_PARQUET = DIR_SCRIPT / "procesados" / "ventanas_geolife.parquet"

COLORES = {"a_pie": "#2E9E4F", "quieto": "#FF7043", "vehiculo": "#1E63D6"}
FEATURES_CLAVE = [
    "vel_media", "vel_std", "acc_media_abs",
    "prop_detenido", "rectitud", "distancia_total",
]
TITULOS = [
    "Velocidad media (m/s)", "Velocidad σ (m/s)", "|Aceleración| media (m/s²)",
    "Prop. detenido", "Rectitud", "Distancia total (m)",
]


def generar():
    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(ARCHIVO_PARQUET)

    conteo = df["modo_real"].value_counts()
    titulo_sup = "  |  ".join(f"{m}: {conteo.get(m, 0)}" for m in ["a_pie", "quieto", "vehiculo"])

    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes = axes.flatten()

    clases = ["a_pie", "quieto", "vehiculo"]
    for i, (feat, titulo) in enumerate(zip(FEATURES_CLAVE, TITULOS)):
        ax = axes[i]
        datos = [df[df["modo_real"] == c][feat].dropna().values for c in clases]
        bp = ax.boxplot(datos, patch_artist=True, showfliers=False)
        ax.set_xticklabels(clases)
        for patch, c in zip(bp["boxes"], clases):
            patch.set_facecolor(COLORES[c])
            patch.set_alpha(0.7)
        ax.set_title(titulo, fontsize=10)
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle(f"Características por clase — ventanas GeoLife\n{titulo_sup}", fontsize=12)
    plt.tight_layout()
    salida = DIR_EVIDENCIAS / "s2_caracteristicas-por-clase.png"
    plt.savefig(salida, dpi=150)
    plt.close()
    print(f"Evidencia guardada: {salida}")


if __name__ == "__main__":
    generar()
