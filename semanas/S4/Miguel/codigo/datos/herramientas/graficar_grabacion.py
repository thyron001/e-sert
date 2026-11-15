"""
Valida y grafica una grabación casera exportada por el grabador de la app.

    python graficar_grabacion.py <grabacion.csv> [--salida figura.png]

1. Valida el CSV contra el contrato (§7 v0 / §8 v1): las 7 columnas
   usuario_id,t,lat,lon,precision_m,velocidad_mps,modo_real primero y en ese orden, valores
   válidos, `t` creciente por usuario y frecuencia cercana a 1 Hz.
2. Dibuja la traza coloreada por etiqueta y la velocidad en el tiempo con franjas por etiqueta.
3. Reporta la duración por etiqueta, la precisión media y los cambios de etiqueta.

Sale con código 1 si la validación encuentra errores. Requiere numpy y matplotlib.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

# SINCRONIZAR con COLUMNAS_TRAZA de comun/esquemas.py
COLUMNAS_CONTRATO = ["usuario_id", "t", "lat", "lon", "precision_m", "velocidad_mps", "modo_real"]
MODOS = {"a_pie", "quieto", "vehiculo"}
COLORES = {
    "a_pie": "#2E7D32",
    "quieto": "#757575",
    "vehiculo": "#1565C0",
    "vehiculo/trafico_lento": "#EF6C00",
    "sin etiqueta": "#BDBDBD",
}
COLOR_MIGUEL = "#C62828"
RADIO_TIERRA_M = 6_371_000


@dataclass
class Grabacion:
    usuario_id: list[str]
    t: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    precision: np.ndarray  # NaN si vacía
    velocidad: np.ndarray  # NaN si vacía
    etiqueta: list[str]  # modo_real, o "vehiculo/trafico_lento"
    extras: list[str]
    telefono: str
    persona: str


def _float(valor: str) -> float:
    return float(valor) if valor.strip() != "" else math.nan


def leer_y_validar(ruta: Path) -> tuple[Grabacion | None, list[str], list[str]]:
    """Devuelve la grabación, la lista de errores y la de advertencias."""
    errores: list[str] = []
    avisos: list[str] = []
    with ruta.open(newline="", encoding="utf-8") as f:
        lector = csv.reader(f)
        try:
            encabezado = next(lector)
        except StopIteration:
            return None, ["el archivo está vacío"], avisos
        filas = list(lector)

    if encabezado[:7] != COLUMNAS_CONTRATO:
        errores.append(f"las 7 primeras columnas deben ser {','.join(COLUMNAS_CONTRATO)}; se encontró {','.join(encabezado[:7])}")
        return None, errores, avisos
    extras = encabezado[7:]
    i_esc = extras.index("escenario") + 7 if "escenario" in extras else None
    i_tel = extras.index("telefono") + 7 if "telefono" in extras else None
    i_per = extras.index("persona") + 7 if "persona" in extras else None

    usuarios, ts, lats, lons, precs, vels, etiquetas = [], [], [], [], [], [], []
    for n, fila in enumerate(filas, start=2):
        if len(fila) != len(encabezado):
            errores.append(f"línea {n}: {len(fila)} campos, se esperaban {len(encabezado)}")
            continue
        try:
            t, lat, lon = float(fila[1]), float(fila[2]), float(fila[3])
            prec, vel = _float(fila[4]), _float(fila[5])
        except ValueError as e:
            errores.append(f"línea {n}: número inválido ({e})")
            continue
        if not fila[0] or "," in fila[0]:
            errores.append(f"línea {n}: usuario_id vacío")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            errores.append(f"línea {n}: coordenadas fuera de rango ({lat}, {lon})")
        if fila[6] and fila[6] not in MODOS:
            errores.append(f"línea {n}: modo_real '{fila[6]}' no es a_pie, quieto ni vehiculo")
        if not math.isnan(vel) and vel < 0:
            errores.append(f"línea {n}: velocidad negativa (debe quedar vacía si se desconoce)")
        etiqueta = fila[6] or "sin etiqueta"
        if i_esc is not None and fila[i_esc] == "trafico_lento":
            etiqueta = "vehiculo/trafico_lento"
        usuarios.append(fila[0])
        ts.append(t)
        lats.append(lat)
        lons.append(lon)
        precs.append(prec)
        vels.append(vel)
        etiquetas.append(etiqueta)

    if len(ts) < 2:
        errores.append("hacen falta al menos 2 muestras válidas")
        return None, errores, avisos

    t_arr = np.array(ts)
    for u in sorted(set(usuarios)):
        idx = [i for i, x in enumerate(usuarios) if x == u]
        if np.any(np.diff(t_arr[idx]) <= 0):
            errores.append(f"t no es estrictamente creciente para {u}")

    primera = filas[0]
    grab = Grabacion(
        usuario_id=usuarios,
        t=t_arr,
        lat=np.array(lats),
        lon=np.array(lons),
        precision=np.array(precs),
        velocidad=np.array(vels),
        etiqueta=etiquetas,
        extras=extras,
        telefono=primera[i_tel] if i_tel is not None else "?",
        persona=primera[i_per] if i_per is not None else "?",
    )

    dt = np.diff(grab.t)
    mediana = float(np.median(dt))
    if not 0.8 <= mediana <= 1.2:
        avisos.append(f"la frecuencia no es ~1 Hz: mediana de dt = {mediana:.2f} s")
    huecos = int(np.sum(dt > 5))
    if huecos:
        avisos.append(f"{huecos} huecos de más de 5 s sin GPS (máximo {dt.max():.0f} s)")
    if np.all(np.isnan(grab.precision)):
        avisos.append("precision_m está vacía en todas las filas")
    return grab, errores, avisos


def a_metros(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Proyección equirectangular local (suficiente para unos pocos km)."""
    lat0, lon0 = np.radians(lat[0]), np.radians(lon[0])
    x = RADIO_TIERRA_M * (np.radians(lon) - lon0) * math.cos(lat0)
    y = RADIO_TIERRA_M * (np.radians(lat) - lat0)
    return x, y


