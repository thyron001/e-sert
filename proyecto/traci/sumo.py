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


def cargar_libsumo() -> ModuleType:
    """Devuelve `libsumo` (SUMO enlazado en el proceso, sin socket TraCI; solo sin GUI).

    En el contenedor, el paquete compilado está en `/usr/lib/python3.10/site-packages/libsumo`, fuera
    de `sys.path`; el `$SUMO_HOME/tools/libsumo` que trae `sumo-tools` no tiene el `.so`.
    """
    herramientas_sumo()
    if "libsumo" in sys.modules and hasattr(sys.modules["libsumo"], "simulationStep"):
        return sys.modules["libsumo"]
    sys.modules.pop("libsumo", None)
    for carpeta in (Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
                    Path("/usr/lib") / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"):
        if (carpeta / "libsumo" / "__init__.py").is_file() and str(carpeta) not in sys.path:
            sys.path.insert(0, str(carpeta))
    # `libsumo/__init__.py` hace `from traci import connection, ...`: mientras se importa, `traci`
    # tiene que ser el TraCI de SUMO y no este paquete, que se llama igual.
    nuestro = sys.modules.get("traci")
    sys.modules["traci"] = cargar_traci()
    try:
        import libsumo  # noqa: WPS433
    finally:
        if nuestro is not None:
            sys.modules["traci"] = nuestro
        else:
            sys.modules.pop("traci", None)
    return libsumo
