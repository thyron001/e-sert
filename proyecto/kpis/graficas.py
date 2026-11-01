"""Figura 2x2 de los KPIs de un escenario (evidencia s1_kpis-base.png).

Uso (desde la carpeta que contiene `kpis/`):
    python -m kpis.graficas --escenario base --salida ../evidencias/s1_kpis-base.png

Lee kpis/salidas/<escenario>_<semilla>_{vehiculos,ocupacion}.csv y kpis_<escenario>.json:
histograma del tiempo y de la distancia de búsqueda, CO2 de búsqueda por vehículo y ocupación
en el tiempo con la banda 85-95 % sombreada.
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from kpis.kpis import SALIDAS  # noqa: E402

COLORES = ["#1E63D6", "#FF9F1C", "#2E9E4F", "#C62828"]


def figura(escenario, salida, carpeta=SALIDAS):
    res = json.loads((carpeta / f"kpis_{escenario}.json").read_text(encoding="utf-8"))
    semillas = res["semillas"]
    fig, ejes = plt.subplots(2, 2, figsize=(13, 9))
    (a_t, a_d), (a_c, a_o) = ejes
    for s, color in zip(semillas, COLORES):
        v = pd.read_csv(carpeta / f"{escenario}_{s}_vehiculos.csv")
        k = res["por_semilla"][s]
        etiqueta = f"semilla {s} (n={k['tiempo_busqueda_s']['n']})"
        a_t.hist(v["tiempo_busqueda_s"], bins=40, alpha=0.55, color=color, label=etiqueta)
        a_d.hist(v["distancia_busqueda_m"], bins=40, alpha=0.55, color=color, label=etiqueta)
        orden = v["co2_busqueda_g"].sort_values(ignore_index=True)
        a_c.plot(orden.index / max(len(orden) - 1, 1) * 100, orden, color=color, label=etiqueta)
        o = pd.read_csv(carpeta / f"{escenario}_{s}_ocupacion.csv")
        a_o.plot(o["t"] / 60, 100 * o["ocupacion"], color=color,
                 label=f"semilla {s} (pico {100 * k['ocupacion_pico']['media']:.1f} %)")
        for eje, clave in ((a_t, "tiempo_busqueda_s"), (a_d, "distancia_busqueda_m")):
            eje.axvline(k[clave]["media"], color=color, ls="--", lw=1.2)
    a_t.set(title="Tiempo de búsqueda (media en línea discontinua)", xlabel="s", ylabel="vehículos")
    a_d.set(title="Distancia de búsqueda", xlabel="m", ylabel="vehículos")
    a_c.set(title="CO$_2$ de búsqueda por vehículo (ordenado)", xlabel="percentil de vehículos (%)",
            ylabel="g de CO$_2$")
    info = json.loads((carpeta / f"{escenario}_{semillas[0]}_info.json").read_text(encoding="utf-8"))
    a_o.axvspan(0, info["warmup_s"] / 60, color="#dddddd", alpha=0.6, label="warm-up")
    a_o.axhspan(85, 95, color="#2E9E4F", alpha=0.12, label="objetivo 85-95 %")
    a_o.set(title="Ocupación de los puestos", xlabel="tiempo de simulación (min)",
            ylabel="ocupación (%)", ylim=(0, 100))
    for eje in (a_t, a_d, a_c):
        eje.legend(fontsize=8)
    a_o.legend(fontsize=8, loc="lower right")
    medias = " · ".join(
        f"s{s}: {res['por_semilla'][s]['tiempo_busqueda_s']['media']:.0f} s, "
        f"{res['por_semilla'][s]['distancia_busqueda_m']['media']:.0f} m, "
        f"{res['por_semilla'][s]['co2_busqueda_g']['media']:.1f} g CO$_2$, "
        f"{100 * res['por_semilla'][s]['ocupacion_pico']['media']:.1f} %"
        for s in semillas)
    fig.suptitle(f"KPIs del escenario '{escenario}' (medias) · {medias}", fontsize=11)
    fig.tight_layout()
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    print(f"Figura -> {salida}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--escenario", default="base")
    ap.add_argument("--salida", required=True)
    args = ap.parse_args()
    figura(args.escenario, Path(args.salida))


if __name__ == "__main__":
    main()