def tramos(etiquetas: list[str]) -> list[tuple[int, int, str]]:
    """Tramos consecutivos con la misma etiqueta: (inicio, fin_exclusivo, etiqueta)."""
    res, inicio = [], 0
    for i in range(1, len(etiquetas) + 1):
        if i == len(etiquetas) or etiquetas[i] != etiquetas[inicio]:
            res.append((inicio, i, etiquetas[inicio]))
            inicio = i
    return res


def resumen(g: Grabacion) -> dict:
    dt = np.diff(g.t, append=g.t[-1] + np.median(np.diff(g.t)))
    por_etiqueta = {}
    for e in dict.fromkeys(g.etiqueta):
        m = np.array([x == e for x in g.etiqueta])
        prec = g.precision[m]
        vel = g.velocidad[m]
        por_etiqueta[e] = {
            "muestras": int(m.sum()),
            "duracion_s": float(dt[m].sum()),
            "precision_media_m": float(np.nanmean(prec)) if not np.all(np.isnan(prec)) else math.nan,
            "velocidad_media_kmh": float(np.nanmean(vel) * 3.6) if not np.all(np.isnan(vel)) else math.nan,
        }
    cambios = [(float(g.t[a] - g.t[0]), e) for a, _, e in tramos(g.etiqueta)[1:]]
    return {
        "muestras": len(g.t),
        "duracion_s": float(g.t[-1] - g.t[0]),
        "frecuencia_hz": float(1 / np.median(np.diff(g.t))),
        "precision_media_m": float(np.nanmean(g.precision)) if not np.all(np.isnan(g.precision)) else math.nan,
        "por_etiqueta": por_etiqueta,
        "cambios": cambios,
    }


