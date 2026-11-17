"""Mapa del recorrido que reproduce el mock del espejo, para la evidencia junto al teléfono.

Uso:
    python scripts/mapa_espejo.py salida.png [--t-sim 1280] [--puestos ../../../../proyecto/sumo/parqueos/puestos.csv]

Lee `src/espejo/recorrido_mock.json` (los mismos mensajes que envía `mock_espejo/`) y dibuja el
trayecto en auto y a pie, el puesto asignado, el destino y la posición en `--t-sim` (la de la
captura del teléfono). Sustituye a sumo-gui o al visor mientras el espejo no exista en el
backend: el auto del mock no está en SUMO. Necesita matplotlib.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

APP = Path(__file__).resolve().parent.parent
RECORRIDO = APP / "src" / "espejo" / "recorrido_mock.json"
COLOR_MIGUEL = "#C62828"
GRIS = "#757575"
TINTA = "#212121"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("salida", type=Path)
    p.add_argument("--t-sim", type=float, default=1280)
    p.add_argument("--puestos", type=Path, default=None)
    a = p.parse_args()

    mensajes = [m for m in json.loads(RECORRIDO.read_text(encoding="utf-8")) if m["tipo"] == "espejo"]
    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    if a.puestos and a.puestos.exists():
        with a.puestos.open(encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        ax.scatter([float(r["lon"]) for r in filas], [float(r["lat"]) for r in filas], s=6, color="#BDBDBD",
                   label="puestos SERT (puestos.csv)", zorder=1)

    # Tramos consecutivos por modo: en auto (línea llena) y a pie (discontinua).
    for modo, estilo, nombre in (("vehiculo", "-", "en auto"), ("a_pie", "--", "a pie")):
        tramo: list[dict] = []
        etiquetado = False
        for m in mensajes + [{"modo": None}]:
            if m.get("modo") == modo:
                tramo.append(m)
                continue
            if len(tramo) > 1:
                ax.plot([x["lon"] for x in tramo], [x["lat"] for x in tramo], estilo, linewidth=2.5,
                        color=COLOR_MIGUEL if modo == "vehiculo" else TINTA, zorder=3 if modo == "vehiculo" else 4,
                        label=None if etiquetado else f"trayecto {nombre}")
                etiquetado = True
            tramo = []

    con_puesto = next(m for m in mensajes if m.get("puesto"))
    puesto, destino = con_puesto["puesto"], con_puesto["destino"]
    ax.scatter([puesto["lon"]], [puesto["lat"]], s=140, marker="s", color="#2E7D32", edgecolor="white",
               linewidth=2, zorder=5, label=f"puesto asignado ({puesto['puesto_id']})")
    ax.scatter([destino["lon"]], [destino["lat"]], s=220, marker="*", color=TINTA, edgecolor="white",
               linewidth=1.5, zorder=5, label=f"destino: {destino['nombre']}")
    actual = min(mensajes, key=lambda m: abs(m["t_sim"] - a.t_sim))
    ax.scatter([actual["lon"]], [actual["lat"]], s=180, marker="o", color=COLOR_MIGUEL, edgecolor="white",
               linewidth=2.5, zorder=6)
    minutos, segundos = divmod(int(actual["t_sim"]), 60)
    ax.annotate(f"sim_veh42 · {actual['estado']}\nt_sim {minutos:02d}:{segundos:02d}", (actual["lon"], actual["lat"]),
                xytext=(12, 8), textcoords="offset points", fontsize=9, color=TINTA,
                bbox={"facecolor": "white", "edgecolor": GRIS, "boxstyle": "round,pad=0.3"}, zorder=7)

    lons = [m["lon"] for m in mensajes] + [puesto["lon"], destino["lon"]]
    lats = [m["lat"] for m in mensajes] + [puesto["lat"], destino["lat"]]
    margen = 0.0012
    ax.set_xlim(min(lons) - margen, max(lons) + margen)
    ax.set_ylim(min(lats) - margen, max(lats) + margen)
    ax.set_aspect("equal")
    ax.set_title("Recorrido del mock del espejo (los mismos mensajes del WS)", fontsize=10, color=TINTA, loc="left")
    ax.set_xlabel("longitud", fontsize=8, color=GRIS)
    ax.set_ylabel("latitud", fontsize=8, color=GRIS)
    ax.tick_params(labelsize=7, colors=GRIS)
    ax.grid(color="#EEEEEE", linewidth=0.8)
    ax.ticklabel_format(useOffset=False, style="plain")
    # Leyenda debajo del mapa para no tapar el puesto ni el destino.
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, fontsize=8, frameon=False)
    fig.tight_layout()
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.salida, dpi=150)
    print(f"Escrito {a.salida} (posición en t_sim {actual['t_sim']}, {actual['estado']})")


if __name__ == "__main__":
    main()
