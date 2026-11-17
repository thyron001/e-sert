"""Evidencia del ensayo (S4-3): línea de tiempo de eventos con los incidentes en rojo y la captura del visor.

    python -m comun.docs.grafica_ensayo [salida.png]      # lee comun/docs/ensayo/eventos.jsonl
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ENSAYO = Path(__file__).resolve().parent / "ensayo"
CARRILES = ["ensayo", "backend", "controlador", "visor", "espejo", "contenedor"]
AZUL, ROJO, TINTA, TINTA_2, REJILLA = "#2a78d6", "#d03b3b", "#0b0b0b", "#5f5e58", "#e1e0d9"


def graficar(salida: Path = None) -> Path:
    eventos = [json.loads(l) for l in (ENSAYO / "eventos.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    corte = None
    if (ENSAYO / "eventos_ctrl_c.jsonl").is_file():
        # Repetición de la prueba 5 tras el arreglo (--vigilar-stdin), a continuación del ensayo.
        corte = max(e["t"] for e in eventos) + 15
        eventos += [{**json.loads(l), "t": json.loads(l)["t"] + corte}
                    for l in (ENSAYO / "eventos_ctrl_c.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # Las líneas de progreso del controlador son muchas: se dibujan como marcas pequeñas sin texto.
    captura = next((ENSAYO / n for n in ("captura_visor.png", "captura_sumo_gui.png") if (ENSAYO / n).is_file()), None)
    fig = plt.figure(figsize=(16, 7.4))
    ax = fig.add_axes([0.07, 0.27, 0.56 if captura else 0.9, 0.65])
    y = {c: i for i, c in enumerate(reversed(CARRILES))}
    t_max = max(e["t"] for e in eventos)
    # Solo se rotulan los incidentes y los hitos, con textos cortos numerados (lista debajo del eje).
    HITOS = (("primer snapshot", "primer snapshot"), ("captura del visor", "captura del visor"),
             ("cortado a propósito", "teléfono pierde el WS"), ("reconectado a", "teléfono reconectado"),
             ("fin seguimiento", "1 recibo, misma sesión"), ("reinicio del backend", "reinicio del backend"),
             ("snapshots de nuevo", "snapshots de nuevo"), ("Ctrl+C (SIGINT) al `docker", "Ctrl+C al lanzador"),
             ("siguen vivos", "quedan controlador y sumo"), ("no quedan procesos", "no quedan procesos"),
             ("OCUPADO", "puerto «ocupado» (falso positivo de la prueba)"), ("puerto", "puerto libre"),
             ("p80 con_gui", "p80 con sumo-gui"), ("p80 sin_gui", "p80 sin GUI"))
    lista = []
    for e in eventos:
        fila = y.get(e["fuente"], 0)
        progreso = e["evento"].startswith("progreso")
        color = ROJO if e["incidente"] else AZUL
        ax.plot(e["t"], fila, marker="|" if progreso else ("X" if e["incidente"] else "o"),
                markersize=7 if progreso else 9, color=color, linestyle="none", zorder=3)
        corto = next((c for clave, c in HITOS if clave in e["evento"]), None)
        if corto:
            n = len(lista) + 1
            lista.append((n, e["t"], corto, e["incidente"]))
            ax.annotate(str(n), (e["t"], fila), xytext=(0, 9 + 9 * (n % 2)), textcoords="offset points",
                        ha="center", fontsize=7.5, color=ROJO if e["incidente"] else TINTA, weight="bold")
    columnas = 4
    for i, (n, t, corto, inc) in enumerate(lista):
        fig.text(0.04 + (i % columnas) * 0.235, 0.13 - (i // columnas) * 0.026, f"{n}. {corto} ({t:.0f} s)",
                 fontsize=7.5, color=ROJO if inc else TINTA_2)
    if corte is not None:
        ax.axvline(corte - 7, color=TINTA_2, linestyle=":", linewidth=1)
        ax.text(corte - 5, len(CARRILES) - 0.45, "repetición de Ctrl+C\ncon --vigilar-stdin", fontsize=7.5,
                color=TINTA_2, va="top")
    ax.set_yticks(list(y.values()))
    ax.set_yticklabels(list(y.keys()), color=TINTA)
    ax.set_ylim(-0.7, len(CARRILES) - 0.3)
    ax.set_xlim(-2, t_max * 1.12)
    ax.set_xlabel("Tiempo del ensayo (s)", color=TINTA_2)
    ax.grid(axis="x", color=REJILLA, linewidth=0.6)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    n_inc = sum(e["incidente"] for e in eventos)
    ax.set_title(f"Ensayo de la demo (backend + controlador): {len(eventos)} eventos, {n_inc} incidentes "
                 "provocados o detectados (rojo)", loc="left", fontsize=11, color=TINTA)
    ax.plot([], [], "o", color=AZUL, label="evento")
    ax.plot([], [], "X", color=ROJO, label="incidente")
    ax.plot([], [], "|", color=AZUL, label="progreso del controlador (300 s simulados)")
    ax.legend(loc="upper left", fontsize=8, frameon=False, bbox_to_anchor=(0, -0.09), ncol=3)
    if captura:
        ax2 = fig.add_axes([0.66, 0.2, 0.33, 0.74])
        ax2.imshow(mpimg.imread(captura))
        ax2.set_axis_off()
        ax2.set_title("Visor durante la demo" if "visor" in captura.name else "sumo-gui durante la demo",
                      fontsize=10, color=TINTA, loc="left")
    salida = Path(salida) if salida else ENSAYO / "linea_tiempo.png"
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    print(f"→ {salida}")
    return salida


if __name__ == "__main__":
    graficar(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
