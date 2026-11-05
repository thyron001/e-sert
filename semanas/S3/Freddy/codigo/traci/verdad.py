"""La "verdad de SUMO" por paso (S3-1): quién está estacionado de verdad y cuánto ocupa cada puesto.

`VerdadSUMO` es un hook `on_paso` del `Controlador`. Sirve de referencia para los KPIs de sistema
(`kpis_sistema.py`), que comparan lo que **cree** el sistema (sesiones y `MapaOcupacion`) con lo
que **pasa** en SUMO.

- Estado físico de cada vehículo con app: bit de *parking* de `VAR_STOPSTATE`
  (`(stopState & 2) != 0`), leído de la suscripción del `Controlador` en lugar de llamar a
  `isStoppedParking` en cada paso. `test_kpis_sistema.py` comprueba que ambos coinciden.
- `t_llegada_real`: primer paso estacionado; `t_salida_real`: primer paso en que deja de estarlo.
- Ocupación real por puesto, total (`parkingarea.getVehicleCount`) y solo de autos con
  `param con_app = 1` (`parkingarea.getVehicleIDs` + filtro). Se calcula bajo pedido, no en
  cada paso, porque son dos llamadas TraCI por puesto.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

BIT_PARKING = 2


def estacionado(stop_state: int) -> bool:
    """True si el bit de parking de `VAR_STOPSTATE` está encendido."""
    return (int(stop_state) & BIT_PARKING) != 0


class VerdadSUMO:
    """Hook del `Controlador` con la verdad física de los autos con app y de los puestos."""

    def __init__(self) -> None:
        self.con_app: Dict[str, bool] = {}
        self.parqueado: Dict[str, bool] = {}
        self.t_llegada_real: Dict[str, float] = {}
        self.t_salida_real: Dict[str, float] = {}

    # ------------------------------------------------------------------ hook

    def on_paso(self, ctrl, t: float) -> None:
        tr = ctrl.traci
        for veh in tr.simulation.getDepartedIDList():
            if veh not in self.con_app:
                self.con_app[veh] = tr.vehicle.getParameter(veh, "con_app") == "1"
        var = tr.constants.VAR_STOPSTATE
        for veh, datos in ctrl.vehiculos.items():
            if not self.con_app.get(veh):
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

    def ocupacion(self, ctrl, puestos: Iterable[str]) -> Dict[str, Tuple[int, int]]:
        """`{puesto: (ocupados_total, ocupados_con_app)}` en este paso."""
        pa = ctrl.traci.parkingarea
        salida = {}
        for pid in puestos:
            total = pa.getVehicleCount(pid)
            app = sum(1 for v in pa.getVehicleIDs(pid) if self.con_app.get(v)) if total else 0
            salida[pid] = (total, app)
        return salida
