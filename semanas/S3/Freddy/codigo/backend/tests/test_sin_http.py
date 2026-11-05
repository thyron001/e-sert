"""El núcleo no importa FastAPI ni nada HTTP (criterio de "hecho")."""

import ast
from pathlib import Path

PROHIBIDOS = {"fastapi", "starlette", "uvicorn", "httpx", "requests", "aiohttp", "http", "urllib", "websockets"}
NUCLEO = Path(__file__).resolve().parents[1] / "nucleo"


def test_nucleo_sin_http():
    for archivo in NUCLEO.glob("*.py"):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                modulos = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0:
                modulos = [nodo.module or ""]
            else:
                continue
            for m in modulos:
                assert m.split(".")[0] not in PROHIBIDOS, f"{archivo.name} importa {m}"