def mediana_movil(v: np.ndarray, ventana: int) -> np.ndarray:
    res = np.full_like(v, np.nan)
    for i in range(len(v)):
        trozo = v[max(0, i - ventana // 2): i + ventana // 2 + 1]
        if not np.all(np.isnan(trozo)):
            res[i] = np.nanmedian(trozo)
    return res


def mmss(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


def graficar(g: Grabacion, r: dict, titulo: str, salida: Path) -> None:
    x, y = a_metros(g.lat, g.lon)
    tmin = (g.t - g.t[0]) / 60
    vel = g.velocidad * 3.6
    # Si el teléfono no dio velocidad, se deriva de las posiciones para la gráfica.
    derivada = np.full_like(vel, np.nan)
    derivada[1:] = np.hypot(np.diff(x), np.diff(y)) / np.diff(g.t) * 3.6
    derivada = mediana_movil(derivada, 5)  # el ruido del GPS a 1 Hz la vuelve ilegible sin suavizar

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [1, 1.5]})
    fig.suptitle(titulo, fontsize=13, fontweight="bold", color=COLOR_MIGUEL)

    for e in dict.fromkeys(g.etiqueta):
        m = np.array([v == e for v in g.etiqueta])
        ax1.scatter(x[m], y[m], s=9, color=COLORES.get(e, "k"), label=e, alpha=0.8)
    ax1.plot(x, y, color="#9E9E9E", lw=0.5, zorder=0)
    ax1.scatter([x[0]], [y[0]], marker="^", s=90, color="k", label="inicio", zorder=3)
    ax1.set_aspect("equal", adjustable="datalim")
    ax1.set_xlabel("Este (m)")
    ax1.set_ylabel("Norte (m)")
    ax1.set_title("Traza coloreada por etiqueta")
    ax1.grid(alpha=0.3)
    ax1.legend(loc="best", fontsize=8)

    for a, b, e in tramos(g.etiqueta):
        fin = tmin[b] if b < len(tmin) else tmin[-1]
        ax2.axvspan(tmin[a], fin, color=COLORES.get(e, "k"), alpha=0.15, lw=0)
    for t_cambio, _ in r["cambios"]:
        ax2.axvline(t_cambio / 60, color="k", ls="--", lw=1)
    ax2.plot(tmin, derivada, color="#9E9E9E", lw=0.8, label="derivada de posiciones (mediana 5 s)")
    ax2.plot(tmin, vel, color=COLOR_MIGUEL, lw=1.2, label="velocidad del GPS")
    ax2.axhline(8, color="#1565C0", ls=":", lw=1, label="umbral 8 km/h")
    ax2.set_xlabel("Tiempo (min)")
    ax2.set_ylabel("Velocidad (km/h)")
    ax2.set_title("Velocidad en el tiempo (franjas = etiqueta, -- = cambio)")
    ax2.set_ylim(bottom=0, top=max(10, np.nanpercentile(np.concatenate([vel, derivada]), 99) * 1.2))
    ax2.grid(alpha=0.3)
    leyenda = [Patch(color=COLORES.get(e, "k"), alpha=0.3, label=e) for e in r["por_etiqueta"]]
    ax2.legend(handles=ax2.get_legend_handles_labels()[0] + leyenda, loc="upper right", fontsize=8)

    lineas = [f"{r['muestras']} muestras · {mmss(r['duracion_s'])} min · {r['frecuencia_hz']:.2f} Hz · "
              f"precisión media {r['precision_media_m']:.1f} m"]
    for e, d in r["por_etiqueta"].items():
        lineas.append(f"{e}: {mmss(d['duracion_s'])} min, {d['muestras']} muestras, "
                      f"precisión {d['precision_media_m']:.1f} m, velocidad media {d['velocidad_media_kmh']:.1f} km/h")
    fig.text(0.01, 0.01, "\n".join(lineas), fontsize=9, family="monospace", va="bottom")
    fig.tight_layout(rect=(0, 0.04 + 0.025 * len(lineas), 1, 0.95))
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--salida", type=Path, default=None, help="PNG de salida (por defecto, junto al CSV)")
    args = ap.parse_args()

    g, errores, avisos = leer_y_validar(args.csv)
    print(f"Archivo: {args.csv.name}")
    for a in avisos:
        print(f"  AVISO: {a}")
    if errores:
        for e in errores[:20]:
            print(f"  ERROR: {e}")
        print(f"Validación: FALLA ({len(errores)} errores)")
        return 1
    print("Validación: OK (columnas del contrato en orden" + (f", extras: {','.join(g.extras)})" if g.extras else ")"))

    r = resumen(g)
    print(f"Muestras: {r['muestras']} · duración {mmss(r['duracion_s'])} min · frecuencia {r['frecuencia_hz']:.2f} Hz"
          f" · precisión media {r['precision_media_m']:.1f} m")
    for e, d in r["por_etiqueta"].items():
        print(f"  {e:<24} {mmss(d['duracion_s']):>6} min  {d['muestras']:>5} muestras  "
              f"precisión {d['precision_media_m']:5.1f} m  velocidad {d['velocidad_media_kmh']:5.1f} km/h")
    for t_cambio, e in r["cambios"]:
        print(f"  cambio de etiqueta a los {mmss(t_cambio)} → {e}")

    salida = args.salida or args.csv.with_suffix(".png")
    titulo = f"Grabación {args.csv.stem} · {g.persona} · {g.telefono} · {g.usuario_id[0]}"
    graficar(g, r, titulo, salida)
    print(f"Figura: {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
