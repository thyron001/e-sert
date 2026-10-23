"""Núcleo del backend: billetera, tarifa, sesiones y ocupación, en Python puro y sin HTTP.

El controlador TraCI lo importa directamente en los experimentos; FastAPI (S2) es solo una
capa delgada encima. Compatible con Python 3.10.
"""

import sys
from pathlib import Path

try:  # `comun/` está junto a `backend/` (en proyecto/ y en la copia semanal)
    import comun  # noqa: F401
except ImportError:  # pragma: no cover - depende de cómo se lance el proceso
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
