"""Emulador de GPS de teléfono para vehículos y peatones de SUMO.

- Ruido gaussiano **correlacionado en el tiempo**: proceso AR(1) por eje, con ρ = 0,8 entre
  muestras consecutivas y desviación estacionaria `sigma_m` por eje. Así se comporta un GPS
  real en un cañón urbano: el error se "arrastra" unos segundos en vez de saltar al azar.
- Pérdida de muestras con probabilidad `p_perdida` (el proceso de error sigue avanzando).
- S3-2: ráfagas de pérdida tipo **Gilbert-Elliott** (cañón urbano): cada agente alterna entre un
  estado bueno y uno malo (sin señal). `rafaga_s` es la duración media del estado malo y
  `frac_rafaga` la fracción del tiempo que se pasa en él; ambos tiempos son exponenciales.
- `precision_m` reportada = `sigma_m × U(0,8; 1,5)`.
- `velocidad_mps` como la calcularía un teléfono: distancia entre posiciones **ruidosas**
  consecutivas / tiempo, no la velocidad de SUMO.
- Etiqueta verdadera `modo_real` (`vehiculo`, `quieto`, `a_pie`).

El núcleo (`EmuladorGPS.observar`) es puro: recibe posiciones (x, y) en metros de la red y un
conversor a lat/lon, así se prueba sin SUMO. `muestrear_controlador` lo conecta al
`Controlador` (posición verdadera de las suscripciones → `convertGeo`).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

CONVERSOR = Callable[[float, float], Tuple[float, float]]  # (x, y) → (lat, lon)

# Etapas de una persona en TraCI (constants.STAGE_*), copiadas para no depender de SUMO aquí.
STAGE_ESPERANDO_SALIR = 0
STAGE_ESPERANDO = 1
STAGE_CAMINANDO = 2
STAGE_EN_VEHICULO = 3

VEL_CONGESTION_MPS = 7 / 3.6  # "auto en congestión": menos de 7 km/h


def modo_real_vehiculo(estacionado: bool) -> str:
    """`quieto` si está estacionado (con la persona adentro); `vehiculo` si circula o está en tráfico."""
    return "quieto" if estacionado else "vehiculo"


def modo_real_persona(etapa: int) -> str:
    """`a_pie` si camina; `quieto` si está parada (etapa de espera); `vehiculo` si va en uno."""
    if etapa == STAGE_CAMINANDO:
        return "a_pie"
    if etapa == STAGE_EN_VEHICULO:
        return "vehiculo"
    return "quieto"


def conversor_plano(lat0: float = -2.8973, lon0: float = -79.0045) -> CONVERSOR:
    """Conversor equirrectangular local (para tests y gráficas; SUMO usa `convertGeo`)."""
    m_por_grado = 111_320.0
    cos0 = math.cos(math.radians(lat0))
    return lambda x, y: (lat0 + y / m_por_grado, lon0 + x / (m_por_grado * cos0))


@dataclass
class _EstadoAgente:
    """Estado del GPS de un agente: error AR(1) y la última muestra emitida."""

    ex: float
    ey: float
    t: float
    malo: bool = False  # Gilbert-Elliott: en ráfaga sin señal
    x_emit: Optional[float] = None
    y_emit: Optional[float] = None
    t_emit: Optional[float] = None


class EmuladorGPS:
    """GPS ruidoso por agente. `observar()` devuelve una fila del CSV del contrato, o None si se pierde."""

    def __init__(self, semilla: int, sigma_m: float = 5.0, p_perdida: float = 0.02, tasa_hz: float = 1,
                 rho: float = 0.8, rafaga_s: Optional[float] = None, frac_rafaga: float = 0.3):
        if not 0 <= rho < 1:
            raise ValueError("rho debe estar en [0, 1)")
        if rafaga_s is not None and (rafaga_s <= 0 or not 0 < frac_rafaga < 1):
            raise ValueError("rafaga_s > 0 y frac_rafaga en (0, 1)")
        self.rafaga_s = rafaga_s
        self.frac_rafaga = frac_rafaga
        self.rng = random.Random(semilla)
        self.sigma_m = sigma_m
        self.p_perdida = p_perdida
        self.tasa_hz = tasa_hz
        self.periodo = 1.0 / tasa_hz
        self.rho = rho
        self._agentes: Dict[str, _EstadoAgente] = {}

    def toca_muestra(self, agente_id: str, t: float) -> bool:
        """True si ya pasó un periodo desde la última muestra del agente (o es nuevo)."""
        estado = self._agentes.get(agente_id)
        return estado is None or t - estado.t >= self.periodo - 1e-9

    def _avanzar_error(self, estado: _EstadoAgente, t: float) -> None:
        # ρ es por muestra; si pasaron k periodos (p. ej. tras un hueco), se usa ρ^k.
        k = max(1.0, (t - estado.t) / self.periodo)
        r = self.rho ** k
        innov = self.sigma_m * math.sqrt(1 - r * r)
        estado.ex = r * estado.ex + innov * self.rng.gauss(0, 1)
        estado.ey = r * estado.ey + innov * self.rng.gauss(0, 1)
        estado.t = t

    def observar(self, agente_id: str, t: float, x: float, y: float, modo_real: str,
                 a_geo: CONVERSOR) -> Optional[dict]:
        """Muestra el GPS del agente en `t` con posición verdadera (x, y) en metros de la red."""
        estado = self._agentes.get(agente_id)
        if estado is None:  # el error arranca en su distribución estacionaria
            estado = _EstadoAgente(self.rng.gauss(0, self.sigma_m), self.rng.gauss(0, self.sigma_m), t)
            if self.rafaga_s is not None:  # y la ráfaga también
                estado.malo = self.rng.random() < self.frac_rafaga
            self._agentes[agente_id] = estado
            dt = 0.0
        else:
            dt = t - estado.t
            self._avanzar_error(estado, t)
        if self.rafaga_s is not None:
            self._avanzar_rafaga(estado, dt)
            if estado.malo:
                return None
        if self.rng.random() < self.p_perdida:
            return None
        xr, yr = x + estado.ex, y + estado.ey
        velocidad = None
        if estado.t_emit is not None and t > estado.t_emit:
            velocidad = math.hypot(xr - estado.x_emit, yr - estado.y_emit) / (t - estado.t_emit)
        estado.x_emit, estado.y_emit, estado.t_emit = xr, yr, t
        lat, lon = a_geo(xr, yr)
        return {
            "usuario_id": agente_id,
            "t": round(t, 3),
            "lat": round(lat, 7),
            "lon": round(lon, 7),
            "precision_m": round(self.sigma_m * self.rng.uniform(0.8, 1.5), 2),
            "velocidad_mps": None if velocidad is None else round(velocidad, 3),
            "modo_real": modo_real,
        }

    def _avanzar_rafaga(self, estado: _EstadoAgente, dt: float) -> None:
        """Cadena de Markov de dos estados en tiempo continuo (salidas exponenciales)."""
        if dt <= 0:
            return
        if estado.malo:
            salir = 1 - math.exp(-dt / self.rafaga_s)
        else:  # media en estado bueno = rafaga_s · (1 − f) / f
            salir = 1 - math.exp(-dt * self.frac_rafaga / ((1 - self.frac_rafaga) * self.rafaga_s))
        if self.rng.random() < salir:
            estado.malo = not estado.malo

    def error_actual(self, agente_id: str) -> Tuple[float, float]:
        """Error (ex, ey) en metros del agente (para tests y gráficas)."""
        e = self._agentes[agente_id]
        return e.ex, e.ey

    def olvidar(self, agente_id: str) -> None:
        """El agente salió de la simulación."""
        self._agentes.pop(agente_id, None)


def muestrear_controlador(gps: EmuladorGPS, ctrl, t: float, seguidos_veh=None,
                          seguidas_per=None) -> List[dict]:
    """Muestra el GPS de los vehículos y personas suscritos al `Controlador` en el paso `t`.

    Cada fila trae además, como columnas extra del contrato (§8), la posición y la velocidad
    verdaderas y el `caso` (`normal`, `congestion` o `peaton_rapido`).
    """
    tc = ctrl.traci.constants
    filas = []
    for veh, datos in ctrl.vehiculos.items():
        if seguidos_veh is not None and veh not in seguidos_veh:
            continue
        agente = f"sim_{veh}"
        if not gps.toca_muestra(agente, t):
            continue
        x, y = datos[tc.VAR_POSITION]
        v = datos[tc.VAR_SPEED]
        estacionado = ctrl.estacionado(datos)
        fila = gps.observar(agente, t, x, y, modo_real_vehiculo(estacionado), ctrl.a_geo)
        if fila:
            caso = "congestion" if (not estacionado and v < VEL_CONGESTION_MPS) else "normal"
            filas.append(_extra(fila, ctrl.a_geo(x, y), v, caso))
    for per, datos in ctrl.personas.items():
        if seguidas_per is not None and per not in seguidas_per:
            continue
        agente = f"ped_{per}"
        if not gps.toca_muestra(agente, t):
            continue
        x, y = datos[tc.VAR_POSITION]
        etapa = ctrl.traci.person.getStage(per).type
        fila = gps.observar(agente, t, x, y, modo_real_persona(etapa), ctrl.a_geo)
        if fila:
            rapido = ctrl.traci.person.getTypeID(per).startswith("peaton_rapido")
            caso = "peaton_rapido" if rapido and etapa == STAGE_CAMINANDO else "normal"
            filas.append(_extra(fila, ctrl.a_geo(x, y), datos[tc.VAR_SPEED], caso))
    return filas


def _extra(fila: dict, latlon_real: Tuple[float, float], v_real: float, caso: str) -> dict:
    fila["lat_real"], fila["lon_real"] = round(latlon_real[0], 7), round(latlon_real[1], 7)
    fila["velocidad_real_mps"] = round(v_real, 3)
    fila["caso"] = caso
    return fila
