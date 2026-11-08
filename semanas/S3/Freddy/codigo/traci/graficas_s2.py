"""Evidencias de S3-2 (Freddy): rendimiento con 80 % de app y robustez ante la pérdida de GPS.

Se ejecuta desde `semanas/S3/Freddy/codigo` (en la computadora o en el contenedor), después de
`traci.perfil` (tres variantes) y `traci.robustez`:

    python3 -m traci.graficas_s2

- `evidencias/s2_rendimiento-80.png`: ms por paso por bloque (barras apiladas), antes y después
  de optimizar, con el factor de tiempo real en el título.
- `evidencias/s2_robustez-perdida-gps.png`: falsas liberaciones /100 frente a `p_perdida`, a la
  duración de la ráfaga y al ruido, con umbral y rf, e IC 95 % entre semillas (t de Student, gl = 1).
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
SALIDAS_KPI = AQUI / "salidas_kpi"
EVIDENCIAS = AQUI.parents[1] / "evidencias"
COLORES = {"simulationStep": "#4C4C4C", "suscripciones": "#9E9E9E", "gps": "#1E63D6", "inferencia": "#2E9E4F",
           "maquina": "#FF7043", "nucleo": "#C62828", "guiado": "#8E6CC0", "peatones": "#00897B",
           "kpis": "#F9A825", "ws": "#6D4C41", "otros": "#D7CCC8"}
VARIANTES = (("antes", "antes\n(traci, todo suscrito,\nsin caché ni lote)"),
             ("despues", "después\n(traci)"),
             ("despues_libsumo", "después\n(libsumo)"))
T_95 = {1: 12.706, 2: 4.303, 3: 3.182}


def rendimiento(id_corrida: str = "p80_rf_s1") -> Path:
    datos = {v: json.loads((SALIDAS_KPI / f"perfil_{id_corrida}_{v}.json").read_text(encoding="utf-8"))
             for v, _ in VARIANTES}
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 5.6), gridspec_kw={"width_ratios": [1.25, 1]})
    x = range(len(VARIANTES))
    base = [0.0] * len(VARIANTES)
    for bloque, color in COLORES.items():
        vals = [datos[v]["ms_por_paso_por_bloque"].get(bloque, 0.0) for v, _ in VARIANTES]
        a.bar(x, vals, bottom=base, color=color, label=bloque, edgecolor="white", linewidth=0.5)
        base = [p + q for p, q in zip(base, vals)]
    for i, (v, _) in enumerate(VARIANTES):
        d = datos[v]
        a.annotate(f"{d['ms_por_paso_medio']:.0f} ms (p95 {d['ms_por_paso_p95']:.0f})\n"
                   f"factor {d['factor_tiempo_real']:.1f}×", (i, base[i]), ha="center", va="bottom", fontsize=9)
    a.set_xticks(list(x), [et for _, et in VARIANTES], fontsize=9)
    a.set_ylabel("ms por paso (media, 1 paso = 1 s simulado)")
    a.set_ylim(0, max(base) * 1.25)
    a.legend(fontsize=8, ncol=2, loc="upper right")
    a.set_title("(a) Costo medio por bloque")

    # (b) serie del paso: el p95 lo marcan los primeros minutos (inserción de ~5 000 autos)
    for v, et in VARIANTES:
        serie = datos[v].get("ms_por_paso_serie")
        if serie:
            ventana = 30
            suave = [statistics.fmean(serie[max(0, i - ventana):i + 1]) for i in range(len(serie))]
            b.plot(range(1, len(serie) + 1), suave, label=" ".join(et.split("\n")[:2]).rstrip(","), lw=1.2)
    b.axhline(100, color="black", ls="--", lw=0.8, label="meta p95 = 100 ms")
    b.set_yscale("log")
    b.set_xlabel("tiempo simulado (s)")
    b.set_ylabel("ms por paso (media móvil de 30 s, escala log)")
    b.set_title("(b) Costo del paso a lo largo de la corrida")
    b.legend(fontsize=8)
    mejor = datos["despues_libsumo"]
    fig.suptitle(f"S3-2 · Rendimiento con 80 % de autos con app ({id_corrida}, 1 800 s sin GUI): "
                 f"factor {datos['antes']['factor_tiempo_real']:.1f}× → {mejor['factor_tiempo_real']:.1f}× "
                 f"(meta ≥ 10×)", fontsize=12)
    fig.tight_layout()
    salida = EVIDENCIAS / "s2_rendimiento-80.png"
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    return salida


def _media_ic(xs):
    m = statistics.fmean(xs)
    if len(xs) < 2:
        return m, 0.0
    return m, T_95.get(len(xs) - 1, 1.96) * statistics.stdev(xs) / math.sqrt(len(xs))


def robustez() -> Path:
    with (SALIDAS_KPI / "robustez.csv").open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    grupos = defaultdict(list)
    for r in filas:
        if r["falsas_lib_100"] not in ("", "nan", "None"):
            grupos[(r["familia"], float(r["valor"]), r["clasificador"])].append(float(r["falsas_lib_100"]))
    fig, ejes = plt.subplots(2, 2, figsize=(13, 9))
    paneles = (("perdida", "(a) pérdida independiente p_perdida", lambda v: f"{v:.2f}"),
               ("rafaga", "(b) ráfaga media (s), 30 % del tiempo sin señal", lambda v: f"{v:.0f}"),
               ("ruido", "(c) ruido σ (m)", lambda v: f"{v:.0f}"))
    estilos = {"umbral": ("#7A7A7A", "o", -0.08), "rf": ("#FF7043", "s", 0.08)}
    for ax, (familia, etiqueta, fmt) in zip(ejes.flat, paneles):
        valores = sorted({v for (f_, v, _) in grupos if f_ == familia})
        for clf, (color, marca, dx) in estilos.items():
            ms, abajo, arriba, xs = [], [], [], []
            for i, v in enumerate(valores):
                datos = grupos.get((familia, v, clf))
                if datos:
                    m, ic = _media_ic(datos)
                    ms.append(m)
                    abajo.append(min(ic, m))
                    arriba.append(min(ic, 100 - m))  # una tasa no pasa de 100
                    xs.append(i + dx)
            ax.errorbar(xs, ms, yerr=[abajo, arriba], color=color, marker=marca, capsize=4, label=clf, lw=1.2)
        ax.set_xticks(range(len(valores)), [fmt(v) for v in valores])
        ax.set_title(etiqueta)
        ax.set_ylim(0, 105)
        ax.set_ylabel("falsas liberaciones / 100 cerradas")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="lower left")

    # (d) efecto de la política de datos pobres (ráfagas de 60 s, umbral)
    d = ejes[1, 1]
    con = [r for r in filas if r["familia"] == "rafaga" and float(r["valor"]) == 60 and r["clasificador"] == "umbral"]
    sin = [r for r in filas if r["familia"] == "sin_politica" and r["clasificador"] == "umbral"]
    etiquetas, pobres, retenidas = [], [], []
    for nombre, grupo in (("con política", con), ("sin política", sin)):
        for r in sorted(grupo, key=lambda r: r["semilla"]):
            etiquetas.append(f"{nombre}\nsemilla {r['semilla']}")
            pobres.append(int(r["falsas_con_datos_pobres"]))
            retenidas.append(int(r["ventanas_retenidas"]))
    barras = d.bar(range(len(etiquetas)), pobres, color=["#2E9E4F"] * len(con) + ["#C62828"] * len(sin))
    for b, n, ret in zip(barras, pobres, retenidas):
        d.annotate(f"{n}\n({ret} ventanas\nretenidas)", (b.get_x() + b.get_width() / 2, b.get_height()),
                   ha="center", va="bottom", fontsize=8)
    d.set_xticks(range(len(etiquetas)), etiquetas, fontsize=8)
    d.set_ylim(0, max(pobres + [1]) * 1.6)
    d.set_ylabel("falsas liberaciones decididas\ncon ventanas incompletas")
    d.set_title("(d) Política de datos pobres (ráfagas de 60 s, umbral)")
    usados = {r["clasificador_usado"] for r in filas if r["clasificador"] == "rf"}
    nota = " · rf cayó al umbral (no hay rf_v1.joblib)" if usados == {"umbral"} else ""
    n = {r["semilla"] for r in filas}
    fig.suptitle(f"S3-2 · Robustez del GPS, 50 % con app, 1 800 s, {len(n)} semillas, media ± IC 95 %{nota}",
                 fontsize=12)
    fig.tight_layout()
    salida = EVIDENCIAS / "s2_robustez-perdida-gps.png"
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    return salida


if __name__ == "__main__":
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    for f in (rendimiento, robustez):
        try:
            print(f())
        except FileNotFoundError as err:
            print(f"falta {err.filename}")
