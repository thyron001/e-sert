"""
Genera el PDF semanal de una persona a partir de su estado.json y sus evidencias.

    python herramientas/resumen_pdf.py S1 Pablo

Salida: semanas/S1/Pablo/evidencias/resumen_S1_Pablo.pdf

Una portada con el color de la persona y una página por sesión: título, estado, resumen,
criterios cumplidos, pendientes y sus imágenes de evidencia.
Requiere: pip install fpdf2 pillow
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fpdf import FPDF
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent

COLORES = {
    "Tyrone": (0x1E, 0x63, 0xD6),
    "Freddy": (0xFF, 0x70, 0x43),
    "Pablo": (0x2E, 0x9E, 0x4F),
    "Miguel": (0xC6, 0x28, 0x28),
}
TINTA = (0x0B, 0x25, 0x40)
GRIS = (0x5B, 0x6B, 0x7E)


def _texto(s: str) -> str:
    """fpdf2 con fuentes estándar solo admite latin-1: se reemplaza lo que no entra."""
    return str(s).encode("latin-1", "replace").decode("latin-1")


def _titulo_sesion(carpeta: Path, clave: str) -> str:
    md = carpeta / f"{clave}.md"
    if md.exists():
        for linea in md.read_text(encoding="utf-8").splitlines():
            if linea.startswith("titulo:"):
                return linea.split(":", 1)[1].strip()
    return clave


def generar(semana: str, persona: str) -> Path:
    carpeta = RAIZ / "semanas" / semana / persona
    estado_p = carpeta / "estado.json"
    if not estado_p.exists():
        sys.exit(f"No existe {estado_p}: primero cierra al menos una sesión.")
    estado = json.loads(estado_p.read_text(encoding="utf-8"))
    color = COLORES.get(persona, TINTA)

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    # Portada
    pdf.add_page()
    pdf.set_fill_color(*color)
    pdf.rect(0, 0, 210, 60, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_xy(15, 18)
    pdf.cell(0, 12, _texto(f"e-sert · {semana}"))
    pdf.set_font("Helvetica", "", 16)
    pdf.set_xy(15, 34)
    pdf.cell(0, 10, _texto(f"Resumen semanal de {persona}"))
    pdf.set_text_color(*TINTA)
    pdf.set_xy(15, 75)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Sesiones", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    sesiones = estado.get("sesiones", {})
    for clave in sorted(sesiones):
        s = sesiones[clave]
        crit = s.get("criterios", {})
        linea = (f"- {clave}: {_titulo_sesion(carpeta, clave)} | {s.get('estado', '?')} | "
                 f"{s.get('fecha', '')} | criterios {crit.get('cumplidos', '?')}/{crit.get('total', '?')}")
        pdf.multi_cell(0, 6, _texto(linea), new_x="LMARGIN", new_y="NEXT")

    # Una página por sesión
    for clave in sorted(sesiones):
        s = sesiones[clave]
        pdf.add_page()
        pdf.set_fill_color(*color)
        pdf.rect(0, 0, 210, 6, "F")
        pdf.set_text_color(*TINTA)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_y(14)
        pdf.multi_cell(0, 8, _texto(f"{semana} · {clave} · {_titulo_sesion(carpeta, clave)}"),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*GRIS)
        pdf.cell(0, 6, _texto(f"Estado: {s.get('estado', '?')} · Fecha: {s.get('fecha', '')}"),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TINTA)
        pdf.set_font("Helvetica", "", 11)
        pdf.ln(2)
        pdf.multi_cell(0, 6, _texto(s.get("resumen", "")), new_x="LMARGIN", new_y="NEXT")
        if s.get("pendientes"):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 6, "Pendientes", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            for p in s["pendientes"]:
                pdf.multi_cell(0, 5, _texto(f"- {p}"), new_x="LMARGIN", new_y="NEXT")
        for rel in s.get("evidencias", []):
            img = carpeta / rel
            if not img.exists() or img.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            with Image.open(img) as im:
                ancho, alto = im.size
            w = 180
            h = w * alto / ancho
            if h > 200:
                h, w = 200, 200 * ancho / alto
            if pdf.get_y() + h + 10 > 287:
                pdf.add_page()
            pdf.ln(3)
            pdf.image(str(img), x=(210 - w) / 2, w=w, h=h)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*GRIS)
            pdf.cell(0, 5, _texto(rel), align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TINTA)

    salida = carpeta / "evidencias" / f"resumen_{semana}_{persona}.pdf"
    salida.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(salida))
    return salida


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: python herramientas/resumen_pdf.py S1 Pablo")
    print(generar(sys.argv[1].upper(), sys.argv[2].capitalize()))
