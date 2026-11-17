"""Figuras de la sección de Freddy del informe (S4-3), a 300 dpi.

    python informe/figuras/freddy/generar_figuras.py      # desde la carpeta con backend/, comun/, traci/, informe/

- `f01_componentes.png` y `f04_estados_sesion.png`: copia de los renders de `comun/docs/diagramas/`
  (se regeneran con `comun/docs/generar_diagramas.py`).
- `f02_traza_gps.png`: traza verdadera de un peatón de SUMO (`traci/trazas/sumo_semilla1_muestra.csv`)
  frente a la que emite `EmuladorGPS` con σ = 5 y 10 m, y la velocidad que derivaría el teléfono.
- `f03_rendimiento.png`: ms por paso de TraCI con 0/20/50/80 % de penetración
  (`informe/datos/freddy/corridas.json`, de `informe/freddy_cifras.py corridas`).
"""

from __future__ import annotations

import csv
import json
import math
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parents[2]
if str(CODIGO) not in sys.path:
    sys.path.insert(0, str(CODIGO))

from traci.gps import EmuladorGPS, conversor_plano  # noqa: E402

DIAGRAMAS = CODIGO / "comun" / "docs" / "diagramas"
TRAZAS = CODIGO / "traci" / "trazas" / "sumo_semilla1_muestra.csv"
DATOS = CODIGO / "informe" / "datos" / "freddy"
CORRIDAS = DATOS / "corridas.json"
AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA_2, REJILLA = "#0b0b0b", "#5f5e58", "#e1e0d9"
PEATON = "ped_p13"
UMBRAL_VEH_KMH = 8.0  # contrato §2: umbral de velocidad del clasificador de reserva


def estilo(ax):
    ax.grid(color=REJILLA, linewidth=0.6)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(colors=TINTA_2)


