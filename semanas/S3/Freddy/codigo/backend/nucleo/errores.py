"""Errores del núcleo con los códigos del contrato (§4.2)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from comun.esquemas import HTTP_POR_CODIGO, CodigoError, CuerpoError, DetalleError


class ErrorNucleo(Exception):
    """Error de negocio con código del contrato. FastAPI lo convierte en respuesta HTTP."""

    def __init__(self, codigo: CodigoError, mensaje: str, detalle: Optional[Dict[str, Any]] = None):
        super().__init__(f"{codigo.value}: {mensaje}")
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalle = detalle

    @property
    def http(self) -> int:
        """Estado HTTP que le corresponde al código."""
        return HTTP_POR_CODIGO[self.codigo]

    def cuerpo(self) -> CuerpoError:
        """Cuerpo `{"error": {...}}` del contrato."""
        return CuerpoError(error=DetalleError(codigo=self.codigo, mensaje=self.mensaje, detalle=self.detalle))
