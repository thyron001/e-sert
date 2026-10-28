"""Exporta el esquema OpenAPI a `backend/openapi.json`.

    python -m backend.api.exportar_openapi [ruta_salida]
"""

from __future__ import annotations

import sys
from pathlib import Path

from .main import openapi_json

SALIDA = Path(__file__).resolve().parents[1] / "openapi.json"


def main(argv=None) -> Path:
    argv = sys.argv[1:] if argv is None else argv
    salida = Path(argv[0]) if argv else SALIDA
    salida.write_text(openapi_json() + "\n", encoding="utf-8")
    print(f"OpenAPI exportado en {salida}")
    return salida


if __name__ == "__main__":
    main()
