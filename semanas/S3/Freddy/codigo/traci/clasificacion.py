"""Clasificación de movimiento por usuario: buffer de 30 s de GPS y `clasificar` cada 5 s.

Cada usuario (`sim_<vehId>`) tiene su buffer con las muestras del `EmuladorGPS` de S1-3. Cada
5 s se clasifica la ventana de los últimos 30 s con la inferencia de Pablo (contrato §2):

- S3-2: si existe `traci/escenario/pablo/ia` (copia de `origin/pablo/s3`, con
  `python traci/obtener_escenario.py --ia`), se usa esa: `clasificar(ventana, previo)` robusto a
  huecos y `clasificar_lote(ventanas, previos)` para todos los usuarios del paso en una llamada.
- Si no, `proyecto/ia/inferencia.py`, y si tampoco está, la regla de umbral del contrato (`# MOCK`).

Cada resultado lleva además `n_muestras` y `cobertura` (muestras / esperadas en la ventana), que
la máquina de estados usa para no decidir con datos pobres.
"""

from __future__ import annotations

import inspect
import math
import os
import sys
from collections import deque
from pathlib import Path
from typing import Callable, Deque, Dict, Iterable, List, Optional, Tuple

VENTANA_S = 30.0
PASO_S = 5.0
TASA_HZ = 1.0

Clasificador = Callable[..., dict]
ClasificadorLote = Callable[..., List[dict]]
SIN_DATOS = {"modo": "sin_datos", "confianza": 0.0, "fuente": "sin_datos"}


def buscar_proyecto() -> Optional[Path]:
    """Sube desde este archivo hasta encontrar `proyecto/ia/inferencia.py` (la carpeta `proyecto/`)."""
    for padre in Path(__file__).resolve().parents:
        if (padre / "proyecto" / "ia" / "inferencia.py").is_file():
            return padre / "proyecto"
    return None


def buscar_ia() -> Optional[Path]:
    """Carpeta que contiene el paquete `ia`: `$ESERT_IA_DIR`, la copia de Pablo S3 o `proyecto/`."""
    candidatas = [os.environ.get("ESERT_IA_DIR"), Path(__file__).resolve().parent / "escenario" / "pablo",
                  buscar_proyecto()]
    for c in candidatas:
        if c and (Path(c) / "ia" / "inferencia.py").is_file():
            return Path(c)
    return None


def _clasificar_mock(ventana: List[dict], previo: Optional[dict] = None) -> dict:
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


def _lote_desde(clasificar: Clasificador) -> ClasificadorLote:
    # MOCK: reemplazar cuando Pablo entregue clasificar_lote (S3-1). Llama a `clasificar` una por una.
    acepta_previo = len(inspect.signature(clasificar).parameters) > 1

    def lote(ventanas: List[List[dict]], previos: Optional[List[Optional[dict]]] = None) -> List[dict]:
        previos = previos or [None] * len(ventanas)
        if acepta_previo:
            return [clasificar(v, p) for v, p in zip(ventanas, previos)]
        return [clasificar(v) for v in ventanas]
    lote.__module__ = getattr(clasificar, "__module__", "")
    return lote


def cargar_inferencia() -> Tuple[Clasificador, ClasificadorLote, str]:
    """`(clasificar, clasificar_lote, origen)` de la `ia` encontrada, o el MOCK si no hay ninguna."""
    raiz = buscar_ia()
    if raiz is not None:
        if str(raiz) not in sys.path:
            sys.path.insert(0, str(raiz))
        try:
            import ia.inferencia as inf
        except ImportError:
            return _clasificar_mock, _lote_desde(_clasificar_mock), "mock"
        lote = getattr(inf, "clasificar_lote", None) or _lote_desde(inf.clasificar)
        return inf.clasificar, lote, str(Path(inf.__file__).resolve().parent.parent)
    return _clasificar_mock, _lote_desde(_clasificar_mock), "mock"


