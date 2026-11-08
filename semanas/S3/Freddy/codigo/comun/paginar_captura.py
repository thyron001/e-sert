"""Parte una captura muy alta (por ejemplo, Swagger con todo desplegado) en trozos que
caben en una página A4.

``explicacion_pdf.py`` incrusta cada imagen con un ancho fijo y no la reparte en varias
páginas, así que una captura alta se corta. Este script la corta por filas en blanco
(entre bloques, para no partir texto) y hace dos cosas:

- ``--trozos``: guarda los trozos como PNG junto a la original (``<nombre>_1.png``, ...),
  para incrustarlos uno tras otro en la explicación.
- ``--pdf``: guarda un PDF A4 con un trozo por página (``<nombre>.pdf``).

Uso (desde ``semanas/S2/Freddy/codigo``)::

    python comun/paginar_captura.py ../evidencias/s1_swagger-rutas.png --trozos
    python comun/paginar_captura.py ../evidencias/s1_swagger.png --pdf

Requiere pillow, numpy y fpdf2. Compatible con Python 3.10.
"""

import argparse
from pathlib import Path

import numpy as np
from fpdf import FPDF
from PIL import Image

# Proporción alto/ancho máxima de un trozo. Con el ancho de 520 pt que usa
# explicacion_pdf.py, 1,1 da unos 570 pt de alto: cabe en una página A4 con su cabecera.
PROPORCION_TROZO = 1.1
# En el PDF propio el trozo ocupa 178 mm de ancho y hasta 255 mm de alto.
PROPORCION_PDF = 255 / 178


def _cortes(img: Image.Image, alto_max: int) -> list[int]:
    """Filas donde cortar: lo más abajo posible sin pasar de ``alto_max`` por trozo,
    eligiendo la fila más uniforme (sin texto) del último tercio del tramo."""
    gris = np.asarray(img.convert("L"), dtype=np.int16)
    variacion = gris.max(axis=1) - gris.min(axis=1)  # 0 = fila de un solo color
    alto = gris.shape[0]
    cortes, inicio = [0], 0
    while alto - inicio > alto_max:
        desde = inicio + alto_max * 2 // 3
        tramo = variacion[desde:inicio + alto_max]
        # La última fila con la menor variación del tramo
        corte = desde + len(tramo) - 1 - int(np.argmin(tramo[::-1]))
        cortes.append(corte)
        inicio = corte
    cortes.append(alto)
    return cortes


def trozos(ruta: Path, proporcion: float) -> list[Image.Image]:
    img = Image.open(ruta).convert("RGB")
    c = _cortes(img, int(img.width * proporcion))
    return [img.crop((0, a, img.width, b)) for a, b in zip(c, c[1:])]


def guardar_trozos(ruta: Path) -> list[Path]:
    salidas = []
    for i, t in enumerate(trozos(ruta, PROPORCION_TROZO), start=1):
        salida = ruta.with_name(f"{ruta.stem}_{i}.png")
        t.save(salida, optimize=True)
        salidas.append(salida)
    return salidas


def guardar_pdf(ruta: Path) -> Path:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(False)
    partes = trozos(ruta, PROPORCION_PDF)
    for i, t in enumerate(partes, start=1):
        pdf.add_page()
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(0x5B, 0x6B, 0x7E)
        pdf.set_xy(16, 8)
        pdf.cell(178, 5, f"{ruta.name} - página {i} de {len(partes)}", align="R")
        pdf.image(t, x=16, y=16, w=178)
    salida = ruta.with_suffix(".pdf")
    pdf.output(str(salida))
    return salida


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("imagen", type=Path)
    p.add_argument("--trozos", action="store_true", help="guarda <nombre>_N.png")
    p.add_argument("--pdf", action="store_true", help="guarda <nombre>.pdf")
    args = p.parse_args()
    if not (args.trozos or args.pdf):
        p.error("indica --trozos, --pdf o ambos")
    if args.trozos:
        for s in guardar_trozos(args.imagen):
            print(s)
    if args.pdf:
        print(guardar_pdf(args.imagen))


if __name__ == "__main__":
    main()
