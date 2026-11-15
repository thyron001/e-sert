"""
Miniaturas del PDF del informe con PyMuPDF -> evidencias/s3_informe-paginas.png (portada, índice, una página de
resultados y una de IA).

    python3 informe/miniaturas_pdf.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz

AQUI = Path(__file__).resolve().parent
PDF = AQUI / "salida" / "informe_e-sert.pdf"
SALIDA = AQUI.parents[1] / "evidencias" / "s3_informe-paginas.png"


def buscar(doc, claves, desde=0):
    for i in range(desde, len(doc)):
        t = doc[i].get_text().lower()
        if any(c.lower() in t for c in claves):
            return i
    return 0


def main():
    doc = fitz.open(PDF)
    paginas = [("Portada", 0),
               ("Índice", buscar(doc, ["índice", "indice", "tabla de contenido"])),
               ("Resultados", buscar(doc, ["reúne en una sola tabla"], 2)),
               ("Inteligencia artificial", buscar(doc, ["cobra el parqueo por el tiempo real"], 2))]
    fig, ejes = plt.subplots(1, 4, figsize=(16, 6.2))
    tmp = Path("/tmp/claude-1000/miniaturas")
    tmp.mkdir(parents=True, exist_ok=True)
    for ax, (titulo, i) in zip(ejes, paginas):
        pix = doc[i].get_pixmap(dpi=70)
        ruta = tmp / f"p{i}.png"
        pix.save(ruta)
        ax.imshow(mpimg.imread(ruta))
        ax.set_title(f"{titulo} (pág. {i + 1} de {len(doc)})", fontsize=10)
        ax.axis("off")
    fig.tight_layout()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(SALIDA, dpi=150)
    print("->", SALIDA, [p[1] + 1 for p in paginas])


if __name__ == "__main__":
    main()
