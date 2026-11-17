"""Histograma de la latencia evento → pantalla del modo espejo (p50 y p95 por modo).

Uso:
    python scripts/latencia_espejo.py latencias.csv salida.png

Entrada: el CSV que exporta la app (`modo,t_sim,lat_total_ms,lat_cliente_ms`), el mismo que el
mock (`mock_espejo/`) junta con POST /api/v1/espejo/latencias. Salida: PNG a 150 dpi con dos
paneles: latencia total (ts del servidor → pintado, corregida por el desfase de reloj) y la
parte del teléfono (recepción → pintado). Necesita matplotlib.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLOR_MIGUEL = "#C62828"  # docs/EQUIPO.md
TINTA = "#212121"
TINTA_SECUNDARIA = "#616161"
REJILLA = "#E0E0E0"
PANELES = (("lat_total_ms", "Total: evento en el servidor → pantalla"),
           ("lat_cliente_ms", "Solo el teléfono: recepción → pantalla"))


def percentil(valores: list[float], p: float) -> float:
    """Rango más cercano, igual que src/espejo/latencia.ts."""
    orden = sorted(valores)
    return orden[max(1, math.ceil(p / 100 * len(orden))) - 1]


def leer(ruta: Path) -> dict[str, dict[str, list[float]]]:
    datos: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    with ruta.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            for col, _ in PANELES:
                datos[fila["modo"]][col].append(float(fila[col]))
    return datos


def graficar(datos: dict[str, dict[str, list[float]]], salida: Path) -> list[str]:
    modos = sorted(datos)
    fig, ejes = plt.subplots(len(PANELES), len(modos), figsize=(8, 6.4), sharex=True, squeeze=False)
    resumen = []
    maximo = max(max(v) for m in modos for v in datos[m].values())
    cajas = list(range(0, int(maximo) + 25, 25))
    for j, modo in enumerate(modos):
        for i, (col, titulo) in enumerate(PANELES):
            ax = ejes[i][j]
            v = datos[modo][col]
            p50, p95 = percentil(v, 50), percentil(v, 95)
            resumen.append(f"{modo} {col}: n={len(v)} p50={p50:.0f} ms p95={p95:.0f} ms")
            ax.hist(v, bins=cajas, color=COLOR_MIGUEL, edgecolor="white", linewidth=1.5)
            alto = ax.get_ylim()[1]
            for valor, nombre in ((p50, "p50"), (p95, "p95")):
                ax.axvline(valor, color=TINTA, linewidth=1.2, linestyle="--" if nombre == "p95" else "-")
                altura = 0.92 if nombre == "p50" else 0.76  # escalonadas: p50 y p95 pueden estar cerca
                ax.text(valor + 6, alto * altura, f"{nombre} {valor:.0f} ms", color=TINTA, fontsize=9, va="top",
                        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1})
            ax.set_title(f"{titulo} (modo {modo}, n={len(v)})", fontsize=10, color=TINTA, loc="left")
            ax.set_ylabel("mensajes", color=TINTA_SECUNDARIA, fontsize=9)
            ax.grid(axis="y", color=REJILLA, linewidth=0.8)
            ax.set_axisbelow(True)
            for lado in ("top", "right"):
                ax.spines[lado].set_visible(False)
            ax.tick_params(colors=TINTA_SECUNDARIA, labelsize=8)
        ejes[-1][j].set_xlabel("latencia (ms)", color=TINTA_SECUNDARIA, fontsize=9)
    fig.suptitle("S2-3 · Latencia del modo espejo (mock local por Tailscale, Android)", fontsize=12,
                 color=COLOR_MIGUEL, x=0.02, ha="left")
    fig.tight_layout()
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=150)
    return resumen


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", type=Path)
    p.add_argument("salida", type=Path)
    a = p.parse_args()
    for linea in graficar(leer(a.csv), a.salida):
        print(linea)
    print(f"Escrito {a.salida}")


if __name__ == "__main__":
    main()
