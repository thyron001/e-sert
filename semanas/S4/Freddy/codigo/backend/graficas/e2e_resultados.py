"""Gráfica de la suite e2e (S4-1): una barra horizontal por test con su duración, leída del JUnit XML.

Verde = pasa, rojo = falla, gris = omitido; el estado también va escrito junto a cada barra, para
no depender solo del color. En el título: total de tests y tiempo.

    python -m backend.graficas.e2e_resultados e2e.xml s1_e2e-resultados.png [--titulo "..."]
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLOR = {"pasa": "#0ca30c", "falla": "#d03b3b", "omitido": "#a8a79f"}
TINTA, TINTA_2, REJILLA, EJE = "#0b0b0b", "#5f5e58", "#e1e0d9", "#c3c2b7"


def leer_junit(ruta: Path) -> Tuple[List[dict], float]:
    """Casos (`nombre`, `archivo`, `segundos`, `estado`, `motivo`) y tiempo total de la corrida."""
    raiz = ET.parse(ruta).getroot()
    suites = [raiz] if raiz.tag == "testsuite" else raiz.findall("testsuite")
    casos, total = [], 0.0
    for suite in suites:
        total += float(suite.get("time", 0))
        for caso in suite.iter("testcase"):
            estado, motivo = "pasa", ""
            for etiqueta, nombre in (("failure", "falla"), ("error", "falla"), ("skipped", "omitido")):
                hijo = caso.find(etiqueta)
                if hijo is not None:
                    estado, motivo = nombre, (hijo.get("message") or "").splitlines()[0].split(": The command")[0][:60]
                    break
            casos.append({"nombre": caso.get("name"), "archivo": caso.get("classname", "").split(".")[-1],
                          "segundos": float(caso.get("time", 0)), "estado": estado, "motivo": motivo})
    return casos, total


def agrupar(casos: List[dict]) -> List[dict]:
    """Une los casos parametrizados (`test[0]`, `test[1]`…) en una barra `test [×N]`."""
    peor = {"falla": 2, "omitido": 1, "pasa": 0}
    grupos: dict = {}
    for c in casos:
        clave = (c["archivo"], c["nombre"].split("[")[0])
        g = grupos.setdefault(clave, {**c, "nombre": clave[1], "segundos": 0.0, "n": 0})
        g["segundos"] += c["segundos"]
        g["n"] += 1
        if peor[c["estado"]] > peor[g["estado"]]:
            g["estado"], g["motivo"] = c["estado"], c["motivo"]
    for g in grupos.values():
        if g["n"] > 1:
            g["nombre"] += f" [×{g['n']}]"
    return list(grupos.values())


def graficar(casos: List[dict], total_s: float, salida: Path, titulo: str = "pytest -m e2e") -> Path:
    cuenta = {k: sum(c["estado"] == k for c in casos) for k in COLOR}
    n_total = len(casos)
    casos = sorted(agrupar(casos), key=lambda c: (c["archivo"], c["nombre"]))
    n = len(casos)
    fig, ax = plt.subplots(figsize=(11, 0.4 * n + 1.6))
    fig.patch.set_facecolor("white")
    y = list(range(n))[::-1]
    ancho = [max(c["segundos"], 0.005) for c in casos]
    ax.barh(y, ancho, height=0.62, color=[COLOR[c["estado"]] for c in casos], edgecolor="white", linewidth=1)
    tope = max(ancho) if ancho else 1
    for yi, c, w in zip(y, casos, ancho):
        texto = f"{c['segundos']:.2f} s · {c['estado']}" + (f" ({c['motivo']})" if c["estado"] != "pasa" else "")
        ax.text(w + tope * 0.01, yi, texto, va="center", fontsize=7.5, color=TINTA_2)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{c['archivo']}::{c['nombre']}"[:78] for c in casos], fontsize=7.5, color=TINTA)
    ax.set_xlim(0, tope * 1.9)
    ax.set_xlabel("duración (s)", color=TINTA_2)
    ax.grid(axis="x", color=REJILLA, linewidth=0.6)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(EJE)
    ax.tick_params(colors=TINTA_2, length=0)
    ax.set_title(f"{titulo}: {n_total} tests · {cuenta['pasa']} pasan · {cuenta['falla']} fallan · "
                 f"{cuenta['omitido']} omitidos · {total_s:.1f} s en total",
                 loc="left", fontsize=11, color=TINTA)
    fig.tight_layout()
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    return salida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("junit", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--titulo", default="pytest -m e2e")
    args = ap.parse_args()
    casos, total = leer_junit(args.junit)
    print(graficar(casos, total, args.salida, args.titulo))


if __name__ == "__main__":
    main()
