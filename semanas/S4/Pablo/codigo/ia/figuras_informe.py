"""
Figuras de la sección de IA del informe (S4-2). Se regeneran desde los reportes, sin reentrenar.

    python3 -m ia.figuras_informe

Entradas (en ia/reportes/ y ia/modelos/, todas de `rf_final`):
  metricas_rf_final.json, curvas_sigma_final.csv, importancia_permutacion_final.csv,
  velocidad_por_clase.csv, suavizado_k_final.csv, suavizado_k_final_contrato.csv,
  entrenamiento_final_datos.json y, para la última figura, `kpis/resultados/final/resumen.csv` de la rama
  `origin/tyrone/s4` (se lee con `git show`; si no existe se dibuja un panel marcado como pendiente).
Salida: informe/figuras/pablo/f0N_*.png a 300 dpi, con ejes en español y verde del equipo (#2E9E4F) para RF.
"""
import io
import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

AQUI = Path(__file__).resolve().parent
REP = AQUI / "reportes"
SALIDA = AQUI.parent / "informe" / "figuras" / "pablo"
VERDE, VERDE_CLARO, GRIS, GRIS_CLARO, INK, MUTED, GRID = "#2E9E4F", "#8CD0A1", "#6B6F78", "#B9BCC4", "#222222", "#666666", "#DDDDDD"
CLASES = ["a_pie", "quieto", "vehiculo"]
ETQ = {"a_pie": "a pie", "quieto": "quieto", "vehiculo": "vehículo"}
FUENTES_TXT = {"geolife_prueba": "GeoLife\n(no vistos)", "sumo_normal": "SUMO\nnormal", "sumo_trafico_lento": "SUMO tráfico\nlento",
               "sumo_peaton_rapido": "SUMO peatón\nrápido"}
DPI = 300
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK, "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlesize": 10})


