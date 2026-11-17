"""Gráfica de evidencia S1-2: tarjeta SERT frente al cobro real por fracciones.

Compara, para estadías de 1 a 120 minutos, lo que paga un conductor con la tarjeta SERT de
papel (bloques de 30 min pagados por adelantado) y lo que pagaría con el cobro real de e-sert
(fracciones de 5 min, mínimo de 10 min, 0,50 USD/h). El área entre ambas curvas es el
sobrecobro de la tarjeta.

Uso (desde `semanas/S1/Freddy/codigo/`):
    backend/.venv/bin/python backend/graficas/cobro_sert_vs_real.py

Salida: `semanas/S1/Freddy/evidencias/s2_cobro-sert-vs-real.png`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# La carpeta `codigo/` debe estar en sys.path para importar `backend` y `comun`.
CODIGO = Path(__file__).resolve().parents[2]
if str(CODIGO) not in sys.path:
    sys.path.insert(0, str(CODIGO))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from backend.nucleo.tarifa import costo, costo_tarjeta_sert  # noqa: E402

SALIDA = CODIGO.parent / "evidencias" / "s2_cobro-sert-vs-real.png"

# Paleta: azul para el cobro real, color de Freddy para la tarjeta; tinta neutra para textos.
COLOR_REAL = "#2a78d6"
COLOR_TARJETA = "#FF7043"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
REJILLA = "#e4e3df"
FONDO = "#fcfcfb"

EJEMPLOS = (31, 47, 95)
# Desplazamiento (puntos) y alineación de cada etiqueta para que no se solapen.
POSICION_ETIQUETA = {31: ((-14, 18), "right"), 47: ((0, 60), "center"), 95: ((0, 14), "center")}


def calcular(paso: float = 0.5, maximo: float = 120.0):
    """Devuelve las listas de minutos, costo real y costo con tarjeta."""
    n = int(round((maximo - 1) / paso))
    minutos = [1 + i * paso for i in range(n + 1)]
    real = [costo(m) for m in minutos]
    tarjeta = [costo_tarjeta_sert(m) for m in minutos]
    return minutos, real, tarjeta


def sobrecobro_medio(real, tarjeta):
    """Sobrecobro medio en USD y en % respecto al costo real medio."""
    dif = [t - r for r, t in zip(real, tarjeta)]
    media_usd = sum(dif) / len(dif)
    media_real = sum(real) / len(real)
    return media_usd, 100 * media_usd / media_real


def main() -> None:
    minutos, real, tarjeta = calcular()
    assert all(t >= r - 1e-9 for r, t in zip(real, tarjeta)), "la tarjeta debería ser ≥ real"
    media_usd, media_pct = sobrecobro_medio(real, tarjeta)

    print("Sobrecobro medio de la tarjeta SERT (1–120 min, paso 0,5 min):")
    print(f"  {media_usd:.3f} USD por estadía ({media_pct:.1f} % sobre el cobro real)")
    for m in EJEMPLOS:
        print(f"  {m:>3} min: tarjeta {costo_tarjeta_sert(m):.2f} USD | real {costo(m):.2f} USD")

    fig, ax = plt.subplots(figsize=(10, 5.8), facecolor=FONDO)
    ax.set_facecolor(FONDO)

    ax.fill_between(minutos, real, tarjeta, step="post", color=COLOR_TARJETA, alpha=0.15,
                    linewidth=0, label="Sobrecobro")
    ax.plot(minutos, tarjeta, drawstyle="steps-post", color=COLOR_TARJETA, lw=2,
            label="Tarjeta SERT (bloques de 30 min)")
    ax.plot(minutos, real, drawstyle="steps-post", color=COLOR_REAL, lw=2,
            label="Cobro real (fracciones de 5 min, mínimo 10 min)")

    # Puntos de ejemplo con sus dos costos.
    for m in EJEMPLOS:
        t, r = costo_tarjeta_sert(m), costo(m)
        ax.plot([m, m], [r, t], color=TINTA_2, lw=1, ls=":", zorder=3)
        ax.scatter([m], [t], s=45, color=COLOR_TARJETA, edgecolor=FONDO, linewidth=1.5, zorder=4)
        ax.scatter([m], [r], s=45, color=COLOR_REAL, edgecolor=FONDO, linewidth=1.5, zorder=4)
        desplazamiento, alineacion = POSICION_ETIQUETA[m]
        ax.annotate(f"{m} min\ntarjeta {t:.2f} · real {r:.2f}\n(+{t - r:.2f} USD)",
                    xy=(m, t), xytext=desplazamiento, textcoords="offset points",
                    ha=alineacion, multialignment="center", va="bottom", fontsize=8.5, color=TINTA,
                    bbox=dict(boxstyle="round,pad=0.3", fc=FONDO, ec=REJILLA))

    ax.text(0.015, 0.97,
            f"Sobrecobro medio (1–120 min)\n{media_usd:.3f} USD por estadía · "
            f"{media_pct:.1f} % sobre el real",
            transform=ax.transAxes, ha="left", va="top", fontsize=9.5, color=TINTA,
            bbox=dict(boxstyle="round,pad=0.5", fc="white", ec=TINTA_2, lw=0.8))

    ax.set_title("Tarjeta SERT (bloques de 30 min) vs. cobro real por fracciones de 5 min",
                 fontsize=12.5, color=TINTA, loc="left", pad=12)
    ax.set_xlabel("Minutos estacionado", color=TINTA_2)
    ax.set_ylabel("Costo (USD)", color=TINTA_2)
    ax.set_xlim(0, 121)
    ax.set_ylim(0, max(tarjeta) * 1.32)
    ax.set_xticks(range(0, 121, 15))
    ax.grid(axis="y", color=REJILLA, lw=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(TINTA_2)
    ax.tick_params(colors=TINTA_2)
    ax.legend(loc="lower right", frameon=False, fontsize=9, labelcolor=TINTA)

    fig.tight_layout()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(SALIDA, dpi=150, facecolor=FONDO)
    print(f"Gráfica guardada en {SALIDA}")


if __name__ == "__main__":
    main()
