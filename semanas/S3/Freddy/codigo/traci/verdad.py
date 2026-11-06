"""La "verdad de SUMO" por paso (S3-1): quién está estacionado de verdad y cuánto ocupa cada puesto.

`VerdadSUMO` es un hook `on_paso` del `Controlador`. Sirve de referencia para los KPIs de sistema
(`kpis_sistema.py`), que comparan lo que **cree** el sistema (sesiones y `MapaOcupacion`) con lo
que **pasa** en SUMO.

- Estado físico de cada vehículo con app: bit de *parking* de `VAR_STOPSTATE`
  (`(stopState & 2) != 0`), leído de la suscripción del `Controlador` en lugar de llamar a
  `isStoppedParking` en cada paso. `test_kpis_sistema.py` comprueba que ambos coinciden.
- `t_llegada_real`: primer paso estacionado; `t_salida_real`: primer paso en que deja de estarlo.
- Ocupación real por puesto, total (`parkingarea.getVehicleCount`) y solo de autos con
  `param con_app = 1` (`parkingarea.getVehicleIDs` + filtro). Se calcula bajo pedido.
- S3-2: la ocupación se **cuenta con eventos** (`getParkingStartingVehiclesIDList` y
  `getParkingEndingVehiclesIDList`, más un `getStops` por llegada) en lugar de dos llamadas por
  puesto en cada consulta (610 puestos). SUMO 1.12 no admite suscripciones a parkingArea
  ("Command not implemented"). Un test con SUMO comprueba que el conteo coincide con
  `getVehicleCount`. Con `contar_eventos=False` (o el `traci` falso de los tests) se usan las
  llamadas sueltas. `con_app` se consulta solo para los autos que sigue el `Controlador`.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .controlador import parametro

BIT_PARKING = 2


def estacionado(stop_state: int) -> bool:
    """True si el bit de parking de `VAR_STOPSTATE` está encendido."""
    return (int(stop_state) & BIT_PARKING) != 0


class VerdadSUMO:
    """Hook del `Controlador` con la verdad física de los autos con app y de los puestos."""

    def __init__(self, contar_eventos: bool = True) -> None:
        self.contar_eventos = contar_eventos
        self.con_app: Dict[str, bool] = {}
        self.en_puesto: Dict[str, Set[str]] = defaultdict(set)  # puesto → autos estacionados
        self._puesto_de: Dict[str, str] = {}
        self._contando = False
        self.parqueado: Dict[str, bool] = {}
        self.t_llegada_real: Dict[str, float] = {}
        self.t_salida_real: Dict[str, float] = {}

    # ------------------------------------------------------------------ hook

    def on_paso(self, ctrl, t: float) -> None:
        tr = ctrl.traci
        if self.contar_eventos and hasattr(tr.simulation, "getParkingEndingVehiclesIDList"):
            self._contar(tr)
        var = tr.constants.VAR_STOPSTATE
        for veh, datos in ctrl.vehiculos.items():
            app = self.con_app.get(veh)
            if app is None:
                app = self.con_app[veh] = parametro(ctrl, veh, "con_app") == "1"
            if not app:
                continue
            ahora = estacionado(datos.get(var, 0))
            if ahora and veh not in self.t_llegada_real:
                self.t_llegada_real[veh] = t
            elif not ahora and self.parqueado.get(veh) and veh not in self.t_salida_real:
                self.t_salida_real[veh] = t
            self.parqueado[veh] = ahora

    # ------------------------------------------------------------------ consultas

    def esta_estacionado(self, veh: str) -> bool:
        """Último estado físico conocido (False si el auto no tiene app o ya salió de la red)."""
        return self.parqueado.get(veh, False)

    def estacionados_app(self) -> List[str]:
        """Autos con app que ahora están estacionados."""
        return [veh for veh, p in self.parqueado.items() if p]

    def estadia(self, veh: str) -> Tuple[Optional[float], Optional[float]]:
        """`(t_llegada_real, t_salida_real)`; `None` si aún no ocurre."""
        return self.t_llegada_real.get(veh), self.t_salida_real.get(veh)

    def _contar(self, tr) -> None:
        """Actualiza `en_puesto` con los autos que empiezan y terminan de estacionar en este paso."""
        self._contando = True
        for veh in tr.simulation.getParkingEndingVehiclesIDList():
            pid = self._puesto_de.pop(veh, None)
            if pid is not None:
                self.en_puesto[pid].discard(veh)
        for veh in tr.simulation.getParkingStartingVehiclesIDList():
            paradas = tr.vehicle.getStops(veh, 1)
            if paradas:
                pid = paradas[0].stoppingPlaceID
                self._puesto_de[veh] = pid
                self.en_puesto[pid].add(veh)

    def ocupacion(self, ctrl, puestos: Iterable[str]) -> Dict[str, Tuple[int, int]]:
        """`{puesto: (ocupados_total, ocupados_con_app)}` en este paso."""
        salida = {}
        if self._contando:
            for pid in puestos:
                ids = self.en_puesto.get(pid, ())
                salida[pid] = (len(ids), sum(1 for v in ids if self.con_app.get(v)))
            return salida
        pa = ctrl.traci.parkingarea
        for pid in puestos:
            total = pa.getVehicleCount(pid)
            ids = pa.getVehicleIDs(pid) if total else ()
            salida[pid] = (total, sum(1 for v in ids if self.con_app.get(v)))
        return salida

