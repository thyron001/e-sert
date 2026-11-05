"""Traducción de errores al formato del contrato (§4.2): `{"error": {codigo, mensaje, detalle}}`."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from comun.esquemas import HTTP_POR_CODIGO, CodigoError, CuerpoError, DetalleError

from ..nucleo.errores import ErrorNucleo

log = logging.getLogger("e-sert.api")


def respuesta_error(codigo: CodigoError, mensaje: str, detalle: Optional[Dict[str, Any]] = None) -> JSONResponse:
    """Respuesta JSON con el cuerpo de error del contrato y su estado HTTP."""
    cuerpo = CuerpoError(error=DetalleError(codigo=codigo, mensaje=mensaje, detalle=detalle))
    return JSONResponse(cuerpo.a_json(), status_code=HTTP_POR_CODIGO[codigo])


async def _error_nucleo(_: Request, exc: ErrorNucleo) -> JSONResponse:
    return respuesta_error(exc.codigo, exc.mensaje, exc.detalle)


async def _error_validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
    errores = [{k: v for k, v in err.items() if k in ("loc", "msg", "type")} for err in exc.errors()]
    return respuesta_error(CodigoError.VALIDACION, "Los datos enviados no cumplen el contrato.",
                           {"errores": jsonable_encoder(errores)})


async def _error_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """404/405 de rutas o métodos inexistentes. El contrato no tiene código propio (se propone
    `RUTA_NO_EXISTE`): se usa `VALIDACION` con el estado HTTP real."""
    cuerpo = CuerpoError(error=DetalleError(codigo=CodigoError.VALIDACION, mensaje=f"Ruta o método no válido: {exc.detail}",
                                            detalle={"http": exc.status_code}))
    return JSONResponse(cuerpo.a_json(), status_code=exc.status_code, headers=getattr(exc, "headers", None))


def error_interno(exc: BaseException) -> JSONResponse:
    """500 con el formato del contrato. Lo usa el middleware, que envuelve toda la app."""
    log.exception("Error no controlado", exc_info=exc)
    return respuesta_error(CodigoError.ERROR_INTERNO, "Error interno del servidor.")


def registrar(app: FastAPI) -> None:
    """Registra los *exception handlers* en la app."""
    app.add_exception_handler(ErrorNucleo, _error_nucleo)
    app.add_exception_handler(RequestValidationError, _error_validacion)
    app.add_exception_handler(StarletteHTTPException, _error_http)