def copiar_diagramas():
    """Renderiza los diagramas a escala 4 (legibles a ancho de página) y los guarda a 300 dpi.

    Usa el mismo mermaid-cli 10.9.1 que `comun/docs/generar_diagramas.py` (npx o Docker); si no hay
    motor, copia el render de escala 2 de `comun/docs/diagramas/`."""
    import subprocess

    from PIL import Image

    from comun.docs.generar_diagramas import comando, elegir_motor

    motor = elegir_motor(None)
    for origen, destino in (("componentes", "f01_componentes.png"), ("estados_sesion", "f04_estados_sesion.png")):
        salida = AQUI / destino
        if motor:
            r = subprocess.run(comando(motor, DIAGRAMAS / f"{origen}.mmd", salida, escala=4), capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(r.stderr[-800:])
        else:
            shutil.copyfile(DIAGRAMAS / f"{origen}.png", salida)
        Image.open(salida).save(salida, dpi=(300, 300))
        print(f"→ {salida}")


def traza_gps():
    filas = [f for f in csv.DictReader(TRAZAS.open(encoding="utf-8")) if f["usuario_id"] == PEATON]
    lat0, lon0 = float(filas[0]["lat_real"]), float(filas[0]["lon_real"])
    m_lat, m_lon = 111_320.0, 111_320.0 * math.cos(math.radians(lat0))
    verdad = [((float(f["lon_real"]) - lon0) * m_lon, (float(f["lat_real"]) - lat0) * m_lat, float(f["t"]),
               float(f["velocidad_real_mps"] or 0)) for f in filas]
    a_geo = conversor_plano(lat0, lon0)
    resumen = {"peaton": PEATON, "muestras_verdaderas": len(verdad), "umbral_kmh": UMBRAL_VEH_KMH,
               "velocidad_real_media_kmh": round(sum(v[3] for v in verdad) / len(verdad) * 3.6, 2), "por_sigma": {}}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [1, 1.35]})
    ax1.plot([v[0] for v in verdad], [v[1] for v in verdad], color=TINTA, linewidth=2, label="Trayectoria verdadera")
    tv = [v[2] - verdad[0][2] for v in verdad]
    ax2.plot(tv, [v[3] * 3.6 for v in verdad], color=TINTA, linewidth=2, label="Velocidad verdadera")
    for sigma, color in ((5, AZUL), (10, NARANJA)):
        gps = EmuladorGPS(semilla=1, sigma_m=sigma, p_perdida=0.05, rho=0.8)
        obs = [gps.observar(PEATON, t, x, y, "a_pie", a_geo) for x, y, t, _ in verdad]
        puntos = [o for o in obs if o]
        xs = [(o["lon"] - lon0) * m_lon for o in puntos]
        ys = [(o["lat"] - lat0) * m_lat for o in puntos]
        ax1.plot(xs, ys, color=color, linewidth=1, alpha=0.9, marker="o", markersize=2.2,
                 label=f"GPS emulado, σ = {sigma} m")
        vel = [(o["t"] - verdad[0][2], o["velocidad_mps"] * 3.6) for o in puntos if o["velocidad_mps"] is not None]
        sobre = sum(1 for _, v in vel if v > UMBRAL_VEH_KMH)
        resumen["por_sigma"][str(sigma)] = {
            "muestras_emitidas": len(puntos), "perdidas": len(verdad) - len(puntos),
            "velocidad_telefono_media_kmh": round(sum(v for _, v in vel) / len(vel), 2),
            "frac_sobre_umbral": round(sobre / len(vel), 3)}
        ax2.plot([v[0] for v in vel], [v[1] for v in vel], color=color, linewidth=1, alpha=0.9,
                 label=f"Velocidad del teléfono, σ = {sigma} m")
    ax2.axhline(UMBRAL_VEH_KMH, color=TINTA_2, linestyle="--", linewidth=1)
    ax2.text(tv[-1], UMBRAL_VEH_KMH - 1.2, "umbral vehículo, 8 km/h", ha="right", va="top", color=TINTA_2,
             fontsize=8, bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
    ax1.set_xlabel("Este (m)")
    ax1.set_ylabel("Norte (m)")
    ax1.set_aspect("equal", adjustable="datalim")
    ax1.set_title("a) Posición", loc="left", color=TINTA, fontsize=10)
    ax2.set_xlabel("Tiempo (s)")
    ax2.set_ylabel("Velocidad (km/h)")
    ax2.set_title("b) Velocidad derivada de posiciones consecutivas", loc="left", color=TINTA, fontsize=10)
    for ax in (ax1, ax2):
        estilo(ax)
        ax.legend(fontsize=7.5, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(AQUI / "f02_traza_gps.png", dpi=300)
    plt.close(fig)
    DATOS.mkdir(parents=True, exist_ok=True)
    (DATOS / "traza_gps.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"→ {DATOS / 'traza_gps.json'}: {resumen['por_sigma']}")
    print(f"→ {AQUI / 'f02_traza_gps.png'}")


def rendimiento():
    if not CORRIDAS.is_file():
        print(f"(sin {CORRIDAS}: corre `python informe/freddy_cifras.py corridas`)")
        return
    d = json.loads(CORRIDAS.read_text(encoding="utf-8"))["corridas"]
    pens = [c["penetracion"] for c in d]
    ms = [c["ms_por_paso"] for c in d]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    barras = ax.bar([f"{p} %" for p in pens], ms, color=AZUL, width=0.55)
    for b, v in zip(barras, ms):
        ax.text(b.get_x() + b.get_width() / 2, v + max(ms) * 0.02, f"{v:.1f}".replace(".", ","), ha="center",
                fontsize=9, color=TINTA)
    ax.set_xlabel("Penetración de la app")
    ax.set_ylabel("ms por paso simulado de 1 s")
    ax.set_ylim(0, max(ms) * 1.18)
    estilo(ax)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(AQUI / "f03_rendimiento.png", dpi=300)
    plt.close(fig)
    print(f"→ {AQUI / 'f03_rendimiento.png'}")


if __name__ == "__main__":
    copiar_diagramas()
    traza_gps()
    rendimiento()
