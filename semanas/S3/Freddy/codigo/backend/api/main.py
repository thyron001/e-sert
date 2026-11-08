"""Aplicación FastAPI de e-sert: `crear_app(config)` y la instancia `app` para uvicorn.

    uvicorn backend.api.main:app --reload --port 8000

Configuración por variables de entorno (`Config`, pydantic-settings). Se aceptan los nombres
de `docs/DESPLIEGUE.md` (`ESERT_*`) y los del prompt de S2-1 / contrato como alias.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from comun import esquemas as e

from . import errores
from .dependencias import Servicios
from .rutas import ROUTERS
from ..espejo.ws_espejo import router as router_ws_espejo
from .ws import router as router_ws

log = logging.getLogger("e-sert.api")

PREFIJO = "/api/v1"
VERSION_APP = "0.2.0"

DESCRIPCION = """
API del backend de **e-sert**, la app de parqueo para la zona SERT del Centro Histórico de
Cuenca. Implementa el **contrato v1** (`docs/CONTRATO.md`).

- Todas las rutas van bajo `/api/v1` y toda respuesta trae `X-Contrato-Version: 1`.
- Si la petición manda otro `X-Contrato-Version`, responde `400 CONTRATO_INCOMPATIBLE`.
- Los errores siguen el formato `{"error": {"codigo", "mensaje", "detalle"}}`.
- Las rutas 🔒 son del controlador TraCI: si el backend tiene `ESERT_TOKEN_SIM`, exigen
  `X-Sim-Token: <token>` o `Authorization: Bearer <token>`.
- WebSocket `ws://<host>/ws/estado?rol=visor|publico`: mensajes `snapshot`, `kpi` y `verdad`
  (este último solo para `rol=visor`).
- WebSocket `ws://<host>/ws/espejo/{veh_id}`: mensajes `espejo` (≤ 1 Hz) de un solo vehículo y
  `espejo_fin` al terminar.
"""

ETIQUETAS = [
    {"name": "sistema", "description": "Salud del servicio y tarifa vigente."},
    {"name": "puestos", "description": "Puestos (`parkingArea`) con la ocupación que estima el sistema."},
    {"name": "guia", "description": "Asignación del puesto libre más cercano al destino."},
    {"name": "eventos", "description": "Ubicación GPS y modo de movimiento de cada usuario."},
    {"name": "sesiones", "description": "Ciclo de vida de la sesión de parqueo y cobro."},
    {"name": "billetera", "description": "Saldo, retenciones y recargas (libro de movimientos)."},
    {"name": "simulacion", "description": "[sim] Entrada del controlador TraCI (rutas 🔒 del contrato)."},
    {"name": "espejo", "description": "Modo espejo: el teléfono sigue a un auto simulado."},
]


def _raiz_repo() -> Optional[Path]:
    for padre in Path(__file__).resolve().parents:
        if (padre / "proyecto").is_dir():
            return padre
    return None


def _visor_por_defecto() -> Optional[str]:
    """`proyecto/visor/` en el repo, o `visor/` junto a `backend/` (imagen Docker)."""
    raiz = _raiz_repo()
    candidatos = [raiz / "proyecto" / "visor"] if raiz else []
    candidatos.append(Path(__file__).resolve().parents[2] / "visor")
    for c in candidatos:
        if c.is_dir():
            return str(c)
    return None


class Config(BaseSettings):
    """Configuración del backend. Todo por entorno; valores por defecto para local."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    db_url: str = Field("sqlite:///./e-sert.db", validation_alias=AliasChoices("ESERT_DB_URL", "E_SERT_DB_URL"))
    puestos_csv: Optional[str] = Field(
        None, validation_alias=AliasChoices("ESERT_PUESTOS_CSV", "E_SERT_PUESTOS_CSV"),
        description="Si falta: proyecto/sumo/parqueos/puestos.csv; si tampoco existe, el mock de 20 puestos.")
    cors: str = Field("*", validation_alias=AliasChoices("ESERT_CORS_ORIGENES", "E_SERT_CORS"))
    token_sim: Optional[str] = Field(None, validation_alias=AliasChoices("ESERT_TOKEN_SIM", "SIM_TOKEN"))
    visor_dir: Optional[str] = Field(default_factory=_visor_por_defecto,
                                     validation_alias=AliasChoices("ESERT_VISOR_DIR"))

    def origenes(self) -> List[str]:
        return [o.strip() for o in self.cors.split(",") if o.strip()] or ["*"]


