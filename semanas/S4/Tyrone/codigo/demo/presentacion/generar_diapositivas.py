"""Genera `diapositivas.md` (Marp) desde `diapositivas.plantilla.md` y `resumen.csv` (S4-3).

    demo/.venv/bin/python demo/presentacion/generar_diapositivas.py            # escribe diapositivas.md
    demo/.venv/bin/python demo/presentacion/generar_diapositivas.py --verificar # 0 si coincide con resumen.csv
    # el mismo motor arma el informe (S4-2):
    demo/.venv/bin/python demo/presentacion/generar_diapositivas.py --plantilla informe/tyrone.plantilla.md --salida informe/tyrone.md

Ninguna cifra se escribe a mano: en la plantilla cada número es un marcador
`{{escenario.columna|decimales}}` (con `|abs`, `|pct` o `|sig` al final: valor absoluto, fracción → %, o signo + explícito) que se lee de
`kpis/resultados/final/resumen.csv`. Con `--verificar` se vuelve a renderizar y se compara con el
`diapositivas.md` guardado; también lista cada marcador con su valor (`cifras.json`).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parent.parent
RESUMEN = CODIGO / "kpis" / "resultados" / "final" / "resumen.csv"
PLANTILLA = AQUI / "diapositivas.plantilla.md"
SALIDA = AQUI / "diapositivas.md"
CIFRAS = AQUI / "cifras.json"
MARCADOR = re.compile(r"\{\{([a-z0-9_]+)\.([a-z0-9_]+)\|(\d)(\|abs|\|pct|\|sig)?\}\}")
# `{{tabla:Título}}`: la tabla Markdown que sigue al `## Título` de `resumen.md`
TABLA = re.compile(r"\{\{tabla:([^}]+)\}\}")
# `{{seccion:Título}}`: todo el bloque bajo `## Título` de `resumen.md` (hasta el siguiente `## `)
SECCION = re.compile(r"\{\{seccion:([^}]+)\}\}")
RESUMEN_MD = RESUMEN.with_suffix(".md")


def tabla_de(resumen_md: str, titulo: str) -> str:
    bloque = resumen_md.split(f"## {titulo}\n", 1)
    if len(bloque) < 2:
        raise KeyError(f"resumen.md no tiene la sección {titulo!r}")
    lineas = [l for l in bloque[1].strip().splitlines()]
    tabla = []
    for l in lineas:
        if l.startswith("|"):
            tabla.append(l)
        elif tabla:
            break
    return "\n".join(tabla)


def seccion_de(resumen_md: str, titulo: str) -> str:
    bloque = resumen_md.split(f"## {titulo}\n", 1)
    if len(bloque) < 2:
        raise KeyError(f"resumen.md no tiene la sección {titulo!r}")
    return bloque[1].split("\n## ", 1)[0].strip()


def leer_resumen(ruta: Path = RESUMEN) -> dict:
    with open(ruta, encoding="utf-8", newline="") as f:
        return {fila["escenario"]: fila for fila in csv.DictReader(f)}


def formato(valor: float, dec: int) -> str:
    """Coma decimal y espacio fino como separador de miles (estilo del informe)."""
    texto = f"{valor:,.{dec}f}".replace(",", " ").replace(".", ",")
    return texto.replace("-", "−")


def renderizar(plantilla: str, res: dict) -> tuple[str, list]:
    usadas = []

    def sustituir(m):
        esc, col, dec, mod = m.group(1), m.group(2), int(m.group(3)), m.group(4) or ""
        if esc not in res or col not in res[esc]:
            raise KeyError(f"marcador sin dato: {esc}.{col}")
        bruto = res[esc][col]
        valor = float(bruto)
        if math.isnan(valor):
            raise ValueError(f"marcador NaN: {esc}.{col}")
        if mod == "|abs":
            valor = abs(valor)
        elif mod == "|pct":  # fracción → porcentaje
            valor = 100 * valor
        texto = formato(valor, dec)
        if mod == "|sig" and valor > 0 and texto.strip("0,") != "":
            texto = "+" + texto
        usadas.append({"marcador": m.group(0), "escenario": esc, "columna": col, "csv": bruto, "texto": texto})
        return texto

    texto = MARCADOR.sub(sustituir, plantilla)
    if TABLA.search(texto) or SECCION.search(texto):
        md = RESUMEN_MD.read_text(encoding="utf-8")
        texto = TABLA.sub(lambda m: tabla_de(md, m.group(1).strip()), texto)
        texto = SECCION.sub(lambda m: seccion_de(md, m.group(1).strip()), texto)
    return texto, usadas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--resumen", type=Path, default=RESUMEN)
    ap.add_argument("--plantilla", type=Path, default=PLANTILLA, help="relativa a codigo/ o absoluta")
    ap.add_argument("--salida", type=Path, default=SALIDA, help="relativa a codigo/ o absoluta")
    args = ap.parse_args(argv)
    plantilla = args.plantilla if args.plantilla.is_absolute() else CODIGO / args.plantilla
    salida = args.salida if args.salida.is_absolute() else CODIGO / args.salida
    if args.plantilla == PLANTILLA:
        plantilla, salida = PLANTILLA, (SALIDA if args.salida == SALIDA else salida)
    cifras = CIFRAS if salida == SALIDA else salida.with_suffix(".cifras.json")
    texto, usadas = renderizar(plantilla.read_text(encoding="utf-8"), leer_resumen(args.resumen))
    if args.verificar:
        guardado = salida.read_text(encoding="utf-8") if salida.exists() else ""
        ok = guardado == texto
        sueltos = [n for n in re.findall(r"\{\{[^}]*\}\}", guardado)]
        print(f"{len(usadas)} cifras desde {args.resumen.name}; {salida.name} "
              f"{'coincide' if ok else 'NO coincide'}; marcadores sin resolver: {len(sueltos)}")
        return 0 if ok and not sueltos else 1
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(texto, encoding="utf-8")
    cifras.write_text(json.dumps(usadas, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{salida.name}: {len(usadas)} cifras desde {args.resumen}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
