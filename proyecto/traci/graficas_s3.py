"""Evidencias de S2-3: guiado frente a sin app, y cobros simulados.

Dentro del contenedor van3twin, desde `semanas/S2/Freddy/codigo`:

    python3 -m traci.graficas_s3 --escenario app50_s1

Genera en `semanas/S2/Freddy/evidencias/`:
- `s3_guiado-vs-ciegas.png`: histogramas superpuestos del tiempo de búsqueda con app y sin app;
- `s3_cobros-simulados.png`: minutos reales frente a cobrados por sesión, con la escalera de 5 min.

`proyecto/kpis/kpis.py` todavía no existe (la carpeta solo tiene `.gitkeep`), así que las cifras
se calculan aquí desde los CSV de `traci/salidas/`.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from backend.nucleo import tarifa as tar  # noqa: E402

AQUI = Path(__file__).resolve().parent
SALIDAS = AQUI / "salidas"
EVIDENCIAS = AQUI.parents[1] / "evidencias"


def _leer(ruta: Path) -> list:
    with ruta.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def guiado_vs_ciegas(escenario: str, salida: Path) -> dict:
    filas = [f for f in _leer(SALIDAS / f"busqueda_{escenario}.csv") if f["tiempo_busqueda_s"]]
    con = [float(f["tiempo_busqueda_s"]) / 60 for f in filas if f["con_app"] == "1"]
    sin = [float(f["tiempo_busqueda_s"]) / 60 for f in filas if f["con_app"] == "0"]
    fig, ax = plt.subplots(figsize=(9, 5))
    bins = range(0, int(max(con + sin, default=1)) + 3, 1)
    ax.hist(sin, bins=bins, alpha=0.55, color="#9E9E9E", label=f"sin app (n={len(sin)})")
    ax.hist(con, bins=bins, alpha=0.6, color="#FF7043", label=f"con app, guiados (n={len(con)})")
    ax.axvline(statistics.median(sin), color="#616161", ls="--", lw=1.2,
               label=f"mediana sin app: {statistics.median(sin):.1f} min")
    ax.axvline(statistics.median(con), color="#E64A19", ls="--", lw=1.2,
               label=f"mediana con app: {statistics.median(con):.1f} min")
    ax.set_xlabel("tiempo de búsqueda (min, salida → estacionamiento)")
    ax.set_ylabel("autos")
    ax.set_title(f"Búsqueda con y sin app · {escenario}", loc="left", fontsize=11)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    return {"n_con_app": len(con), "n_sin_app": len(sin),
            "media_con_app_min": round(statistics.mean(con), 2) if con else None,
            "media_sin_app_min": round(statistics.mean(sin), 2) if sin else None,
            "mediana_con_app_min": round(statistics.median(con), 2) if con else None,
            "mediana_sin_app_min": round(statistics.median(sin), 2) if sin else None}


def cobros(escenario: str, salida: Path) -> dict:
    filas = _leer(SALIDAS / f"sesiones_{escenario}.csv")
    reales = [float(f["minutos_reales"]) for f in filas]
    cobrados = [float(f["minutos_cobrados"]) for f in filas]
    fig, ax = plt.subplots(figsize=(9, 5))
    xs = [x / 2 for x in range(0, int(max(reales, default=120) * 2) + 2)]
    ax.step(xs, [tar.minutos_cobrables(x) for x in xs], where="post", color="#1E63D6", lw=1.5,
            label="escalera: fracciones de 5 min, mínimo 10 min")
    ax.scatter(reales, cobrados, s=14, color="#FF7043", alpha=0.7, label=f"sesiones (n={len(filas)})")
    ax.set_xlabel("minutos reales")
    ax.set_ylabel("minutos cobrados")
    ax.set_title(f"Cobros simulados por sesión · {escenario}", loc="left", fontsize=11)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    return {"sesiones": len(filas),
            "minutos_reales_medios": round(statistics.mean(reales), 2) if reales else None,
            "minutos_cobrados_medios": round(statistics.mean(cobrados), 2) if cobrados else None}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Evidencias gráficas de S2-3")
    ap.add_argument("--escenario", default="app50_s1")
    args = ap.parse_args(argv)
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    print("busqueda:", guiado_vs_ciegas(args.escenario, EVIDENCIAS / "s3_guiado-vs-ciegas.png"))
    print("cobros:", cobros(args.escenario, EVIDENCIAS / "s3_cobros-simulados.png"))


if __name__ == "__main__":
    main()
