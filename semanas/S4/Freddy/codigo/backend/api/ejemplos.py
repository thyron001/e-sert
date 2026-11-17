"""Ejemplos de Swagger cargados desde `comun/ejemplos/*.json` (un JSON válido por mensaje)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import comun

CARPETA = Path(comun.__file__).resolve().parent / "ejemplos"


@lru_cache(maxsize=None)
def cargar(nombre: str) -> Any:
    """Contenido de `comun/ejemplos/<nombre>.json`."""
    return json.loads((CARPETA / f"{nombre}.json").read_text(encoding="utf-8"))


def cuerpo(nombre: str, resumen: str) -> Dict[str, Dict[str, Any]]:
    """`openapi_examples` para un `Body(...)`."""
    return {nombre: {"summary": resumen, "value": cargar(nombre)}}


def respuesta(estado: int, nombre: str, descripcion: str = "Respuesta correcta") -> Dict[int, Dict[str, Any]]:
    """Entrada de `responses=` con el ejemplo de la respuesta correcta."""
    return {estado: {"description": descripcion,
                     "content": {"application/json": {"example": cargar(nombre)}}}}


def errores(*codigos: str) -> Dict[int, Dict[str, Any]]:
    """Entradas de `responses=` para los errores posibles, con el cuerpo `{"error": ...}`."""
    from comun.esquemas import HTTP_POR_CODIGO, CodigoError, CuerpoError

    salida: Dict[int, Dict[str, Any]] = {}
    for c in codigos:
        cod = CodigoError(c)
        estado = HTTP_POR_CODIGO[cod]
        ej = {"error": {"codigo": cod.value, "mensaje": "Mensaje legible en español", "detalle": None}}
        entrada = salida.setdefault(estado, {"description": "Error del contrato (§4.2)", "model": CuerpoError,
                                             "content": {"application/json": {"examples": {}}}})
        entrada["content"]["application/json"]["examples"][cod.value] = {"value": ej}
    return salida
