"""Une capturas del teléfono en una tira horizontal (evidencias de la app).

Uso:
    python scripts/montaje.py salida.png cap1.jpeg cap2.jpeg ... [--titulos "Buscar,Guiar,..."]
        [--alto 1200] [--encabezado "Texto arriba"]

Todas las capturas se escalan al mismo alto, se separan con un margen blanco y, si se dan
títulos, cada una lleva el suyo debajo. Solo necesita Pillow (pip install pillow).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MARGEN = 40
ALTO_TITULO = 70
COLOR_FONDO = (255, 255, 255)
COLOR_TEXTO = (33, 33, 33)
COLOR_MIGUEL = (198, 40, 40)  # #C62828, color de Miguel en docs/EQUIPO.md


def fuente(tamano: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Una fuente TrueType común si existe (macOS, Windows, Linux); si no, la de Pillow."""
    for nombre in ("Arial.ttf", "arial.ttf", "DejaVuSans.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    for ruta in (
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if ruta.exists():
            return ImageFont.truetype(str(ruta), tamano)
    return ImageFont.load_default()


def montar(capturas: list[Path], titulos: list[str], alto: int, encabezado: str | None) -> Image.Image:
    imagenes = []
    for ruta in capturas:
        im = Image.open(ruta).convert("RGB")
        imagenes.append(im.resize((round(im.width * alto / im.height), alto), Image.LANCZOS))

    alto_titulo = ALTO_TITULO if titulos else 0
    alto_encabezado = ALTO_TITULO if encabezado else 0
    ancho = sum(im.width for im in imagenes) + MARGEN * (len(imagenes) + 1)
    total = alto + alto_titulo + alto_encabezado + MARGEN * 2
    lienzo = Image.new("RGB", (ancho, total), COLOR_FONDO)
    dibujo = ImageDraw.Draw(lienzo)

    if encabezado:
        dibujo.text((MARGEN, MARGEN // 2), encabezado, fill=COLOR_MIGUEL, font=fuente(44))

    x = MARGEN
    y = MARGEN + alto_encabezado
    letra = fuente(36)
    for i, im in enumerate(imagenes):
        lienzo.paste(im, (x, y))
        dibujo.rectangle((x - 1, y - 1, x + im.width, y + alto), outline=(200, 200, 200))
        if i < len(titulos):
            caja = dibujo.textbbox((0, 0), titulos[i], font=letra)
            dibujo.text(
                (x + (im.width - (caja[2] - caja[0])) / 2, y + alto + 14),
                titulos[i],
                fill=COLOR_TEXTO,
                font=letra,
            )
        x += im.width + MARGEN
    return lienzo


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("salida", type=Path)
    p.add_argument("capturas", type=Path, nargs="+")
    p.add_argument("--titulos", default="", help="separados por comas, en el mismo orden")
    p.add_argument("--alto", type=int, default=1200, help="alto de cada captura en px")
    p.add_argument("--encabezado", default=None)
    args = p.parse_args()

    faltan = [str(c) for c in args.capturas if not c.exists()]
    if faltan:
        raise SystemExit(f"No existen: {', '.join(faltan)}")
    titulos = [t.strip() for t in args.titulos.split(",")] if args.titulos else []

    tira = montar(args.capturas, titulos, args.alto, args.encabezado)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    tira.save(args.salida, dpi=(150, 150), optimize=True)
    print(f"{args.salida}: {tira.width}x{tira.height} px con {len(args.capturas)} capturas")


if __name__ == "__main__":
    main()
