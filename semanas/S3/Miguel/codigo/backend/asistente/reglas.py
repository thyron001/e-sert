"""Intérprete por reglas: la alternativa sin clave, con timeout, error o respuesta inválida del LLM.

Duración con expresiones regulares ("90 min", "2 horas", "media hora", "hora y media", "una
hora") y destino con el mismo emparejador de destinos.py. Si algo falta, queda en None y la app
muestra el formulario.
"""

from __future__ import annotations

import re
from typing import Optional

from .destinos import buscar_en_texto, normalizar
from .modelos import Interpretacion, recortar_duracion

NUMEROS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "diez": 10,
           "quince": 15, "veinte": 20, "treinta": 30, "cuarenta": 40, "cuarenta y cinco": 45, "noventa": 90}
_NUM = r"(\d+(?:[.,]\d+)?|" + "|".join(sorted(map(re.escape, NUMEROS), key=len, reverse=True)) + r")"


def _numero(texto: str) -> float:
    return float(NUMEROS[texto]) if texto in NUMEROS else float(texto.replace(",", "."))


def duracion_en_texto(texto: str) -> Optional[int]:
    """Minutos pedidos en la frase, o None si no hay una duración clara."""
    t = normalizar(texto)
    if re.search(r"\bhoras? y media\b", t):
        horas = re.search(_NUM + r"\s+horas?\s+y\s+media\b", t)
        return int(_numero(horas.group(1)) * 60 + 30) if horas else 90
    if re.search(r"\bmedia hora\b", t):
        return 30
    # Se suman todas las cantidades: "1 hora y 30 minutos" = 90.
    total = 0.0
    for m in re.finditer(_NUM + r"\s*(minutos?|mins?|m|horas?|hrs?|h)\b", t):
        valor, unidad = _numero(m.group(1)), m.group(2)
        total += valor * 60 if unidad.startswith("h") else valor
    return int(round(total)) if total else None


def interpretar_con_reglas(texto: str) -> Interpretacion:
    destino, puntaje = buscar_en_texto(texto)
    minutos, aviso = recortar_duracion(duracion_en_texto(texto))
    encontrados = (destino is not None) + (minutos is not None)
    return Interpretacion(
        destino=destino,
        duracion_min=minutos,
        fuente="reglas",
        confianza=round((puntaje / 100 if destino else 0) * 0.5 + 0.5 * (minutos is not None), 2) if encontrados else 0.0,
        avisos=[aviso] if aviso else [],
    )
