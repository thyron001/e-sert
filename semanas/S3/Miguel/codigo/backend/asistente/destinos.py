"""Destinos conocidos (destinos.csv de Tyrone, S1-3) y su búsqueda por nombre o alias.

El asistente nunca inventa destinos: solo devuelve uno de esta lista. La comparación es
difusa (rapidfuzz, puntaje >= 80; si no está instalado, difflib) sobre el texto normalizado
(minúsculas y sin tildes), para tolerar "calderon", "mercado diez de agosto", etc.
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

UMBRAL = 80

try:  # pragma: no cover - depende del entorno
    from rapidfuzz import fuzz

    def _parecido(a: str, b: str) -> float:
        return float(fuzz.ratio(a, b))

except ImportError:  # pragma: no cover
    import difflib

    def _parecido(a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio() * 100


@dataclass(frozen=True)
class Destino:
    nombre: str
    lat: float
    lon: float


# Formas habituales de nombrar cada destino (normalizadas al compararse).
ALIAS: Dict[str, str] = {
    "la catedral": "Catedral Nueva",
    "catedral": "Catedral Nueva",
    "catedral de la inmaculada": "Catedral Nueva",
    "el parque": "Parque Calderón",
    "parque central": "Parque Calderón",
    "calderon": "Parque Calderón",
    "abdon calderon": "Parque Calderón",
    "mercado 10": "Mercado 10 de Agosto",
    "diez de agosto": "Mercado 10 de Agosto",
    "mercado diez de agosto": "Mercado 10 de Agosto",
    "nueve de octubre": "Mercado 9 de Octubre",
    "mercado nueve de octubre": "Mercado 9 de Octubre",
    "9 de octubre": "Mercado 9 de Octubre",
    "san francisco": "Plaza San Francisco",
    "municipio": "Municipio (Bolívar y Borrero)",
    "alcaldia": "Municipio (Bolívar y Borrero)",
    "las flores": "Plaza de las Flores",
    "pumapungo": "Museo Pumapungo",
    "otorongo": "Plaza del Otorongo",
    "santo domingo": "Santo Domingo",
    "san sebastian": "San Sebastián",
    "el banco": "Banco en la Gran Colombia",
    "banco": "Banco en la Gran Colombia",
}


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni signos, espacios simples."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", sin_tildes.lower())).strip()


def ruta_destinos() -> Path:
    """ESERT_DESTINOS_CSV, o el primer `proyecto/sumo/demanda/destinos.csv` (o `sumo/...`) hacia arriba."""
    if os.environ.get("ESERT_DESTINOS_CSV"):
        return Path(os.environ["ESERT_DESTINOS_CSV"])
    for carpeta in Path(__file__).resolve().parents:
        for relativa in ("proyecto/sumo/demanda/destinos.csv", "sumo/demanda/destinos.csv"):
            if (carpeta / relativa).exists():
                return carpeta / relativa
    raise FileNotFoundError("No se encontró destinos.csv; define ESERT_DESTINOS_CSV")


@lru_cache(maxsize=1)
def cargar_destinos(ruta: Optional[str] = None) -> Tuple[Destino, ...]:
    with Path(ruta or ruta_destinos()).open(encoding="utf-8") as f:
        return tuple(Destino(r["nombre"], float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f))


def _formas() -> List[Tuple[str, Destino]]:
    """Pares (forma normalizada, destino): el nombre oficial y sus alias."""
    por_nombre = {d.nombre: d for d in cargar_destinos()}
    formas = [(normalizar(d.nombre), d) for d in por_nombre.values()]
    formas += [(normalizar(a), por_nombre[n]) for a, n in ALIAS.items() if n in por_nombre]
    return formas


def resolver(nombre: Optional[str]) -> Tuple[Optional[Destino], float]:
    """Nombre (del LLM o del usuario) → destino conocido y puntaje 0–100; (None, 0) si no alcanza 80."""
    if not nombre or not nombre.strip():
        return None, 0.0
    buscado = normalizar(nombre)
    mejor: Tuple[Optional[Destino], float] = (None, 0.0)
    for forma, destino in _formas():
        puntaje = 100.0 if forma == buscado else _parecido(forma, buscado)
        if puntaje > mejor[1]:
            mejor = (destino, puntaje)
    return mejor if mejor[1] >= UMBRAL else (None, mejor[1])


def buscar_en_texto(texto: str) -> Tuple[Optional[Destino], float]:
    """Busca un destino mencionado dentro de una frase libre (intérprete por reglas).

    Compara cada nombre o alias con ventanas de la frase del mismo número de palabras, para
    no confundir palabras sueltas ("hola", "la") con un destino.
    """
    palabras = normalizar(texto).split()
    mejor: Tuple[Optional[Destino], float] = (None, 0.0)
    for forma, destino in _formas():
        n = len(forma.split())
        if n == 0 or n > len(palabras):
            continue
        for i in range(len(palabras) - n + 1):
            ventana = " ".join(palabras[i : i + n])
            # Las formas de una sola palabra corta piden coincidencia casi exacta.
            umbral = 92 if n == 1 and len(forma) <= 6 else UMBRAL
            puntaje = 100.0 if ventana == forma else _parecido(ventana, forma)
            # Más palabras coincidiendo = mención más específica ("mercado 10 de agosto" > "mercado 10").
            clave = puntaje + n * 0.01
            if puntaje >= umbral and clave > mejor[1]:
                mejor = (destino, clave)
    return (mejor[0], min(100.0, round(mejor[1], 1))) if mejor[0] else (None, 0.0)
