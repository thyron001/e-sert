"""
Benchmark de latencia de ia.inferencia.

    python -m ia.bench_inferencia [--n 10000] [--png RUTA]

Mide clasificar() ventana a ventana y clasificar_lote() en bloques de 500, con
time.perf_counter_ns y descartando las 100 primeras ventanas (calentamiento).
Usa ventanas de usuarios GeoLife no vistos y de trazas SUMO (semillas reservadas).
"""
import argparse
import gc
import json
import platform
import time
from pathlib import Path

import numpy as np

from ia import inferencia
from ia.datos.ventanas_prueba import a_puntos, cargar, cargar_sumo

RAIZ = Path(__file__).resolve().parent
CALENTAMIENTO = 100
BLOQUE = 500
LIM_IND_MS = 5.0
LIM_LOTE_MS = 0.5


def _pct(x):
    p50, p95, p99 = np.percentile(x, (50, 95, 99))
    return {"p50": float(p50), "p95": float(p95), "p99": float(p99), "media": float(np.mean(x)), "n": int(len(x))}


def reunir(n: int):
    mitad = n // 2
    geo = [a_puntos(v) for v, _ in cargar(mitad)]
    sumo = [a_puntos(v) for v, _ in cargar_sumo(n - len(geo))]
    if len(geo) + len(sumo) < n:  # completa con la otra fuente si una se queda corta
        extra = [a_puntos(v) for v, _ in cargar(n - len(sumo))]
        geo = extra[: n - len(sumo)]
    return geo, sumo


def medir_individual(ventanas):
    for v in ventanas[:CALENTAMIENTO]:
        inferencia.clasificar(v)
    ms = np.empty(len(ventanas) - CALENTAMIENTO)
    for i, v in enumerate(ventanas[CALENTAMIENTO:]):
        t0 = time.perf_counter_ns()
        inferencia.clasificar(v)
        ms[i] = (time.perf_counter_ns() - t0) / 1e6
    return ms


def medir_lote(ventanas, repeticiones=5):
    inferencia.clasificar_lote(ventanas[:CALENTAMIENTO])
    util = ventanas[CALENTAMIENTO:]
    bloques = [util[i:i + BLOQUE] for i in range(0, len(util) - BLOQUE + 1, BLOQUE)]
    ms = []
    for _ in range(repeticiones):
        for b in bloques:
            t0 = time.perf_counter_ns()
            inferencia.clasificar_lote(b)
            ms.append((time.perf_counter_ns() - t0) / 1e6 / len(b))
    return np.array(ms)


def graficar(ind, lote, ruta, dpi=150, pdf=False, figsize=(9, 4.8),
            titulo="Latencia del servicio de inferencia (RF v1, 200 árboles)"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    c_ind, c_lote, ink, muted = "#2A6FB0", "#C8761F", "#222222", "#666666"
    fig, ax = plt.subplots(figsize=figsize)
    lo = min(ind.min(), lote.min()) * 0.8
    hi = max(ind.max(), LIM_IND_MS) * 1.3
    bins = np.logspace(np.log10(lo), np.log10(hi), 70)
    ax.hist(ind, bins=bins, weights=np.full(len(ind), 100 / len(ind)), color=c_ind, alpha=0.85, edgecolor="white", linewidth=0.4, label="Individual: clasificar()")
    ax.hist(lote, bins=bins, weights=np.full(len(lote), 100 / len(lote)), color=c_lote, alpha=0.85, edgecolor="white", linewidth=0.4, label="Lote: clasificar_lote(), por ventana")
    ax.set_xscale("log")
    from matplotlib.ticker import FuncFormatter, NullFormatter
    ax.set_xticks([0.3, 0.5, 1, 2, 5])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
    ax.xaxis.set_minor_formatter(NullFormatter())
    for datos, col, lim, nombre in ((ind, c_ind, LIM_IND_MS, "individual"), (lote, c_lote, LIM_LOTE_MS, "lote")):
        p95 = np.percentile(datos, 95)
        ax.axvline(p95, color=col, lw=2, ls="-")
        ax.text(p95, 0.97, f" p95 {nombre}\n {p95:.2f} ms".replace(".", ","), transform=ax.get_xaxis_transform(),
                color=ink, fontsize=9, ha="left", va="top")
    ax.axvline(LIM_IND_MS, color=ink, lw=1.5, ls="--")
    ax.text(LIM_IND_MS, 0.97, "límite 5 ms ", transform=ax.get_xaxis_transform(),
            color=ink, fontsize=9, ha="right", va="top")
    ax.set_xlabel("Latencia por ventana (ms, escala log)", color=ink)
    ax.set_ylabel("% de las mediciones de cada serie", color=ink)
    ax.set_title(titulo, color=ink, loc="left", fontsize=12 if figsize[0] >= 9 else 9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#DDDDDD", lw=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=muted)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=9, labelcolor=ink)
    fig.tight_layout()
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=dpi)
    if pdf:
        fig.savefig(Path(ruta).with_suffix(".pdf"))
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10_000)
    ap.add_argument("--png", type=str, default=None)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--pdf", action="store_true", help="escribe tambien el PDF junto al PNG")
    ap.add_argument("--figsize", type=float, nargs=2, default=(9, 4.8))
    ap.add_argument("--titulo", type=str, default="Latencia del servicio de inferencia (RF v1, 200 árboles)")
    a = ap.parse_args()

    geo, sumo = reunir(a.n)
    rng = np.random.default_rng(2026)
    ventanas = geo + sumo
    ventanas = [ventanas[i] for i in rng.permutation(len(ventanas))]
    print(f"ventanas: {len(ventanas)} (GeoLife {len(geo)}, SUMO {len(sumo)})")

    gc.collect()
    gc.disable()
    try:
        ind = medir_individual(ventanas)
        lote = medir_lote(ventanas)
    finally:
        gc.enable()
    fuentes = [r["fuente"] for r in inferencia.clasificar_lote(ventanas[:1000])]

    import sklearn
    informe = {
        "n_ventanas": len(ventanas), "n_geolife": len(geo), "n_sumo": len(sumo),
        "calentamiento_descartado": CALENTAMIENTO, "bloque_lote": BLOQUE,
        "individual_ms": _pct(ind), "lote_ms_por_ventana": _pct(lote),
        "fraccion_rf_en_muestra": float(np.mean([f == "rf" for f in fuentes])),
        "cumple": {"individual_p95_lt_5ms": bool(np.percentile(ind, 95) < LIM_IND_MS),
                   "lote_lt_0_5ms": bool(np.percentile(lote, 95) < LIM_LOTE_MS)},
        "entorno": {"python": platform.python_version(), "numpy": np.__version__,
                    "sklearn": sklearn.__version__, "cpu": platform.processor() or platform.machine()},
    }
    (RAIZ / "reportes").mkdir(exist_ok=True)
    (RAIZ / "reportes/bench_inferencia.json").write_text(json.dumps(informe, indent=2))
    print(json.dumps(informe, indent=2))
    if a.png:
        graficar(ind, lote, a.png, a.dpi, a.pdf, tuple(a.figsize), a.titulo)
        print("PNG ->", a.png)


if __name__ == "__main__":
    main()
