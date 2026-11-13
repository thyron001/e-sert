"""KPIs de los escenarios con app: tabla resumen y figuras (S2-3).

Uso (desde la carpeta que contiene `kpis/` y `sumo/`, con kpis/.venv):
    python -m kpis.resumen_escenarios [--calcular] [--evidencias ../evidencias] [--guiado-provisional]

--calcular aplica `kpis.kpis` a cada corrida de sumo/escenarios/escenarios.json (salidas en
sumo/salidas/<escenario>_s<N>/) y comprueba la ocupación real registrada contra el
stop-output. Después escribe kpis/salidas/resumen_escenarios.csv (escenario, semilla,
% app, búsqueda media con IC 95 %, distancia media, CO2 de búsqueda, ocupación media en la
hora pico, y la búsqueda media de quienes tienen app y de quienes no) y las figuras:
    s3_penetracion-escenarios.png   búsqueda media (IC 95 %) frente al % de app, una línea por semilla
    s3_ocupacion-real.png           mapa de calor puesto x tiempo de la ocupación real de app50_s1
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from kpis.kpis import SALIDAS, resumen_estadistico  # noqa: E402
from kpis.registrar_ocupacion import comprobar  # noqa: E402

DIR_CODIGO = Path(__file__).resolve().parent.parent
ESCENARIOS = DIR_CODIGO / "sumo" / "escenarios" / "escenarios.json"
SALIDAS_SUMO = DIR_CODIGO / "sumo" / "salidas"


def leer_escenarios():
    return json.loads(ESCENARIOS.read_text(encoding="utf-8"))["escenarios"]


def calcular(escenarios):
    """Corre kpis.kpis sobre cada corrida y comprueba la ocupación real (±1 puesto)."""
    comprobaciones = {}
    for e in escenarios:
        tipo = e["escenario"].rsplit("_s", 1)[0]
        carpeta = SALIDAS_SUMO / e["escenario"]
        subprocess.run([sys.executable, "-m", "kpis.kpis", "--salidas", str(carpeta),
                        "--escenario", tipo, "--semilla", str(e["semilla"]),
                        "--demanda", str(ESCENARIOS.parent / e["rou"])],
                       cwd=DIR_CODIGO, check=True)
        comprobaciones[e["escenario"]] = comprobar(SALIDAS / f"ocupacion_real_{e['escenario']}.csv",
                                                   carpeta / "stops.xml")
        print(e["escenario"], comprobaciones[e["escenario"]], flush=True)
    (SALIDAS / "comprobacion_ocupacion_real.json").write_text(
        json.dumps(comprobaciones, indent=1), encoding="utf-8")
    return comprobaciones


def teletransportes(carpeta):
    import xml.etree.ElementTree as ET
    raiz = ET.parse(carpeta / "estadisticas.xml").getroot()
    # Con guiado, `loaded` suma una carga por cada rerouteParkingArea: se usa `inserted`
    return int(raiz.find("teleports").get("total")), int(raiz.find("vehicles").get("inserted"))


def tabla(escenarios):
    filas = []
    for e in escenarios:
        tipo = e["escenario"].rsplit("_s", 1)[0]
        s = str(e["semilla"])
        v = pd.read_csv(SALIDAS / f"{tipo}_{s}_vehiculos.csv")
        info = json.loads((SALIDAS / f"{tipo}_{s}_info.json").read_text(encoding="utf-8"))
        o = pd.read_csv(SALIDAS / f"{tipo}_{s}_ocupacion.csv")
        o = o[(o["t"] >= info["warmup_s"]) & (o["t"] < info["fin_s"])]
        t = resumen_estadistico(v["tiempo_busqueda_s"])
        app = v[v["con_app"] == 1]["tiempo_busqueda_s"]
        sin = v[v["con_app"] != 1]["tiempo_busqueda_s"]
        tele, insertados = teletransportes(SALIDAS_SUMO / e["escenario"])
        filas.append({
            "escenario": tipo, "semilla": e["semilla"], "porc_app": e["porc_app"],
            "busqueda_media_s": round(t["media"], 1),
            "busqueda_ic95_lo": round(t["ic95"][0], 1), "busqueda_ic95_hi": round(t["ic95"][1], 1),
            "distancia_media_m": round(v["distancia_busqueda_m"].mean(), 1),
            "co2_busqueda_medio_g": round(v["co2_busqueda_g"].mean(), 1),
            "co2_busqueda_total_kg": round(v["co2_busqueda_g"].sum() / 1000, 1),
            "ocupacion_media_pico": round(o["ocupacion"].mean(), 4),
            "busqueda_media_con_app_s": round(app.mean(), 1) if len(app) else None,
            "busqueda_media_sin_app_s": round(sin.mean(), 1) if len(sin) else None,
            "buscadores_con_kpi": len(v), "sin_estacionar": info["buscadores_sin_estacionar"],
            "teletransportes": tele, "porc_teletransportes": round(100 * tele / insertados, 3),
        })
    df = pd.DataFrame(filas).sort_values(["semilla", "porc_app"])
    df.to_csv(SALIDAS / "resumen_escenarios.csv", index=False)
    return df


def figura_penetracion(df, destino, provisional):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for (semilla, g), color in zip(df.groupby("semilla"), ["#1E63D6", "#FF9F1C"]):
        g = g.sort_values("porc_app")
        err = [g["busqueda_media_s"] - g["busqueda_ic95_lo"], g["busqueda_ic95_hi"] - g["busqueda_media_s"]]
        ax.errorbar(g["porc_app"], g["busqueda_media_s"], yerr=err, marker="o", capsize=5,
                    color=color, label=f"semilla {semilla} (todos los buscadores)")
        ax.plot(g["porc_app"], g["busqueda_media_con_app_s"], ls=":", marker="^", color=color,
                alpha=0.8, label=f"semilla {semilla}, solo con app")
    ax.set_xticks([0, 20, 50, 80])
    ax.set_xlabel("Buscadores con la app (%)")
    ax.set_ylabel("Tiempo de búsqueda medio (s), IC 95 %")
    titulo = "Tiempo de búsqueda frente a la penetración de la app"
    if provisional:
        titulo += "\nGUIADO PROVISIONAL (oráculo MOCK con la ocupación real; no es el guiado de Freddy)"
    ax.set_title(titulo, fontsize=11)
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    print(f"Figura -> {destino}")


def figura_ocupacion(escenario, destino):
    real = pd.read_csv(SALIDAS / f"ocupacion_real_{escenario}.csv")
    real["ocupacion"] = real["ocupados"] / real["capacidad"]
    m = real.pivot(index="puesto_id", columns="t_sim", values="ocupacion")
    # Puestos ordenados por su ocupación media (los que se llenan antes, arriba)
    m = m.loc[m.mean(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(11, 7))
    im = ax.imshow(m.to_numpy(), aspect="auto", cmap="RdYlGn_r", vmin=0, vmax=1,
                   extent=[m.columns.min() / 60, m.columns.max() / 60, len(m), 0],
                   interpolation="nearest")
    ax.axvline(15, color="black", ls="--", lw=1)
    ax.text(15.3, len(m) * 0.03, "fin del warm-up", fontsize=8)
    ax.set_xlabel("Tiempo de simulación (min)")
    ax.set_ylabel(f"Puestos ({len(m)} parkingArea, ordenados por ocupación media)")
    total = real.groupby("t_sim")["ocupados"].sum() / real.groupby("t_sim")["capacidad"].sum()
    ax.set_title(f"Ocupación real por puesto · {escenario} (registrador TraCI cada 60 s) · "
                 f"media en la hora pico {100 * total[total.index >= 900].mean():.1f} %", fontsize=11)
    fig.colorbar(im, ax=ax, label="ocupados / capacidad")
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    print(f"Figura -> {destino}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--calcular", action="store_true")
    ap.add_argument("--evidencias", default=str(DIR_CODIGO.parent / "evidencias"))
    ap.add_argument("--guiado-provisional", action="store_true",
                    help="marca la figura como guiado provisional (oráculo MOCK)")
    args = ap.parse_args()
    escenarios = leer_escenarios()
    if args.calcular:
        calcular(escenarios)
    df = tabla(escenarios)
    print(df.drop(columns=["busqueda_ic95_lo", "busqueda_ic95_hi"]).to_string(index=False))
    ev = Path(args.evidencias)
    figura_penetracion(df, ev / "s3_penetracion-escenarios.png", args.guiado_provisional)
    figura_ocupacion("app50_s1", ev / "s3_ocupacion-real.png")


if __name__ == "__main__":
    main()
