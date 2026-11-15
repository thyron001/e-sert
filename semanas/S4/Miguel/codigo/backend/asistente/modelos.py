"""Modelos del asistente (Pydantic) y el recorte de la duración a los límites de la tarifa."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from .destinos import Destino


def _tarifa() -> dict:
    """tarifa.json de comun/ (cobro_minimo_min y tiempo_maximo_min); valores del contrato si no está."""
    for carpeta in Path(__file__).resolve().parents:
        for relativa in ("proyecto/comun/tarifa.json", "comun/tarifa.json"):
            if (carpeta / relativa).exists():
                return json.loads((carpeta / relativa).read_text(encoding="utf-8"))
    return {"cobro_minimo_min": 10, "tiempo_maximo_min": 120}


_T = _tarifa()
MINIMO_MIN = int(_T["cobro_minimo_min"])
MAXIMO_MIN = int(_T["tiempo_maximo_min"])


def recortar_duracion(minutos: Optional[int]) -> Tuple[Optional[int], Optional[str]]:
    """Recorta a [cobro_minimo_min, tiempo_maximo_min] y devuelve el aviso si hubo recorte."""
    if minutos is None:
        return None, None
    if minutos > MAXIMO_MIN:
        return MAXIMO_MIN, f"La duración se recortó de {minutos} a {MAXIMO_MIN} min: es el tope SERT."
    if minutos < MINIMO_MIN:
        return MINIMO_MIN, f"La duración se subió de {minutos} a {MINIMO_MIN} min: es el cobro mínimo."
    return minutos, None


class DestinoSalida(BaseModel):
    nombre: str
    lat: float
    lon: float

    @classmethod
    def de(cls, d: Optional[Destino]) -> Optional["DestinoSalida"]:
        return cls(nombre=d.nombre, lat=d.lat, lon=d.lon) if d else None


class PedidoInterpretar(BaseModel):
    texto: str = Field(..., min_length=1, max_length=300, examples=["cerca de la Catedral Nueva una hora"])


class Interpretacion(BaseModel):
    destino: Optional[Destino] = None
    duracion_min: Optional[int] = None
    fuente: Literal["llm", "reglas"]
    confianza: float = Field(0.0, ge=0, le=1)
    avisos: List[str] = []

    model_config = {"arbitrary_types_allowed": True}

    def salida(self) -> "RespuestaInterpretar":
        return RespuestaInterpretar(
            destino=DestinoSalida.de(self.destino),
            duracion_min=self.duracion_min,
            fuente=self.fuente,
            confianza=self.confianza,
            avisos=self.avisos,
        )


class RespuestaInterpretar(BaseModel):
    """POST /api/v1/asistente/interpretar (mensaje nuevo, pedido a Freddy para el contrato)."""

    destino: Optional[DestinoSalida]
    duracion_min: Optional[int]
    fuente: Literal["llm", "reglas"]
    confianza: float
    avisos: List[str] = []


class IntencionLLM(BaseModel):
    """Lo que devuelve la herramienta registrar_intencion; se valida antes de usarlo."""

    destino: Optional[str] = Field(None, max_length=120)
    duracion_min: Optional[int] = Field(None, ge=0, le=24 * 60)
