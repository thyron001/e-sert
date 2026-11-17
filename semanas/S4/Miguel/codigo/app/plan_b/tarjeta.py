"""Tarjeta de título 1920×1080 para el video del plan B (S4-3). Uso: python tarjeta.py salida.png "Título" "Subtítulo"."""
import sys
from PIL import Image, ImageDraw, ImageFont

ROJO = "#C62828"


def fuente(tam: int):
    for ruta in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(ruta, tam)
        except OSError:
            pass
    return ImageFont.load_default()


def main(salida: str, titulo: str, sub: str) -> None:
    im = Image.new("RGB", (1920, 1080), "#111111")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1920, 18], fill=ROJO)
    for texto, tam, y, color in ((titulo, 96, 400, ROJO), (sub, 44, 560, "white")):
        f = fuente(tam)
        for i, linea in enumerate(texto.split("\\n")):
            w = d.textlength(linea, font=f)
            d.text(((1920 - w) / 2, y + i * (tam + 16)), linea, fill=color, font=f)
    im.save(salida)


if __name__ == "__main__":
    main(*sys.argv[1:4])
