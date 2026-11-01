"""Clasificación de movimiento por usuario: buffer de 30 s de GPS y `clasificar` cada 5 s.

Cada usuario (`sim_<vehId>`) tiene su buffer con las muestras del `EmuladorGPS` de S1-3. Cada
5 s, cuando el buffer cubre la ventana completa, se llama a `clasificar(ventana)` de Pablo
(`proyecto/ia/inferencia.py`, contrato §2).

Si el módulo de Pablo no está en el repo, se usa la regla de umbral del contrato (`# MOCK`).
"""

from __future__ import annotations

import math
import sys
from collections import deque
from pathlib import Path
from typing import Callable, Deque, Dict, List, Optional

VENTANA_S = 30.0
PASO_S = 5.0

Clasificador = Callable[[List[dict]], dict]


def buscar_proyecto() -> Optional[Path]:
    """Sube desde este archivo hasta encontrar `proyecto/ia/inferencia.py` (la carpeta `proyecto/`)."""
    for padre in Path(__file__).resolve().parents:
        if (padre / "proyecto" / "ia" / "inferencia.py").is_file():
            return padre / "proyecto"
    return None


def _clasificar_mock(ventana: List[dict]) -> dict:
    # MOCK: reemplazar cuando proyecto/ia/inferencia.py esté disponible en el repo.
    # Regla de umbral del contrato §2 sobre la velocidad media de la ventana (distancia / tiempo).
    recorrido = 0.0
    for a, b in zip(ventana, ventana[1:]):
        recorrido += haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
    dt = ventana[-1]["t"] - ventana[0]["t"]
    vel = recorrido / dt if dt > 0 else 0.0
    if vel > 8.0 / 3.6:
        modo = "vehiculo"
    elif vel < 0.5 / 3.6:
        modo = "quieto"
    else:
        modo = "a_pie"
    return {"modo": modo, "confianza": 1.0, "fuente": "umbral"}


def cargar_clasificar() -> Clasificador:
    """`clasificar` de `proyecto/ia/inferencia.py`, o el MOCK si no está."""
    raiz = buscar_proyecto()
    if raiz is not None:
        if str(raiz) not in sys.path:
            sys.path.append(str(raiz))
        try:
            from ia.inferencia import clasificar
        except ImportError:
            return _clasificar_mock
        return clasificar
    return _clasificar_mock


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    # el redondeo flotante puede dar a = 1 + ε (puntos casi antípodas): se acota a [0, 1]
    a = min(1.0, max(0.0, a))
    return 2 * r * math.asin(math.sqrt(a))


class ClasificadorUsuario:
    """Buffer circular de 30 s por usuario y evaluación cada 5 s."""

    def __init__(self, clasificar: Optional[Clasificador] = None, ventana_s: float = VENTANA_S,
                 paso_s: float = PASO_S):
        self._clasificar = clasificar or cargar_clasificar()
        self.origen = getattr(self._clasificar, "__module__", "")
        self.ventana_s = ventana_s
        self.paso_s = paso_s
        self._buffers: Dict[str, Deque[dict]] = {}
        self._ultima_eval: Dict[str, float] = {}

    def observar(self, usuario: str, fila: dict) -> None:
        """Añade una muestra GPS (fila del `EmuladorGPS`) y descarta lo que sale de la ventana."""
        buf = self._buffers.setdefault(usuario, deque())
        buf.append({"t": fila["t"], "lat": fila["lat"], "lon": fila["lon"],
                    "precision_m": fila["precision_m"]})
        while buf and buf[0]["t"] <= fila["t"] - self.ventana_s:
            buf.popleft()

    def evaluar(self, usuario: str, t: float) -> Optional[dict]:
        """`clasificar` sobre la ventana actual si toca (cada `paso_s`) y hay 30 s de datos."""
        buf = self._buffers.get(usuario)
        if not buf:
            return None
        ultima = self._ultima_eval.get(usuario)
        if ultima is not None and t - ultima < self.paso_s:
            return None
        if buf[-1]["t"] - buf[0]["t"] < self.ventana_s - 1:
            return None
        self._ultima_eval[usuario] = t
        return self._clasificar(list(buf))
