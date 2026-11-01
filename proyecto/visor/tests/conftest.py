"""Configuración común de los tests del visor.

Añade a `sys.path` (con rutas relativas a este archivo):
- `semanas/S2/Tyrone/codigo`, para importar `visor`;
- `proyecto` en la raíz del repo, para importar `comun` (el contrato).
"""
import sys
from pathlib import Path

import pytest

DIR_TESTS = Path(__file__).resolve().parent
DIR_VISOR = DIR_TESTS.parent
DIR_CODIGO = DIR_VISOR.parent
# codigo -> Tyrone -> S2 -> semanas -> raíz del repo
DIR_RAIZ = DIR_CODIGO.parents[3]
DIR_PROYECTO = DIR_RAIZ / "proyecto"

# `proyecto/` también tiene un paquete `visor`: `codigo` va primero para que gane esta copia.
for ruta in (DIR_PROYECTO, DIR_CODIGO):
    if str(ruta) in sys.path:
        sys.path.remove(str(ruta))
    sys.path.insert(0, str(ruta))

SNAPSHOTS = DIR_VISOR / "datos" / "snapshots.jsonl"
MUESTRA = DIR_VISOR / "datos" / "snapshots_muestra.jsonl"
INDEX = DIR_VISOR / "index.html"


@pytest.fixture(scope="session")
def ruta_muestra():
    """Muestra versionada de snapshots; sin ella el servidor no tiene qué reproducir."""
    if not MUESTRA.exists():
        pytest.skip(f"no existe {MUESTRA.name}")
    return MUESTRA


@pytest.fixture(scope="session")
def app(ruta_muestra):
    """App del servidor de prueba sobre la muestra, a 1000 mensajes/s para que el test sea rápido."""
    from visor.servidor_prueba import crear_app

    return crear_app(ruta_muestra, velocidad=1000)


@pytest.fixture()
def cliente(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