def _limpio(ax, grid="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis=grid, color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def _guardar(fig, nombre):
    SALIDA.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(SALIDA / nombre, dpi=DPI)
    plt.close(fig)
    print("->", SALIDA / nombre)


def _metricas():
    return json.loads((REP / "metricas_rf_final.json").read_text())


def f01_ventanas():
    m = _metricas()["fuentes"]
    ent = json.loads((REP / "entrenamiento_final_datos.json").read_text())["por_origen_y_clase"]
    filas = {"GeoLife\nentrenamiento": {r["modo_real"]: r["n"] for r in ent if r["origen"] == "geolife"},
             "SUMO\nentrenamiento": {r["modo_real"]: r["n"] for r in ent if r["origen"] == "sumo"}}
    for k, nombre in FUENTES_TXT.items():
        if k in m:
            filas[nombre] = {c: m[k]["rf_final"]["por_clase"][c]["support"] for c in CLASES}
    df = pd.DataFrame(filas).T.reindex(columns=CLASES).fillna(0)
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    x = np.arange(len(df))
    colores = {"a_pie": GRIS_CLARO, "quieto": VERDE_CLARO, "vehiculo": VERDE}
    for j, c in enumerate(CLASES):
        ax.bar(x + (j - 1) * 0.27, df[c], 0.25, color=colores[c], label=ETQ[c])
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(df.index, fontsize=8)
    ax.set_ylabel("Ventanas (escala logarítmica)")
    ax.legend(frameon=False, ncol=3, loc="upper right")
    ax.axvline(1.5, color=GRID, lw=1, ls="--")
    _limpio(ax)
    _guardar(fig, "f01_ventanas-por-clase-fuente.png")


def f02_velocidad():
    h = pd.read_csv(REP / "velocidad_por_clase.csv")
    fuentes = [f for f in ("geolife_prueba", "sumo_normal") if f in set(h["fuente"])]
    fig, ejes = plt.subplots(1, len(fuentes), figsize=(7.5, 3.4), sharey=True)
    ejes = np.atleast_1d(ejes)
    col = {"a_pie": GRIS, "quieto": VERDE_CLARO, "vehiculo": VERDE}
    for ax, f in zip(ejes, fuentes):
        for c in CLASES:
            d = h[(h["fuente"] == f) & (h["clase"] == c)].sort_values("vel_kmh_inicio")
            tot = d["n"].sum()
            if tot:
                ax.step(d["vel_kmh_inicio"], d["n"] / tot * 100, where="post", color=col[c], lw=1.8, label=ETQ[c])
        ax.axvline(8, color=INK, ls="--", lw=1.2)
        ax.text(8.6, ax.get_ylim()[1] * 0.92, "umbral 8 km/h", fontsize=8)
        ax.set_title("GeoLife (usuarios no vistos)" if f == "geolife_prueba" else "SUMO normal (σ = 5 m)", loc="left")
        ax.set_xlabel("Velocidad media de la ventana (km/h; 40 = 40 o más)")
        _limpio(ax)
    ejes[0].set_ylabel("% de ventanas de la clase")
    ejes[0].legend(frameon=False)
    _guardar(fig, "f02_velocidad-por-clase.png")


def f03_importancia():
    d = pd.read_csv(REP / "importancia_permutacion_final.csv").sort_values("importancia_media")
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    ax.barh(d["caracteristica"], d["importancia_media"], xerr=d["importancia_std"], color=VERDE,
            error_kw={"ecolor": INK, "elinewidth": 0.8, "capsize": 2})
    ax.set_xscale("symlog", linthresh=1e-3)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_xlabel("Caída del macro-F1 al permutar la característica (escala simétrica logarítmica)")
    _limpio(ax, "x")
    _guardar(fig, "f03_importancia-permutacion.png")


def f04_matrices():
    g = _metricas()["fuentes"]["geolife_prueba"]
    fig, ejes = plt.subplots(1, 2, figsize=(7.5, 3.5))
    for ax, (clave, titulo, cmap) in zip(ejes, [("umbral", "Umbral", "Greys"), ("rf_final", "Random Forest", "Greens")]):
        cm = np.array(g[clave]["confusion_normalizada"])
        n = np.array(g[clave]["confusion_conteos"])
        ax.imshow(cm, cmap=cmap, vmin=0, vmax=1)
        for i in range(3):
            for j in range(3):
                ax.text(j, i, f"{cm[i, j]:.2f}\n({n[i, j]:,})".replace(",", " "), ha="center", va="center", fontsize=8,
                        color="white" if cm[i, j] > 0.55 else INK)
        ax.set_xticks(range(3), [ETQ[c] for c in CLASES])
        ax.set_yticks(range(3), [ETQ[c] for c in CLASES])
        ax.set_title(f"{titulo} (F1 macro {g[clave]['macro_f1']:.3f})".replace(".", ","), loc="left")
        ax.set_xlabel("Clase predicha")
    ejes[0].set_ylabel("Clase real")
    _guardar(fig, "f04_matrices-confusion.png")


def f05_sigma():
    c = pd.read_csv(REP / "curvas_sigma_final.csv")
    c = c[c["sistema"].isin(["umbral", "rf_final"])]
    fig, ejes = plt.subplots(1, 2, figsize=(7.5, 3.4))
    for sis, col, etq in (("umbral", GRIS, "Umbral"), ("rf_final", VERDE, "Random Forest")):
        d = c[c["sistema"] == sis].sort_values("sigma")
        ejes[0].plot(d["sigma"], d["macro_f1"], marker="o", color=col, lw=2, label=etq)
        ejes[0].fill_between(d["sigma"], d["macro_f1_ic_lo"], d["macro_f1_ic_hi"], color=col, alpha=0.2)
        ejes[1].plot(d["sigma"], d["tasa_veh_apie"] * 100, marker="o", color=col, lw=2, label=etq)
    ejes[0].set_ylabel("F1 macro en SUMO")
    ejes[1].set_ylabel("Vehículos clasificados a pie (%)")
    for ax in ejes:
        ax.set_xlabel("σ del ruido GPS (m; 0 = traza limpia)")
        ax.set_xticks([0, 3, 5, 8, 10, 15])
        _limpio(ax)
    ejes[0].set_ylim(0, 1)
    ejes[0].legend(frameon=False)
    _guardar(fig, "f05_f1-vs-sigma.png")


def f06_trafico_lento():
    t = _metricas()["trafico_lento"]
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    etiquetas = ["F1 de vehículo", "Recall de vehículo\n(velocidad < 8 km/h)"]
    claves = ["f1_vehiculo", "recall_vehiculo_lt_8kmh"]
    x = np.arange(2)
    for j, (sis, col, etq) in enumerate((("umbral", GRIS, "Umbral"), ("rf_final", VERDE, "Random Forest"))):
        vals = [t[sis][k] for k in claves]
        b = ax.bar(x + (j - 0.5) * 0.35, vals, 0.33, color=col, label=etq)
        for r, v in zip(b, vals):
            ax.text(r.get_x() + r.get_width() / 2, v + 0.02, f"{v:.2f}".replace(".", ","), ha="center", fontsize=8)
    ax.set_xticks(x, etiquetas)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Valor")
    ax.legend(frameon=False)
    _limpio(ax)
    _guardar(fig, "f06_trafico-lento.png")


def f07_suavizado():
    fig, ejes = plt.subplots(2, 2, figsize=(7.5, 5.2), sharex=True)
    series = [("rf", "mayoria", "RF", VERDE), ("umbral", "mayoria", "Umbral", GRIS)]
    for col, (arch, titulo) in enumerate([("suavizado_k_final.csv", "Máquina de Freddy"),
                                         ("suavizado_k_final_contrato.csv", "Máquina del contrato §3")]):
        t = pd.read_csv(REP / arch)
        for sis, met, etq, color in series:
            d = t[(t["sistema"] == sis) & (t["metodo"] == met)].sort_values("k")
            lo = d["falsas_100"] - d["falsas_ic95_inf"]
            hi = d["falsas_ic95_sup"] - d["falsas_100"]
            off = -0.15 if sis == "rf" else 0.15
            ejes[0, col].bar(np.arange(3) + off, d["falsas_100"], 0.28, yerr=[lo, hi], color=color, label=etq,
                             error_kw={"ecolor": INK, "elinewidth": 0.8, "capsize": 2})
            ejes[1, col].plot(np.arange(3), d["retardo_mediano_s"], marker="o", color=color, lw=2, label=etq)
        ejes[0, col].set_title(titulo, loc="left")
        ejes[1, col].axhline(60, color=INK, ls="--", lw=1)
        ejes[1, col].set_xticks(range(3), ["k = 1", "k = 3", "k = 5"])
    ejes[0, 0].set_ylabel("Falsas liberaciones\npor 100 sesiones")
    ejes[1, 0].set_ylabel("Retardo mediano\nde cierre (s)")
    ejes[0, 0].legend(frameon=False)
    for ax in ejes.ravel():
        _limpio(ax)
    _guardar(fig, "f07_suavizado-falsas-liberaciones.png")


def _resumen_tyrone():
    """kpis/resultados/final/resumen.csv de origin/tyrone/s4, o None si aún no existe."""
    raiz = AQUI.parents[4]
    for ruta in ("semanas/S4/Tyrone/codigo/kpis/resultados/final/resumen.csv", "proyecto/kpis/resultados/final/resumen.csv"):
        r = subprocess.run(["git", "-C", str(raiz), "show", f"origin/tyrone/s4:{ruta}"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return pd.read_csv(io.StringIO(r.stdout))
    return None


def f08_penetracion():
    df = _resumen_tyrone()
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    if df is None:
        ax.text(0.5, 0.5, "PENDIENTE: corrida final de Tyrone (S4-2)\nkpis/resultados/final/resumen.csv\naún no está en origin/tyrone/s4",
                ha="center", va="center", fontsize=10, transform=ax.transAxes)  # MOCK: reemplazar cuando Tyrone entregue el resumen
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        col_pen = next(c for c in df.columns if "penetr" in c.lower())
        col_val = next(c for c in df.columns if "falsa" in c.lower())
        col_sis = next((c for c in df.columns if c.lower() in ("clasificador", "sistema", "modo")), None)
        for nombre, d in (df.groupby(col_sis) if col_sis else [("", df)]):
            ax.plot(d[col_pen], d[col_val], marker="o", lw=2, color=VERDE if "rf" in str(nombre).lower() else GRIS, label=str(nombre))
        ax.set_xlabel("Penetración de la app")
        ax.set_ylabel("Falsas liberaciones por 100 sesiones")
        ax.legend(frameon=False)
        _limpio(ax)
    _guardar(fig, "f08_falsas-por-penetracion.png")


def main():
    for f in (f01_ventanas, f02_velocidad, f03_importancia, f04_matrices, f05_sigma, f06_trafico_lento, f07_suavizado, f08_penetracion):
        f()


if __name__ == "__main__":
    main()