class MiddlewareContrato:
    """ASGI: exige/añade `X-Contrato-Version` y convierte excepciones sueltas en 500 del contrato.

    Va por fuera de los *exception handlers*, así que también el 500 lleva el header.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        cabecera = (b"x-contrato-version", e.CONTRATO_VERSION.encode())
        pedida = dict(scope.get("headers") or []).get(b"x-contrato-version")
        if pedida is not None and pedida.decode("latin-1").strip() != e.CONTRATO_VERSION:
            resp = errores.respuesta_error(e.CodigoError.CONTRATO_INCOMPATIBLE,
                                           f"Este backend implementa el contrato v{e.CONTRATO_VERSION}.",
                                           {"recibida": pedida.decode("latin-1")})
            resp.headers["X-Contrato-Version"] = e.CONTRATO_VERSION
            return await resp(scope, receive, send)
        iniciada = False

        async def enviar(mensaje):
            nonlocal iniciada
            if mensaje["type"] == "http.response.start":
                iniciada = True
                mensaje.setdefault("headers", [])
                mensaje["headers"] = [*mensaje["headers"], cabecera]
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        except Exception as exc:
            if iniciada:
                raise
            await errores.error_interno(exc)(scope, receive, enviar)


def _montar_pagos(app: FastAPI) -> bool:
    """Monta el router de Miguel (`backend/pagos/rutas.py`, variable `router`) si existe."""
    try:
        from ..pagos.rutas import router as router_pagos  # type: ignore[import-not-found]
    except ImportError:
        return False
    app.include_router(router_pagos, prefix=PREFIJO)
    return True


def crear_app(config: Optional[Config] = None) -> FastAPI:
    """Fábrica de la app. Los tests pasan `Config(db_url="sqlite:///:memory:")`."""
    config = config or Config()

    @asynccontextmanager
    async def ciclo(app: FastAPI):
        app.state.servicios.gestor.iniciar()
        yield
        await app.state.servicios.gestor.detener()

    app = FastAPI(title="e-sert API", version=e.CONTRATO_VERSION, description=DESCRIPCION,
                  openapi_tags=ETIQUETAS, lifespan=ciclo)
    app.state.config = config
    app.state.servicios = Servicios.armar(config.db_url, config.puestos_csv, config.token_sim)

    errores.registrar(app)
    for r in ROUTERS:
        app.include_router(r, prefix=PREFIJO)
    app.include_router(router_ws)
    app.include_router(router_ws_espejo)

    # Healthcheck de Dokploy en la raíz (DESPLIEGUE.md); mismo cuerpo que /api/v1/salud.
    @app.get("/salud", response_model=e.Salud, tags=["sistema"], summary="Healthcheck (raíz)",
             responses={200: {"description": "Servicio vivo", "content": {"application/json": {
                 "example": {"ok": True, "contrato": 1, "t_sim": None}}}}})
    def salud_raiz() -> e.Salud:
        return app.state.servicios.mundo.salud()

    app.state.pagos_montado = _montar_pagos(app)
    if config.visor_dir and Path(config.visor_dir).is_dir() and any(Path(config.visor_dir).iterdir()):
        app.mount("/visor", StaticFiles(directory=config.visor_dir, html=True), name="visor")

    app.add_middleware(CORSMiddleware, allow_origins=config.origenes(), allow_methods=["*"],
                       allow_headers=["*"], expose_headers=["X-Contrato-Version"])
    app.add_middleware(MiddlewareContrato)
    log.info("e-sert API v%s · BD %s · %d puestos · pagos %s", VERSION_APP, config.db_url,
             len(app.state.servicios.mapa.puestos), "sí" if app.state.pagos_montado else "no")
    return app


def openapi_json(app: Optional[FastAPI] = None) -> str:
    """El esquema OpenAPI como texto JSON (lo usa `exportar_openapi`)."""
    app = app or crear_app(Config(db_url="sqlite:///:memory:"))
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2)


_app: Optional[FastAPI] = None


def __getattr__(nombre: str):
    """`backend.api.main.app` se crea al pedirlo (uvicorn), no al importar: así los tests no
    abren la base por defecto `./e-sert.db`."""
    global _app
    if nombre == "app":
        if _app is None:
            _app = crear_app()
        return _app
    raise AttributeError(nombre)
