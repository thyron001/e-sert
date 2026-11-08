"""
Genera las evidencias PNG de la sesión 1:
- s1_geolife-horas-por-modo.png: barras de horas por clase con detalle de modo original.
- s1_geolife-trayectorias.png: 30 segmentos al azar coloreados por clase.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DIR_SCRIPT = Path(__file__).resolve().parent
DIR_EVIDENCIAS = DIR_SCRIPT.parent.parent.parent / "evidencias"
ARCHIVO_PARQUET = DIR_SCRIPT / "procesados" / "geolife_etiquetado.parquet"
ARCHIVO_INFO = DIR_SCRIPT / "geolife_info.json"

COLORES_CLASE = {"a_pie": "#2E9E4F", "vehiculo": "#1E63D6", "quieto": "#FF7043"}
COLORES_MODO = {
    "walk": "#2E9E4F",
    "car": "#1E63D6",
    "taxi": "#5B8DEF",
    "bus": "#FF7043",
}


def grafica_horas_por_modo(df: pd.DataFrame, info: dict, salida: Path):
    """Barras de horas por clase del proyecto, con detalle de modo original apilado."""
    horas_orig = info.get("horas_por_modo_original", {})
    clases = {"a_pie": ["walk"], "vehiculo": ["car", "taxi", "bus"]}

    fig, ax = plt.subplots(figsize=(8, 5))
    x_pos = np.arange(len(clases))
    ancho = 0.5

    for i, (clase, modos) in enumerate(clases.items()):
        base = 0.0
        for modo in modos:
            h = horas_orig.get(modo, 0)
            ax.bar(i, h, ancho, bottom=base, label=modo if i == list(clases.keys()).index(clase) else "",
                   color=COLORES_MODO.get(modo, "#999999"))
            if h > 0:
                ax.text(i, base + h / 2, f"{modo}\n{h:.0f}h", ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
            base += h

    ax.set_xticks(x_pos)
    ax.set_xticklabels(list(clases.keys()))
    ax.set_ylabel("Horas")
    ax.set_title("GeoLife: horas por clase del proyecto\n(detalle de modo original)")
    handles, labels_leg = ax.get_legend_handles_labels()
    by_label = dict(zip(labels_leg, handles))
    ax.legend(by_label.values(), by_label.keys(), title="Modo original")
    plt.tight_layout()
    plt.savefig(salida, dpi=150)
    plt.close()
    print(f"Evidencia guardada: {salida}")


def grafica_trayectorias(df: pd.DataFrame, salida: Path, n_segmentos: int = 30):
    """30 segmentos al azar, coloreados por clase, sobre lat/lon."""
    segmentos_unicos = df["segmento_id"].unique()
    rng = np.random.default_rng(42)
    sel = rng.choice(segmentos_unicos, size=min(n_segmentos, len(segmentos_unicos)), replace=False)

    fig, ax = plt.subplots(figsize=(10, 8))
    for seg_id in sel:
        seg = df[df["segmento_id"] == seg_id].sort_values("t")
        modo = seg["modo_real"].iloc[0]
        color = COLORES_CLASE.get(modo, "#999999")
        ax.plot(seg["lon"], seg["lat"], "-", color=color, alpha=0.6, linewidth=0.8)

    for modo, color in COLORES_CLASE.items():
        ax.plot([], [], "-", color=color, label=modo)
    ax.legend(title="Clase")
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.set_title(f"GeoLife: {len(sel)} segmentos al azar por clase")
    plt.tight_layout()
    plt.savefig(salida, dpi=150)
    plt.close()
    print(f"Evidencia guardada: {salida}")


def generar():
    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(ARCHIVO_PARQUET)
    with open(ARCHIVO_INFO, encoding="utf-8") as f:
        info = json.load(f)

    grafica_horas_por_modo(df, info, DIR_EVIDENCIAS / "s1_geolife-horas-por-modo.png")
    grafica_trayectorias(df, DIR_EVIDENCIAS / "s1_geolife-trayectorias.png")


if __name__ == "__main__":
    generar()
