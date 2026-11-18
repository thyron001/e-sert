"""Servicio `sim` de Dokploy: SUMO + controlador TraCI (+ sumo-gui por noVNC) en su propio contenedor.

El backend (`api`) no corre SUMO: cuando el visor pulsa «Iniciar», `/api/v1/demo/iniciar` del
backend llama a este servicio por la red interna de Dokploy (`ESERT_URL_SIM`), y el controlador
publica los pasos de vuelta en el backend (`ESERT_URL_BACKEND`) con `ESERT_TOKEN_SIM`.

    uvicorn backend.simulador.servicio:app --host 0.0.0.0 --port 8100

Rutas (todas menos `/salud` exigen `Authorization: Bearer <ESERT_TOKEN_SIM>`):
- `GET  /salud`
- `GET  /estado`
- `POST /iniciar`  cuerpo: `{penetracion, semilla, ritmo, hasta_s, clasificador}`
- `POST /detener`
"""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import Body, Depends, FastAPI, Header, HTTPException

from .gestor import Escenario, GestorSimulacion, estado_a_dict


def crear_app(gestor: Optional[GestorSimulacion] = None, token: Optional[str] = None) -> FastAPI:
    token = token if token is not None else os.environ.get("ESERT_TOKEN_SIM")
    g = gestor or GestorSimulacion(os.environ.get("ESERT_URL_BACKEND", "http://127.0.0.1:8000"), token)
    app = FastAPI(title="e-sert · servicio de simulación", version="1")
    app.state.gestor = g

    def exigir_token(authorization: Optional[str] = Header(None)) -> None:
        if not token:
            raise HTTPException(503, "el servicio no tiene ESERT_TOKEN_SIM")
        recibido = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else ""
        if not hmac.compare_digest(recibido.encode(), token.encode()):
            raise HTTPException(401, "token incorrecto")

    @app.get("/salud")
    def salud() -> dict:
        return {"ok": True, "pantalla": g.pantalla()}

    @app.get("/estado", dependencies=[Depends(exigir_token)])
    def estado() -> dict:
        return estado_a_dict(g.estado())

    @app.post("/iniciar", status_code=202, dependencies=[Depends(exigir_token)])
    def iniciar(params: dict = Body(default_factory=dict)) -> dict:
        validos = {"penetracion", "semilla", "ritmo", "hasta_s", "clasificador"}
        if set(params) - validos:
            raise HTTPException(422, f"parámetros desconocidos: {sorted(set(params) - validos)}")
        try:
            esc = Escenario(**params)
        except TypeError as exc:
            raise HTTPException(422, str(exc)) from exc
        try:
            g.iniciar(esc)
        except LookupError as exc:
            raise HTTPException(503, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return estado_a_dict(g.estado())

    @app.post("/clasificar", dependencies=[Depends(exigir_token)])
    def clasificar(cuerpo: dict = Body(...)) -> dict:
        muestras = cuerpo.get("muestras") or []
        if not isinstance(muestras, list) or not muestras:
            raise HTTPException(422, "faltan muestras")
        try:
            return g.clasificar(muestras)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(422, f"muestras inválidas: {exc}") from exc

    @app.post("/detener", dependencies=[Depends(exigir_token)])
    def detener() -> dict:
        return estado_a_dict(g.detener())

    @app.on_event("shutdown")
    def apagar() -> None:
        if g.corriendo():
            g.detener()

    return app


def __getattr__(nombre: str):
    """`backend.simulador.servicio.app` se crea al pedirlo (uvicorn), no al importar."""
    if nombre == "app":
        global app
        app = crear_app()
        return app
    raise AttributeError(nombre)
