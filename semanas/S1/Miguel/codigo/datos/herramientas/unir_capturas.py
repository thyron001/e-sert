"""
Une capturas de teléfono lado a lado, cada una con un rótulo encima (por ejemplo "iOS · Mapa").

    python unir_capturas.py salida.png "iOS · Mapa=ruta/a.png" "Android · Ajustes=ruta/b.png" ...

Todas las capturas se escalan a la misma altura. Requiere Pillow.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ALTO = 1400
MARGEN = 30
ALTO_ROTULO = 90
COLOR_MIGUEL = (0xC6, 0x28, 0x28)


def fuente(tamano: int) -> ImageFont.ImageFont:
    for nombre in ("Arial Bold.ttf", "Arial.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    return ImageFont.load_default(size=tamano)


def unir(salida: Path, capturas: list[tuple[str, Path]]) -> None:
    imagenes = []
    for rotulo, ruta in capturas:
        img = ImageOps.exif_transpose(Image.open(ruta)).convert("RGB")
        ancho = round(img.width * ALTO / img.height)
        imagenes.append((rotulo, img.resize((ancho, ALTO), Image.LANCZOS)))

    ancho_total = sum(img.width for _, img in imagenes) + MARGEN * (len(imagenes) + 1)
    lienzo = Image.new("RGB", (ancho_total, ALTO + ALTO_ROTULO + 2 * MARGEN), "white")
    dibujo = ImageDraw.Draw(lienzo)
    letra = fuente(48)

    x = MARGEN
    for rotulo, img in imagenes:
        caja = dibujo.textbbox((0, 0), rotulo, font=letra)
        dibujo.text((x + (img.width - (caja[2] - caja[0])) / 2, MARGEN), rotulo, fill=COLOR_MIGUEL, font=letra)
        lienzo.paste(img, (x, MARGEN + ALTO_ROTULO))
        dibujo.rectangle(
            (x - 1, MARGEN + ALTO_ROTULO - 1, x + img.width, MARGEN + ALTO_ROTULO + ALTO), outline=(180, 180, 180), width=2
        )
        x += img.width + MARGEN

    salida.parent.mkdir(parents=True, exist_ok=True)
    lienzo.save(salida, dpi=(150, 150))
    print(f"{salida}: {lienzo.width}x{lienzo.height}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    pares = []
    for arg in sys.argv[2:]:
        rotulo, _, ruta = arg.rpartition("=")
        pares.append((rotulo, Path(ruta)))
    unir(Path(sys.argv[1]), pares)
