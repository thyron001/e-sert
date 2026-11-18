"""Figuras del informe IEEE (una columna, PDF vectorial).

Fuentes: `kpis/resultados/final/resumen.csv` (corrida final, 5 semillas) y `datos/rutas.csv`
(`comparar_rutas.py`). Uso, en el contenedor van3twin, desde `proyecto/`:
    python3 informe_ieee/generar_figuras.py
"""
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
RESUMEN = AQUI.parent / "kpis" / "resultados" / "final" / "resumen.csv"
SALIDA = AQUI / "figuras"
GRIS, GRIS_CLARO, AZUL, TOMATE, VERDE = "#4B5A6B", "#B7C3D0", "#1E63D6", "#F4511E", "#2E9E4F"
plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.formatter.use_locale": False, "figure.dpi": 150})


def coma(x, d=0):
    return f"{x:.{d}f}".replace(".", ",")


def filas():
    return {r["escenario"]: r for r in csv.DictReader(open(RESUMEN, encoding="utf-8"))}


def fig_busqueda(R):
    esc = [("ciegas", "A ciegas"), ("p20_rf_final", "App 20 %"), ("p50_rf_final", "App 50 %"),
           ("p80_rf_final", "App 80 %"), ("p50_oraculo", "App 50 %\nocup. real")]
    fig, ax = plt.subplots(figsize=(3.45, 2.3))
    for i, (k, et) in enumerate(esc):
        r = R[k]
        m, lo, hi = float(r["busqueda_media"]), float(r["busqueda_ic_lo"]), float(r["busqueda_ic_hi"])
        color = GRIS if k == "ciegas" else TOMATE if k == "p50_oraculo" else GRIS_CLARO
        ax.bar(i, m, 0.62, color=color, yerr=[[m - lo], [hi - m]], capsize=3, error_kw={"lw": 1})
        txt = coma(m) + ("" if k == "ciegas" else f"\n{float(r['busqueda_cambio_pct']):+.1f} %".replace(".", ","))
        ax.text(i, hi + 6, txt, ha="center", va="bottom", fontsize=7)
    ax.axhline(float(R["ciegas"]["busqueda_media"]), color=GRIS, ls="--", lw=0.8)
    ax.set_xticks(range(len(esc)), [e for _, e in esc], fontsize=7)
    ax.set_ylabel("Búsqueda media (s)")
    ax.set_ylim(0, 540)
    fig.tight_layout()
    fig.savefig(SALIDA / "busqueda.pdf")


def fig_co2(R):
    a, b = R["ciegas"], R["p50_oraculo"]
    metr = [("busqueda_media", "Tiempo (s)"), ("distancia_media", "Distancia (m)"), ("co2_media", "CO$_2$ por auto (g)")]
    fig, ax = plt.subplots(figsize=(3.45, 2.1))
    for i, (k, et) in enumerate(metr):
        va, vb = float(a[k]), float(b[k])
        ax.barh(i + 0.18, 100, 0.34, color=GRIS)
        ax.barh(i - 0.18, vb / va * 100, 0.34, color=TOMATE)
        ax.text(101, i + 0.18, coma(va), va="center", fontsize=7)
        ax.text(vb / va * 100 + 1, i - 0.18, f"{coma(vb)} ({(vb / va - 1) * 100:+.1f} %)".replace(".", ","), va="center", fontsize=7)
    ax.set_yticks(range(len(metr)), [e for _, e in metr])
    ax.set_xlim(0, 135)
    ax.set_xlabel("% de la búsqueda a ciegas")
    ax.invert_yaxis()
    ax.legend(["A ciegas", "App 50 %, ocupación real"], fontsize=6.5, frameon=False, ncol=2,
              loc="upper center", bbox_to_anchor=(0.45, -0.3))
    fig.tight_layout()
    fig.savefig(SALIDA / "co2.pdf")


def fig_falsas(R):
    fig, ax = plt.subplots(figsize=(3.45, 1.9))
    pen = [20, 50, 80]
    for j, (clf, color, et) in enumerate([("umbral", GRIS, "Regla de 8 km/h"), ("rf_final", VERDE, "Random Forest")]):
        v = [float(R[f"p{p}_{clf}"]["falsas_100"]) for p in pen]
        lo = [float(R[f"p{p}_{clf}"]["falsas_100_wilson_lo"]) for p in pen]
        hi = [float(R[f"p{p}_{clf}"]["falsas_100_wilson_hi"]) for p in pen]
        x = [i + (j - 0.5) * 0.36 for i in range(3)]
        ax.bar(x, v, 0.34, color=color, label=et,
               yerr=[[max(a - b, 0) for a, b in zip(v, lo)], [max(c - a, 0) for a, c in zip(v, hi)]], capsize=2, error_kw={"lw": 0.8})
        for xi, vi in zip(x, v):
            ax.text(xi, vi + 3, coma(vi, 1), ha="center", fontsize=6.5)
    ax.set_xticks(range(3), [f"App {p} %" for p in pen])
    ax.set_ylabel("Falsas liberaciones / 100 sesiones")
    ax.set_ylim(0, 105)
    ax.legend(fontsize=6.5, frameon=False, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.12))
    fig.tight_layout()
    fig.savefig(SALIDA / "falsas.pdf")


def fig_rutas():
    datos = list(csv.DictReader(open(AQUI / "datos" / "rutas.csv")))
    a = sorted(float(d["linea_recta_m"]) for d in datos)
    b = sorted(float(d["ruta_m"]) for d in datos)
    n = len(a)
    fig, ax = plt.subplots(figsize=(3.45, 1.9))
    ax.plot(a, [i / n * 100 for i in range(1, n + 1)], color=GRIS, lw=1.4, label="Más cercano en línea recta")
    ax.plot(b, [i / n * 100 for i in range(1, n + 1)], color=AZUL, lw=1.4, label="Ruta de manejo más corta")
    ax.axvline(500, color=GRIS_CLARO, ls=":", lw=1)
    ax.set_xlabel("Distancia de manejo al puesto elegido (m)")
    ax.set_ylabel("% de los casos")
    ax.set_xlim(0, 1500)
    ax.legend(fontsize=6.5, frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(SALIDA / "rutas.pdf")


if __name__ == "__main__":
    SALIDA.mkdir(exist_ok=True)
    R = filas()
    fig_busqueda(R)
    fig_co2(R)
    fig_falsas(R)
    fig_rutas()
    print("Figuras en", SALIDA)
