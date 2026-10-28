"""
Genera las evidencias PNG de la sesión 3: evaluación de generalización.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
DIR_EVIDENCIAS = AQUI.parent.parent / "evidencias"
DIR_REPORTES = AQUI / "reportes"
CLASES = ["a_pie", "quieto", "vehiculo"]


def generar_umbral_vs_rf_por_fuente():
    """PNG 1: macro-F1 por fuente de los 3 sistemas con IC 95%."""
    ruta = DIR_REPORTES / "metricas_generalizacion.json"
    with ruta.open() as f:
        datos = json.load(f)

    fuentes_dict = datos["fuentes"]
    fuentes = [f for f in fuentes_dict if not isinstance(fuentes_dict[f], str)]
    if not fuentes:
        print("Sin fuentes para graficar")
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(fuentes))
    ancho = 0.25
    colores = {"umbral": "#FF7043", "rf": "#2E9E4F", "rf_suavizado": "#1565C0"}
    labels = {"umbral": "Umbral", "rf": "RF v1", "rf_suavizado": "RF v1 + suavizado"}

    for i, sistema in enumerate(["umbral", "rf", "rf_suavizado"]):
        f1s = []
        errs_lo = []
        errs_hi = []
        for fuente in fuentes:
            res = fuentes_dict[fuente]
            f1 = res[sistema]["macro_f1"]
            boot = res[sistema]["bootstrap"]
            lo, hi = boot["macro_f1_ic95"]
            f1s.append(f1)
            errs_lo.append(f1 - lo)
            errs_hi.append(hi - f1)

        ax.bar(x + i * ancho, f1s, ancho,
               yerr=[errs_lo, errs_hi],
               label=labels[sistema], color=colores[sistema],
               alpha=0.85, capsize=4, edgecolor="white", linewidth=0.5)

    ax.set_xticks(x + ancho)
    fuentes_label = [f.replace("sumo_", "SUMO\n").replace("geolife_prueba", "GeoLife\nprueba")
                     for f in fuentes]
    ax.set_xticklabels(fuentes_label, fontsize=9)
    ax.set_ylabel("macro-F1", fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=10, loc="lower right")
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("Evaluación de generalización: macro-F1 por fuente (IC 95% bootstrap agrupado)",
                 fontsize=12)

    plt.tight_layout()
    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    ruta_png = DIR_EVIDENCIAS / "s3_umbral-vs-rf-por-fuente.png"
    plt.savefig(ruta_png, dpi=150)
    plt.close()
    print(f"Evidencia: {ruta_png}")
    return ruta_png


def generar_curvas_sigma():
    """PNG 2: F1 y tasa vehiculo→a_pie vs σ."""
    ruta_csv = DIR_REPORTES / "curvas_sigma.csv"
    if not ruta_csv.exists():
        print("Sin curvas_sigma.csv (escenarios SUMO no generados)")
        # Generar un placeholder con datos de GeoLife
        ruta_json = DIR_REPORTES / "metricas_generalizacion.json"
        with ruta_json.open() as f:
            datos = json.load(f)
        if "geolife_prueba" in datos.get("fuentes", {}):
            geo = datos["fuentes"]["geolife_prueba"]
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
            ax1.text(0.5, 0.5, "Curvas σ no disponibles\n(contenedor van3twin apagado)\n\n"
                     f"GeoLife prueba (σ=mezcla):\n"
                     f"RF macro-F1 = {geo['rf']['macro_f1']:.4f}\n"
                     f"Umbral macro-F1 = {geo['umbral']['macro_f1']:.4f}",
                     ha="center", va="center", transform=ax1.transAxes, fontsize=11)
            ax1.set_title("macro-F1 vs σ")
            ax2.text(0.5, 0.5, "Tasa vehiculo→a_pie vs σ\nno disponible sin SUMO",
                     ha="center", va="center", transform=ax2.transAxes, fontsize=11)
            ax2.set_title("Tasa vehiculo→a_pie vs σ")
            plt.tight_layout()
            DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
            ruta_png = DIR_EVIDENCIAS / "s3_curvas-sigma.png"
            plt.savefig(ruta_png, dpi=150)
            plt.close()
            print(f"Evidencia (placeholder): {ruta_png}")
            return ruta_png
        return None

    df = pd.read_csv(ruta_csv)
    colores = {"umbral": "#FF7043", "rf": "#2E9E4F", "rf_suavizado": "#1565C0"}
    labels = {"umbral": "Umbral", "rf": "RF v1", "rf_suavizado": "RF v1 + suavizado"}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    for sistema in ["umbral", "rf", "rf_suavizado"]:
        sub = df[df["sistema"] == sistema].sort_values("sigma")
        ax1.plot(sub["sigma"], sub["macro_f1"], "o-", color=colores[sistema],
                 label=labels[sistema], linewidth=2, markersize=6)
        ax1.fill_between(sub["sigma"], sub["macro_f1_ic_lo"], sub["macro_f1_ic_hi"],
                         color=colores[sistema], alpha=0.15)

        ax2.plot(sub["sigma"], sub["tasa_veh_apie"], "o-", color=colores[sistema],
                 label=labels[sistema], linewidth=2, markersize=6)
        ax2.fill_between(sub["sigma"], sub["tasa_veh_apie_ic_lo"], sub["tasa_veh_apie_ic_hi"],
                         color=colores[sistema], alpha=0.15)

    ax1.axhline(0.7, ls="--", color="gray", alpha=0.5, label="F1=0.7")
    ax1.set_xlabel("σ (metros)")
    ax1.set_ylabel("macro-F1")
    ax1.set_title("macro-F1 vs ruido GPS (σ)")
    ax1.legend(fontsize=9)
    ax1.grid(alpha=0.3)

    ax2.set_xlabel("σ (metros)")
    ax2.set_ylabel("Tasa vehiculo→a_pie")
    ax2.set_title("Falsas liberaciones vs ruido GPS")
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    ruta_png = DIR_EVIDENCIAS / "s3_curvas-sigma.png"
    plt.savefig(ruta_png, dpi=150)
    plt.close()
    print(f"Evidencia: {ruta_png}")
    return ruta_png


def generar_trafico_lento():
    """PNG 3: traza de tráfico lento con franjas de modo real y predicciones."""
    ruta_json = DIR_REPORTES / "metricas_generalizacion.json"
    with ruta_json.open() as f:
        datos = json.load(f)

    tl = datos.get("trafico_lento")
    geo = datos.get("fuentes", {}).get("geolife_prueba", {})

    fig, ax = plt.subplots(figsize=(10, 5))

    if tl and tl.get("n_ventanas", 0) > 0:
        sistemas = ["umbral", "rf", "rf_suavizado"]
        labels_s = ["Umbral", "RF v1", "RF+suavizado"]
        colores = ["#FF7043", "#2E9E4F", "#1565C0"]
        recalls = [tl[s]["recall_vehiculo"] for s in sistemas]

        bars = ax.barh(labels_s, recalls, color=colores, alpha=0.85, edgecolor="white")
        for bar, val in zip(bars, recalls):
            ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height() / 2,
                    f"{val:.1%}", va="center", fontsize=11)

        ax.set_xlabel("Recall de vehículo (ventanas con vel < 8 km/h)")
        ax.set_title(f"Tráfico lento: {tl['n_ventanas']} ventanas, {tl['minutos']} min\n"
                     f"vel media: {tl['vel_media_kmh']} km/h")
        ax.set_xlim(0, 1.15)
        ax.grid(axis="x", alpha=0.3)
    else:
        ax.text(0.5, 0.6, "Tráfico lento: sin datos SUMO\n(contenedor van3twin apagado)",
                ha="center", va="center", transform=ax.transAxes, fontsize=12)
        if geo:
            ax.text(0.5, 0.35,
                    f"GeoLife prueba — tasa vehiculo→a_pie:\n"
                    f"RF: {geo['rf']['tasa_veh_como_apie']:.1%}  |  "
                    f"Umbral: {geo['umbral']['tasa_veh_como_apie']:.1%}",
                    ha="center", va="center", transform=ax.transAxes, fontsize=10)
        ax.set_title("Análisis de tráfico lento (parcial)")

    plt.tight_layout()
    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    ruta_png = DIR_EVIDENCIAS / "s3_trafico-lento.png"
    plt.savefig(ruta_png, dpi=150)
    plt.close()
    print(f"Evidencia: {ruta_png}")
    return ruta_png


def main():
    print("Generando evidencias S2-3...")
    generar_umbral_vs_rf_por_fuente()
    generar_curvas_sigma()
    generar_trafico_lento()
    print("Listo.")


if __name__ == "__main__":
    main()