def cargar_clasificar() -> Clasificador:
    """`clasificar` de la `ia` encontrada, o el MOCK (compatibilidad con S2)."""
    return cargar_inferencia()[0]


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
    """Buffer de 30 s por usuario y evaluación cada 5 s, una por una o en lote."""

    def __init__(self, clasificar: Optional[Clasificador] = None, ventana_s: float = VENTANA_S,
                 paso_s: float = PASO_S, tasa_hz: float = TASA_HZ,
                 clasificar_lote: Optional[ClasificadorLote] = None):
        if clasificar is None:
            clasificar, lote, origen = cargar_inferencia()
            clasificar_lote = clasificar_lote or lote
        else:
            origen = getattr(clasificar, "__module__", "")
        self._clasificar = clasificar
        self._lote = clasificar_lote or _lote_desde(clasificar)
        self._acepta_previo = len(inspect.signature(clasificar).parameters) > 1
        self.origen = origen
        self.ventana_s = ventana_s
        self.paso_s = paso_s
        self.esperadas = ventana_s * tasa_hz
        self._buffers: Dict[str, Deque[dict]] = {}
        self._primera: Dict[str, float] = {}
        self._ultima_eval: Dict[str, float] = {}
        self.previo: Dict[str, dict] = {}

    def observar(self, usuario: str, fila: dict) -> None:
        """Añade una muestra GPS (fila del `EmuladorGPS`) y descarta lo que sale de la ventana."""
        buf = self._buffers.setdefault(usuario, deque())
        self._primera.setdefault(usuario, fila["t"])
        buf.append({"t": fila["t"], "lat": fila["lat"], "lon": fila["lon"],
                    "precision_m": fila["precision_m"]})
        self._recortar(buf, fila["t"])

    def _recortar(self, buf: Deque[dict], t: float) -> None:
        while buf and buf[0]["t"] <= t - self.ventana_s:
            buf.popleft()

    def toca(self, usuario: str, t: float) -> bool:
        """True si toca evaluar: pasaron 5 s desde la última y el usuario lleva 30 s observado."""
        if usuario not in self._primera or t - self._primera[usuario] < self.ventana_s - 1:
            return False
        ultima = self._ultima_eval.get(usuario)
        return ultima is None or t - ultima >= self.paso_s

    def _ventana(self, usuario: str, t: float) -> List[dict]:
        buf = self._buffers[usuario]
        self._recortar(buf, t)  # sin muestras nuevas (teléfono apagado) la ventana se vacía
        return list(buf)

    def _anotar(self, usuario: str, t: float, ventana: List[dict], resultado: Optional[dict]) -> dict:
        self._ultima_eval[usuario] = t
        if not ventana or resultado is None:
            resultado = dict(SIN_DATOS)
        else:
            resultado = dict(resultado)
            self.previo[usuario] = resultado
        resultado["n_muestras"] = len(ventana)
        resultado["cobertura"] = min(1.0, len(ventana) / self.esperadas)
        return resultado

    def evaluar(self, usuario: str, t: float) -> Optional[dict]:
        """Clasifica la ventana actual del usuario si toca (cada `paso_s`)."""
        if not self.toca(usuario, t):
            return None
        ventana = self._ventana(usuario, t)
        resultado = None
        if ventana:
            if self._acepta_previo:
                resultado = self._clasificar(ventana, self.previo.get(usuario))
            else:
                resultado = self._clasificar(ventana)
        return self._anotar(usuario, t, ventana, resultado)

    def evaluar_lote(self, usuarios: Iterable[str], t: float) -> Dict[str, dict]:
        """Clasifica en una sola llamada a `clasificar_lote` a todos los usuarios a los que les toca."""
        toca = [u for u in usuarios if self.toca(u, t)]
        if not toca:
            return {}
        ventanas = {u: self._ventana(u, t) for u in toca}
        con_datos = [u for u in toca if ventanas[u]]
        resultados = self._lote([ventanas[u] for u in con_datos],
                                [self.previo.get(u) for u in con_datos]) if con_datos else []
        por_usuario = dict(zip(con_datos, resultados))
        return {u: self._anotar(u, t, ventanas[u], por_usuario.get(u)) for u in toca}

    def olvidar(self, usuario: str) -> None:
        for d in (self._buffers, self._primera, self._ultima_eval, self.previo):
            d.pop(usuario, None)
