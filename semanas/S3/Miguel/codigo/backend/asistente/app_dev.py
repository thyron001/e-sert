"""App FastAPI mínima para probar el asistente sin el backend de Freddy.

    cd semanas/S3/Miguel/codigo
    uvicorn backend.asistente.app_dev:app --host 0.0.0.0 --port 8002

En producción el router lo monta la app principal (backend/api/main.py).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .interprete import _cliente
from .router import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="e-sert asistente (desarrollo)", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api/v1")


@app.get("/api/v1/salud")
def salud() -> dict:
    return {"ok": True, "contrato": 1, "t_sim": None, "ts": datetime.now(timezone.utc).isoformat(),
            "asistente": "llm" if _cliente() is not None else "reglas"}
