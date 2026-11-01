"""Acceso a la librería TraCI de SUMO sin chocar con este paquete, que también se llama `traci`.

`cargar_traci()` importa `$SUMO_HOME/tools/traci` como el módulo `sumo_traci` (sus imports
internos son relativos, así que funciona con otro nombre). `$SUMO_HOME/tools` se añade al
final de `sys.path` para que `sumolib` se encuentre sin tapar a este paquete.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

NOMBRE = "sumo_traci"


def herramientas_sumo() -> Path:
    """Carpeta `tools` de SUMO (requiere la variable SUMO_HOME, como en el contenedor)."""
    sumo_home = os.environ.get("SUMO_HOME")
    if not sumo_home:
        raise RuntimeError("Falta SUMO_HOME: ejecuta esto dentro del contenedor van3twin")
    tools = Path(sumo_home) / "tools"
    if str(tools) not in sys.path:
        sys.path.append(str(tools))
    return tools


def cargar_traci() -> ModuleType:
    """Devuelve la librería TraCI de SUMO (cargada una sola vez como `sumo_traci`)."""
    if NOMBRE in sys.modules:
        return sys.modules[NOMBRE]
    carpeta = herramientas_sumo() / "traci"
    spec = importlib.util.spec_from_file_location(NOMBRE, carpeta / "__init__.py",
                                                  submodule_search_locations=[str(carpeta)])
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[NOMBRE] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def cargar_sumolib() -> ModuleType:
    """Devuelve `sumolib` de SUMO."""
    herramientas_sumo()
    import sumolib  # noqa: WPS433 (import tardío a propósito)

    return sumolib
