"""Evidencias del emulador de GPS (S1-3).

- `s3_trazas-gps.png`: ruta verdadera frente a la ruidosa de un auto y de un peatón, sobre la red.
- `s3_ruido-gps.png`: histograma del error en metros y autocorrelación del error.

Dentro del contenedor, desde `semanas/S1/Freddy/codigo`:

    python3 -m traci.graficas_gps --semilla 1
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

from .generar_trazas import CARPETA_TRAZAS, CFG_TYRONE  # noqa: E402
from .sumo import cargar_sumolib  # noqa: E402

EVIDENCIAS = Path(__file__).resolve().parents[2] / "evidencias"
TOMATE, AZUL, GRIS = "#FF7043", "#2A78D6", "#C9CED6"
M_POR_GRADO = 111_320.0


def leer(ruta: Path):
    por_agente = defaultdict(list)
    with ruta.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            por_agente[fila["usuario_id"]].append(fila)
    return por_agente


def error_m(fila):
    """Error (este, norte) en metros entre la posición publicada y la verdadera."""
    lat, lon = float(fila["lat"]), float(fila["lon"])
    lat_r, lon_r = float(fila["lat_real"]), float(fila["lon_real"])
    return ((lon - lon_r) * M_POR_GRADO * math.cos(math.radians(lat_r)), (lat - lat_r) * M_POR_GRADO)


def elegir_agentes(por_agente):
    """Un auto que circule y pase por congestión, y un peatón que camine y se detenga."""
    def puntaje_auto(filas):
        modos = [f["modo_real"] for f in filas]
        return (sum(f["caso"] == "congestion" for f in filas) > 5, modos.count("vehiculo"))

    def puntaje_peaton(filas):
        modos = [f["modo_real"] for f in filas]
        return ("quieto" in modos, modos.count("a_pie") if len(filas) < 1500 else 0)

    autos = {a: f for a, f in por_agente.items() if a.startswith("sim_") and not a.startswith("sim_fondo")}
    peatones = {a: f for a, f in por_agente.items() if a.startswith("ped_")}
    return max(autos, key=lambda a: puntaje_auto(autos[a])), max(peatones, key=lambda a: puntaje_peaton(peatones[a]))


def dibujar_red(ax, red, caja):
    lat0, lat1, lon0, lon1 = caja
    for borde in red.getEdges(withInternal=False):
        puntos = [red.convertXY2LonLat(x, y) for x, y in borde.getShape()]
        if not any(lat0 <= la <= lat1 and lon0 <= lo <= lon1 for lo, la in puntos):
            continue
        ax.plot([p[0] for p in puntos], [p[1] for p in puntos], color=GRIS, lw=2.2, zorder=1,
                solid_capstyle="round")


def grafica_trazas(por_agente, red, salida: Path):
    auto, peaton = elegir_agentes(por_agente)
    fig, ejes = plt.subplots(1, 2, figsize=(14, 7))
    for ax, agente, titulo in ((ejes[0], auto, "Auto"), (ejes[1], peaton, "Peatón")):
        filas = por_agente[agente]
        lat_r = [float(f["lat_real"]) for f in filas]
        lon_r = [float(f["lon_real"]) for f in filas]
        lat = [float(f["lat"]) for f in filas]
        lon = [float(f["lon"]) for f in filas]
        margen = 0.0004
        caja = (min(lat_r + lat) - margen, max(lat_r + lat) + margen, min(lon_r + lon) - margen, max(lon_r + lon) + margen)
        dibujar_red(ax, red, caja)
        ax.plot(lon_r, lat_r, color=AZUL, lw=2.4, zorder=3, label="Ruta verdadera (SUMO)")
        ax.plot(lon, lat, color=TOMATE, lw=0.8, alpha=0.6, zorder=4)
        ax.scatter(lon, lat, s=9, color=TOMATE, zorder=5, label="GPS emulado (σ = 5 m, AR(1) ρ = 0,8)")
        quietos = [i for i, f in enumerate(filas) if f["modo_real"] == "quieto"]
        lentos = [i for i, f in enumerate(filas) if f["caso"] == "congestion"]
        if quietos:
            ax.scatter([lon[i] for i in quietos], [lat[i] for i in quietos], s=26, facecolor="none",
                       edgecolor="#333333", lw=0.9, zorder=6, label="modo_real = quieto")
        if lentos:
            ax.scatter([lon[i] for i in lentos], [lat[i] for i in lentos], s=26, marker="s", facecolor="none",
                       edgecolor="#7A3EB1", lw=0.9, zorder=6, label="vehículo en congestión (< 7 km/h)")
        ax.set_xlim(caja[2], caja[3])
        ax.set_ylim(caja[0], caja[1])
        ax.set_aspect(1 / math.cos(math.radians(sum(caja[:2]) / 2)))
        dur = float(filas[-1]["t"]) - float(filas[0]["t"])
        ax.set_title(f"{titulo}: {agente} · {len(filas)} muestras en {dur / 60:.0f} min", fontsize=11)
        ax.set_xlabel("Longitud")
        ax.set_ylabel("Latitud")
        ax.ticklabel_format(useOffset=False)
        ax.xaxis.set_major_locator(plt.MaxNLocator(4))
        ax.tick_params(labelsize=8)
        ax.legend(loc="best", fontsize=8, framealpha=0.9)
    fig.suptitle("Trazas GPS emuladas sobre la red del Centro Histórico (semilla 1)", fontsize=13)
    fig.tight_layout()
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    return auto, peaton


def autocorrelacion(series, max_lag=20):
    """Autocorrelación media de varias series (una por agente, muestras consecutivas de 1 s).

    El error del GPS tiene media cero por construcción, así que no se resta la media de cada
    tramo: con tramos cortos (cortados por las pérdidas) eso sesgaría la estimación hacia abajo.
    """
    acf = []
    for lag in range(max_lag + 1):
        num = den = 0.0
        for s in series:
            if len(s) <= lag + 1:
                continue
            num += sum(s[i] * s[i + lag] for i in range(len(s) - lag))
            den += sum(v * v for v in s)
        acf.append(num / den)
    return acf


def grafica_ruido(por_agente, salida: Path, sigma=5.0, rho=0.8):
    errores, series_este = [], []
    for filas in por_agente.values():
        serie, t_prev = [], None
        for f in filas:
            ee, en = error_m(f)
            errores.append(math.hypot(ee, en))
            t = float(f["t"])
            if t_prev is not None and t - t_prev > 1.01:  # una pérdida corta la serie
                if len(serie) > 30:
                    series_este.append(serie)
                serie = []
            serie.append(ee)
            t_prev = t
        if len(serie) > 30:
            series_este.append(serie)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    a1.hist(errores, bins=80, range=(0, 25), density=True, color=TOMATE, alpha=0.75, label="Error emulado")
    xs = [i * 25 / 200 for i in range(201)]
    a1.plot(xs, [x / sigma ** 2 * math.exp(-x * x / (2 * sigma ** 2)) for x in xs], color="#333333", lw=1.6,
            label="Rayleigh teórica (σ = 5 m)")
    media = sum(errores) / len(errores)
    p95 = sorted(errores)[int(0.95 * len(errores))]
    a1.axvline(media, color=AZUL, lw=1.4, ls="--", label=f"Media {media:.2f} m")
    a1.set_title(f"Error horizontal ({len(errores):,} muestras) · p95 = {p95:.1f} m".replace(",", " "))
    a1.set_xlabel("Error (m)")
    a1.set_ylabel("Densidad")
    a1.legend(fontsize=9)
    acf = autocorrelacion(series_este[:400])
    lags = list(range(len(acf)))
    a2.bar(lags, acf, color=TOMATE, alpha=0.75, label="Medida (eje este)")
    a2.plot(lags, [rho ** k for k in lags], color="#333333", marker="o", ms=3, lw=1.4, label="Teórica ρ^k, ρ = 0,8")
    a2.plot(lags, [1 if k == 0 else 0 for k in lags], color=GRIS, lw=1.2, ls=":", label="Ruido blanco")
    a2.set_title(f"Autocorrelación del error · lag 1 = {acf[1]:.3f}")
    a2.set_xlabel("Retardo (s)")
    a2.set_ylabel("Autocorrelación")
    a2.legend(fontsize=9)
    for a in (a1, a2):
        a.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Ruido del GPS emulado: AR(1) correlacionado en el tiempo (semilla 1)", fontsize=13)
    fig.tight_layout()
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    return media, p95, acf[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--semilla", type=int, default=1)
    args = ap.parse_args()
    por_agente = leer(CARPETA_TRAZAS / f"sumo_semilla{args.semilla}.csv")
    sumolib = cargar_sumolib()
    red = sumolib.net.readNet(str(CFG_TYRONE.parent / "red" / "centro.net.xml"))
    EVIDENCIAS.mkdir(exist_ok=True)
    auto, peaton = grafica_trazas(por_agente, red, EVIDENCIAS / "s3_trazas-gps.png")
    media, p95, lag1 = grafica_ruido(por_agente, EVIDENCIAS / "s3_ruido-gps.png")
    print(f"auto={auto} peaton={peaton} error_medio={media:.2f} m p95={p95:.2f} m lag1={lag1:.3f}")


if __name__ == "__main__":
    main()
