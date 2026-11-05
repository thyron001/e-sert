"""Evidencia de S3-1: `evidencias/s1_kpis-sistema.png` (2 × 2) a partir de las corridas de `correr_kpis`.

Se ejecuta desde `semanas/S3/Freddy/codigo` (en la computadora o en el contenedor), después de
correr `p50_umbral_s1` y `p50_rf_s1` (900 s) y `p50_rf_s1 --hasta 3600 --sufijo _3600`:

    python3 -m traci.graficas_kpis

Paneles: falsas liberaciones /100 (umbral vs rf); histograma del retardo de cierre; debitado vs
costo ideal y vs tarjeta SERT; serie temporal de la precisión del mapa (total y solo app).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
SALIDAS = AQUI / "salidas"
SALIDAS_KPI = AQUI / "salidas_kpi"
EVIDENCIAS = AQUI.parents[1] / "evidencias"
TOMATE, GRIS, AZUL = "#FF7043", "#7A7A7A", "#1E63D6"


def _csv(ruta: Path) -> list:
    with ruta.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(x: str) -> float:
    return float(x) if x not in ("", "nan", "None") else float("nan")


def generar(ids=("p50_umbral_s1", "p50_rf_s1"), principal: str = "p50_rf_s1_3600") -> Path:
    """(a) compara `ids` (900 s); (b)–(d) usan la corrida `principal` (más larga: hay salidas reales)."""
    leer = lambda i: json.loads((SALIDAS_KPI / f"ejemplo_{i}.json").read_text(encoding="utf-8"))  # noqa: E731
    resumenes = {i: leer(i) for i in ids}
    resumenes[principal] = leer(principal)
    sesiones = _csv(SALIDAS / f"kpis_sesiones_{principal}.csv")
    mapa = _csv(SALIDAS / f"kpis_mapa_{principal}.csv")

    fig, ax = plt.subplots(2, 2, figsize=(12, 8.5))
    # (a) falsas liberaciones por 100 sesiones
    a = ax[0, 0]
    etiquetas = [f"{resumenes[i]['clasificador_pedido']}\n(usó {resumenes[i]['clasificador_usado']})" for i in ids]
    valores = [resumenes[i]["kpis"]["falsas_lib_100"] or 0 for i in ids]
    barras = a.bar(etiquetas, valores, color=[GRIS, TOMATE])
    for b, i in zip(barras, ids):
        k = resumenes[i]["kpis"]
        a.annotate(f"{k['falsas_lib_100']:.1f}\n({k['n_falsas']}/{k['n_sesiones']})",
                   (b.get_x() + b.get_width() / 2, b.get_height()), ha="center", va="bottom")
    a.set_ylabel("falsas liberaciones / 100 sesiones cerradas")
    a.set_title("(a) Falsas liberaciones, 50 % con app, s1, 900 s")
    a.set_ylim(0, max(valores + [1]) * 1.25)

    # (b) retardo de cierre
    b = ax[0, 1]
    retardos = [_num(s["retardo_cierre_s"]) for s in sesiones]
    retardos = [r for r in retardos if r == r]
    k = resumenes[principal]["kpis"]
    if retardos:
        b.hist(retardos, bins=20, color=TOMATE, edgecolor="white")
        b.axvline(k["retardo_cierre_mediana_s"], color="black", ls="--",
                  label=f"mediana {k['retardo_cierre_mediana_s']:.0f} s")
        b.axvline(k["retardo_cierre_p90_s"], color=GRIS, ls=":", label=f"p90 {k['retardo_cierre_p90_s']:.0f} s")
        b.legend()
    else:
        b.text(0.5, 0.5, "sin cierres correctos", ha="center", transform=b.transAxes)
    b.set_xlabel("t_cerrada − t_salida_real (s)")
    b.set_ylabel("sesiones")
    b.set_title(f"(b) Retardo de cierre ({principal}, n={len(retardos)})")

    # (c) facturación
    c = ax[1, 0]
    filas = [s for s in sesiones if _num(s["costo_ideal"]) == _num(s["costo_ideal"])]
    ideal = [_num(s["costo_ideal"]) for s in filas]
    debitado = [_num(s["debitado"]) for s in filas]
    tarjeta = [_num(s["tarjeta_sert_usd"]) for s in filas]
    falsa = [s["falsa"] == "True" for s in filas]
    tope = max(ideal + debitado + tarjeta + [0.5]) * 1.1
    c.plot([0, tope], [0, tope], color="black", lw=0.8, label="sin error")
    c.scatter(ideal, debitado, s=18, color=[GRIS if f else TOMATE for f in falsa],
              label="debitado (gris: falsa liberación)")
    c.scatter(ideal, tarjeta, s=14, marker="x", color=AZUL, label="tarjeta SERT")
    c.set_xlabel("costo ideal con la estadía real de SUMO (USD)")
    c.set_ylabel("USD")
    c.set_title(f"(c) Debitado vs ideal: error medio {k['error_fact_medio_usd']:+.3f} USD; "
                f"ahorro medio {k['ahorro_vs_tarjeta_medio_usd']:+.3f}", fontsize=10)
    c.legend(fontsize=8, loc="upper left")

    # (d) precisión del mapa
    d = ax[1, 1]
    t = [_num(m["t_sim"]) / 60 for m in mapa]
    d.plot(t, [_num(m["precision"]) for m in mapa], color=GRIS, marker="o", ms=3,
           label=f"vs ocupación total (media {k['precision_mapa']:.2f})")
    d.plot(t, [_num(m["precision_app"]) for m in mapa], color=TOMATE, marker="o", ms=3,
           label=f"vs solo usuarios con app (media {k['precision_mapa_app']:.2f})")
    d.set_ylim(0, 1.05)
    d.set_xlabel("tiempo simulado (min)")
    d.set_ylabel("exactitud libre/lleno por puesto")
    d.set_title("(d) Precisión del mapa de ocupación")
    d.legend(fontsize=8, loc="lower left")

    dur = resumenes[principal]["t_sim_final"] / 60
    fig.suptitle(f"S3-1 · KPIs de sistema (Freddy) · (b)–(d): {principal}, {dur:.0f} min simulados", fontsize=13)
    fig.tight_layout()
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    salida = EVIDENCIAS / "s1_kpis-sistema.png"
    fig.savefig(salida, dpi=150)
    return salida


if __name__ == "__main__":
    print(generar())
