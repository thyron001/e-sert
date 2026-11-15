"""Evidencias gráficas de la sesión 2 (peatones y máquina de estados) a partir de `traci/salidas/`.

Dentro del contenedor van3twin, desde `semanas/S2/Freddy/codigo`:

    python3 -m traci.graficas_sesion --escenario centro_base

Genera en `semanas/S2/Freddy/evidencias/`:
- `s2_linea-tiempo-sesion.png`: estado de una sesión en el tiempo, distancia al puesto y modo
  clasificado frente a `modo_real`;
- `s2_peaton-diligencia.png`: trayectoria de un peatón de diligencia sobre la red.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
SALIDAS = AQUI / "salidas"
EVIDENCIAS = AQUI.parents[1] / "evidencias"

COLORES = {
    "ESTACIONADO": "#9E9E9E",
    "A_PIE": "#FFB74D",
    "REGRESANDO": "#4DB6AC",
    "SALIENDO": "#E57373",
    "CERRADA": "#FFFFFF",
}
MODO_Y = {"quieto": 2, "a_pie": 1, "vehiculo": 0}
COLOR_MODO_REAL = {"quieto": "#455A64", "a_pie": "#2E9E4F", "vehiculo": "#1E63D6"}


def _leer(ruta: Path) -> list:
    with ruta.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def linea_de_tiempo(escenario: str, salida: Path) -> str:
    """Una sesión con ciclo completo: estado, distancia y modo clasificado frente al real."""
    ventanas = _leer(SALIDAS / f"ventanas_{escenario}.csv")
    transiciones = _leer(SALIDAS / f"transiciones_{escenario}.csv")
    cerradas = [t["usuario_id"] for t in transiciones if t["hacia"] == "CERRADA"]
    ventanas_por_usuario = defaultdict(list)
    for v in ventanas:
        ventanas_por_usuario[v["usuario_id"]].append(v)
    # la sesión con más transiciones y con cierre
    usuario = max(set(cerradas), key=lambda u: (sum(t["usuario_id"] == u for t in transiciones),
                                                len(ventanas_por_usuario[u])))
    datos = ventanas_por_usuario[usuario]
    trans = [t for t in transiciones if t["usuario_id"] == usuario]
    t = [float(v["t_sim"]) for v in datos]
    dist = [float(v["distancia_m"]) for v in datos]

    fig, (ax0, ax1, ax2) = plt.subplots(3, 1, figsize=(10, 7), sharex=True,
                                        gridspec_kw={"height_ratios": [1, 2, 2]})
    # franjas de estado: cada transición abre un estado nuevo
    limites = [(0.0, "ESTACIONADO")] + [(float(x["t_sim"]), x["hacia"]) for x in trans]
    fin = t[-1] if t else 0.0
    for (ini, estado), (sig, _) in zip(limites, limites[1:] + [(fin, None)]):
        ax0.axvspan(ini, sig, color=COLORES[estado], edgecolor="none")
        if sig - ini > 20:
            ax0.text((ini + sig) / 2, 0.5, estado, ha="center", va="center", fontsize=8)
    ax0.set_yticks([])
    ax0.set_title(f"Sesión {usuario} · escenario {escenario}", loc="left", fontsize=11)

    ax1.plot(t, dist, color="#333333", lw=1.2, label="distancia al puesto (m)")
    ax1.axhline(15, ls=":", color="#FFB74D", label="15 m (A_PIE)")
    ax1.axhline(30, ls=":", color="#4DB6AC", label="30 m (REGRESANDO)")
    ax1.axhline(20, ls=":", color="#E57373", label="20 m (SALIDA)")
    ax1.set_ylabel("m")
    ax1.legend(fontsize=8, loc="upper right")

    for modo, y in MODO_Y.items():
        xs = [float(v["t_sim"]) for v in datos if v["modo_clasificado"] == modo]
        ax2.scatter(xs, [y] * len(xs), s=14, color="#1E63D6", label="clasificado" if modo == "quieto" else None)
    for modo, y in MODO_Y.items():
        xs = [float(v["t_sim"]) for v in datos if v["modo_real"] == modo]
        ax2.scatter(xs, [y + 0.25] * len(xs), s=10, marker="x", color=COLOR_MODO_REAL[modo],
                    label="modo real" if modo == "quieto" else None)
    ax2.set_yticks(list(MODO_Y.values()))
    ax2.set_yticklabels(list(MODO_Y.keys()))
    ax2.set_xlabel("tiempo de simulación (s)")
    ax2.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    return usuario


def diligencia(escenario: str, salida: Path) -> str:
    """Trayectoria de un peatón de diligencia sobre la red (`sumolib` lee la red de la copia)."""
    from .sumo import cargar_sumolib

    sumolib = cargar_sumolib()
    red = sumolib.net.readNet(str(AQUI / "escenario" / "tyrone" / "sumo" / "red" / "centro.net.xml"))
    filas = _leer(SALIDAS / f"trayectorias_{escenario}.csv")
    por_ped = defaultdict(list)
    for f in filas:
        por_ped[f["ped_id"]].append((float(f["x"]), float(f["y"]), f["etapa"], float(f["t_sim"])))
    # peatón que más se aleja de su auto (la diligencia más visible sobre la red)
    def alejamiento(p):
        x0, y0 = por_ped[p][0][0], por_ped[p][0][1]
        return max(((x - x0) ** 2 + (y - y0) ** 2) ** 0.5 for x, y, _, _ in por_ped[p])
    ped = max(por_ped, key=lambda p: (alejamiento(p), p))
    puntos = por_ped[ped]

    fig, ax = plt.subplots(figsize=(8, 7))
    for arista in red.getEdges():
        if arista.getFunction() == "internal":
            continue
        xs, ys = zip(*arista.getShape())
        ax.plot(xs, ys, color="#CFD8DC", lw=0.8, zorder=1)
    ruta = [(x, y) for x, y, _, _ in puntos]
    xs, ys = zip(*ruta)
    ax.plot(xs, ys, color="#FF7043", lw=2.0, zorder=3, label=f"{ped}")
    ax.scatter([xs[0]], [ys[0]], s=60, color="#1E63D6", zorder=4, label="auto (puesto)")
    espera = [(x, y) for x, y, e, _ in puntos if e.startswith("waiting")]
    if espera:
        ex, ey = zip(*espera)
        ax.scatter(ex, ey, s=12, color="#2E9E4F", zorder=4, label="diligencia (espera)")
    ax.set_aspect("equal")
    ax.set_title(f"Diligencia de {ped} · {escenario}", loc="left", fontsize=11)
    ax.legend(fontsize=8)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    fig.tight_layout()
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    return ped


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Evidencias gráficas de la sesión 2")
    ap.add_argument("--escenario", default="centro_base")
    args = ap.parse_args(argv)
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    usuario = linea_de_tiempo(args.escenario, EVIDENCIAS / "s2_linea-tiempo-sesion.png")
    ped = diligencia(args.escenario, EVIDENCIAS / "s2_peaton-diligencia.png")
    print(f"Sesión: {usuario} · peatón: {ped}")
    print(f"PNG en {EVIDENCIAS}")


if __name__ == "__main__":
    main()
