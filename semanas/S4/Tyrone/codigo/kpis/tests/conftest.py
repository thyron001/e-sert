"""Configuración mínima de pytest para el paquete kpis.

Añade `semanas/S2/Tyrone/codigo` al sys.path para que `import kpis` funcione al
ejecutar `pytest semanas/S2/Tyrone/codigo/kpis/tests` desde la raíz del repo.
"""
import sys
from pathlib import Path

import pytest

CODIGO = Path(__file__).resolve().parents[2]
if str(CODIGO) not in sys.path:
    sys.path.insert(0, str(CODIGO))

DATOS = Path(__file__).resolve().parent / "datos"


@pytest.fixture
def datos():
    """Carpeta con los XML sintéticos de los tests."""
    return DATOS
