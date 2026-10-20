"""
Convierte la explicación conceptual de una sesión (Markdown) en PDF.

    python herramientas/explicacion_pdf.py S1 Pablo 2

Entrada: semanas/S1/Pablo/explicaciones/s2_explicacion.md
Salida:  semanas/S1/Pablo/explicaciones/s2_explicacion.pdf

Las imágenes con rutas relativas (por ejemplo ../evidencias/s2_x.png) se incrustan.
Requiere: pip install fpdf2 markdown pillow
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import markdown
from fpdf import FPDF

RAIZ = Path(__file__).resolve().parent.parent

COLORES = {
    "Tyrone": (0x1E, 0x63, 0xD6),
    "Freddy": (0xFF, 0x70, 0x43),
    "Pablo": (0x2E, 0x9E, 0x4F),
    "Miguel": (0xC6, 0x28, 0x28),
}


def _latin1(s: str) -> str:
    """Las fuentes estándar del PDF solo cubren latin-1 (sí las tildes y la ñ). Lo demás,
    como los emojis o las flechas, se cambia por un equivalente o se quita."""
    reemplazos = {"→": "->", "←": "<-", "≥": ">=", "≤": "<=", "≈": "~", "×": "x",
                  "—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...",
                  "✓": "[x]", "✔": "[x]", "•": "-", "·": "·"}
    for a, b in reemplazos.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "ignore").decode("latin-1")


class PDF(FPDF):
    def __init__(self, titulo: str, color):
        super().__init__(format="A4")
        self.titulo, self.color = titulo, color
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(16, 16, 16)

    def header(self):
        self.set_fill_color(*self.color)
        self.rect(0, 0, 210, 5, "F")
        self.set_y(8)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(0x5B, 0x6B, 0x7E)
        self.cell(0, 4, self.titulo, align="R")
        self.ln(8)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(0x94, 0xA3, 0xB5)
        self.cell(0, 6, f"e-sert · página {self.page_no()}", align="C")


def _a_html(md_texto: str, base: Path) -> str:
    html = markdown.markdown(md_texto, extensions=["fenced_code", "tables", "sane_lists"])
    # Rutas de imagen relativas -> absolutas
    def abs_img(m):
        ruta = (base / m.group(1)).resolve()
        return f'<img src="{ruta.as_posix()}" width="520"' if ruta.exists() else '<span'
    html = re.sub(r'<img[^>]*src="([^"]+)"', abs_img, html)
    # write_html de fpdf2 no maneja <code> dentro de <pre> con clases: se simplifica
    html = re.sub(r'<pre><code[^>]*>', '<pre>', html).replace('</code></pre>', '</pre>')
    html = re.sub(r'<code>(.*?)</code>', r'<font face="courier">\1</font>', html, flags=re.S)
    return _latin1(html)


def generar(semana: str, persona: str, sesion: int) -> Path:
    carpeta = RAIZ / "semanas" / semana / persona / "explicaciones"
    md_p = carpeta / f"s{sesion}_explicacion.md"
    if not md_p.exists():
        sys.exit(f"No existe {md_p}: escribe primero la explicación en Markdown.")
    color = COLORES.get(persona, (0x1E, 0x54, 0xE0))
    texto = md_p.read_text(encoding="utf-8")

    pdf = PDF(_latin1(f"{semana} · Sesión {sesion} · {persona}"), color)
    pdf.add_page()
    pdf.set_text_color(0x0B, 0x25, 0x40)
    html = _a_html(texto, md_p.parent)
    try:  # fpdf2 >= 2.7.8: títulos con el color de la persona
        from fpdf.fonts import FontFace
        estilos = {
            "h1": FontFace(color=color, size_pt=20, emphasis="B"),
            "h2": FontFace(color=(0x0B, 0x25, 0x40), size_pt=15, emphasis="B"),
            "h3": FontFace(color=(0x1C, 0x3A, 0x58), size_pt=12.5, emphasis="B"),
        }
        pdf.write_html(html, tag_styles=estilos, font_family="Helvetica")
    except TypeError:
        pdf.write_html(html)

    salida = md_p.with_suffix(".pdf")
    pdf.output(str(salida))
    return salida


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("Uso: python herramientas/explicacion_pdf.py S1 Pablo 2")
    print(generar(sys.argv[1].upper(), sys.argv[2].capitalize(), int(sys.argv[3])))
