"""Controlador TraCI base: arranca SUMO, avanza el bucle y llama a los hooks `on_paso`.

Usa suscripciones (`vehicle.subscribe` y `person.subscribe`) en lugar de llamadas sueltas,
por rendimiento. La máquina de estados y el guiado (S2) se enchufan como hooks, sin tocar
el bucle.

Se ejecuta **dentro del contenedor** `van3twin`, desde `semanas/S1/Freddy/codigo`:

    python3 -m traci.controlador --cfg traci/escenario/tyrone/sumo/centro_base.sumocfg --hasta 300
    python3 -m traci.controlador --cfg ... --gui --hasta 600     # sumo-gui por VNC (:5901)
"""

from __future__ import annotations

import argparse
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from .sumo import cargar_libsumo, cargar_traci

Hook = Callable[["Controlador", float], None]


@dataclass
class ConfigControlador:
    """Cómo arrancar SUMO."""

    cfg: Path
    gui: bool = False
    semilla: Optional[int] = None
    args_extra: List[str] = field(default_factory=list)
    etiqueta: str = "esert"
    # Qué vehículos suscribir (por defecto, todos). El generador de trazas solo sigue algunos.
    filtro_vehiculos: Optional[Callable[[str], bool]] = None
    seguir_personas: bool = True
    # S3-2: `libsumo` (SUMO en el mismo proceso, sin socket). Solo sin GUI y un proceso por corrida.
    libsumo: bool = False
    cache_parametros: bool = True  # S3-2: `parametro()` recuerda los parámetros de cada vehículo


class Controlador:
    """Bucle TraCI con suscripciones y hooks.

    Tras cada `paso()`, `self.vehiculos` y `self.personas` tienen los resultados de las
    suscripciones: `{id: {VAR_POSITION: (x, y), VAR_SPEED: v, ...}}`.
    """

    VARS_VEHICULO = ("VAR_POSITION", "VAR_SPEED", "VAR_STOPSTATE")
    VARS_PERSONA = ("VAR_POSITION", "VAR_SPEED")

    def __init__(self, config: ConfigControlador):
        self.config = config
        if config.libsumo and config.gui:
            raise ValueError("libsumo no tiene GUI: usa traci con --gui")
        self.traci = cargar_libsumo() if config.libsumo else cargar_traci()
        tc = self.traci.constants
        self._vars_veh = [getattr(tc, n) for n in self.VARS_VEHICULO]
        self._vars_per = [getattr(tc, n) for n in self.VARS_PERSONA]
        self.hooks: List[Hook] = []
        self.vehiculos: Dict[str, dict] = {}
        self.personas: Dict[str, dict] = {}
        self.t: float = 0.0
        self.pasos = 0
        self.vistos_vehiculos = 0
        self.vistas_personas = 0
        self._personas_suscritas: set = set()
        self._parametros: Dict[tuple, str] = {}
        self._activo = False

    # ------------------------------------------------------------------ ciclo de vida

    def comando(self) -> List[str]:
        """Línea de comandos de SUMO."""
        binario = "sumo-gui" if self.config.gui else "sumo"
        cmd = [binario, "-c", str(self.config.cfg), "--no-step-log", "true"]
        if self.config.semilla is not None:
            cmd += ["--seed", str(self.config.semilla)]
        if self.config.gui:
            cmd += ["--start", "true", "--quit-on-end", "true"]
        return cmd + list(self.config.args_extra)

    def iniciar(self) -> "Controlador":
        """Arranca SUMO con `traci.start`."""
        preparar_salidas(Path(self.config.cfg), self.config.args_extra)
        if self.config.libsumo:
            self.traci.start(self.comando())
        else:
            self.traci.start(self.comando(), label=self.config.etiqueta)
        self._activo = True
        self.t = self.traci.simulation.getTime()
        return self

    def cerrar(self) -> None:
        """Cierra la conexión con SUMO (idempotente)."""
        if self._activo:
            self.traci.close()
            self._activo = False

    def __enter__(self) -> "Controlador":
        return self.iniciar()

    def __exit__(self, *exc) -> None:
        self.cerrar()

    def agregar_hook(self, hook: Hook) -> None:
        """Registra una función `hook(controlador, t)` que se llama tras cada paso."""
        self.hooks.append(hook)

    # ------------------------------------------------------------------ bucle

    def paso(self) -> float:
        """Avanza un paso, actualiza suscripciones y llama a los hooks. Devuelve `t`."""
        tr = self.traci
        tr.simulationStep()
        self.t = tr.simulation.getTime()
        self.pasos += 1
        filtro = self.config.filtro_vehiculos
        for veh in tr.simulation.getDepartedIDList():
            if filtro is None or filtro(veh):
                tr.vehicle.subscribe(veh, self._vars_veh)
                self.vistos_vehiculos += 1
        self.vehiculos = tr.vehicle.getAllSubscriptionResults()
        if self.config.seguir_personas:
            nuevas = tr.simulation.getDepartedPersonIDList()
            if self.config.libsumo:
                # libsumo (1.12) no informa en getDepartedPersonIDList las personas creadas con
                # `person.add` (los peatones de diligencia): se descubren con getIDList.
                nuevas = [p for p in tr.person.getIDList() if p not in self._personas_suscritas]
            for per in nuevas:
                if per not in self._personas_suscritas:
                    tr.person.subscribe(per, self._vars_per)
                    self._personas_suscritas.add(per)
                    self.vistas_personas += 1
            self.personas = tr.person.getAllSubscriptionResults()
        for hook in self.hooks:
            hook(self, self.t)
        return self.t

    def correr(self, hasta: float) -> float:
        """Avanza hasta `t >= hasta` o hasta que no queden agentes. Devuelve `t` final."""
        while self.t < hasta and self.traci.simulation.getMinExpectedNumber() > 0:
            self.paso()
        return self.t

    # ------------------------------------------------------------------ utilidades

    def a_geo(self, x: float, y: float):
        """(x, y) de la red → (lat, lon) con `traci.simulation.convertGeo`."""
        lon, lat = self.traci.simulation.convertGeo(x, y)
        return lat, lon

    def parametro(self, veh: str, clave: str) -> str:
        """`vehicle.getParameter` con caché: `clase`, `con_app` y `destino` no cambian en la corrida.

        S3-2: varios hooks preguntan lo mismo por cada auto que sale; con ~5 000 autos al inicio
        eran miles de llamadas TraCI repetidas.
        """
        if not self.config.cache_parametros:
            return self.traci.vehicle.getParameter(veh, clave)
        k = (veh, clave)
        valor = self._parametros.get(k)
        if valor is None:
            valor = self._parametros[k] = self.traci.vehicle.getParameter(veh, clave)
        return valor

    def estacionado(self, datos_vehiculo: dict) -> bool:
        """True si el vehículo está detenido en un parkingArea (bit de parking de STOPSTATE)."""
        estado = datos_vehiculo.get(self.traci.constants.VAR_STOPSTATE, 0)
        return bool(int(estado) & 2)


def parametro(ctrl, veh: str, clave: str) -> str:
    """Parámetro del vehículo con la caché del `Controlador`; con un controlador falso, la llamada directa."""
    if hasattr(ctrl, "parametro"):
        return ctrl.parametro(veh, clave)
    return ctrl.traci.vehicle.getParameter(veh, clave)


def preparar_salidas(cfg: Path, args_extra: Sequence[str] = ()) -> None:
    """Crea las carpetas de los archivos de salida del .sumocfg (SUMO no las crea solo)."""
    prefijo = ""
    if "--output-prefix" in args_extra:
        prefijo = args_extra[list(args_extra).index("--output-prefix") + 1]
    for nodo in ET.parse(cfg).getroot().iter():
        valor = nodo.get("value", "")
        if nodo.tag.endswith("-output") and valor:
            (cfg.parent / Path(valor).parent / Path(prefijo).parent).mkdir(parents=True, exist_ok=True)


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Controlador TraCI base de e-sert")
    ap.add_argument("--cfg", required=True, type=Path, help="Archivo .sumocfg")
    ap.add_argument("--gui", action="store_true", help="Usa sumo-gui (pantalla :99, VNC 5901)")
    ap.add_argument("--hasta", type=float, default=600, help="Segundo de simulación final")
    ap.add_argument("--semilla", type=int, default=None)
    ap.add_argument("--captura", type=Path, default=None, help="PNG de sumo-gui al terminar (solo --gui)")
    args, extra = ap.parse_known_args(argv)
    cfg = ConfigControlador(cfg=args.cfg, gui=args.gui, semilla=args.semilla, args_extra=extra)
    inicio = time.perf_counter()
    with Controlador(cfg) as ctrl:
        ctrl.correr(args.hasta)
        if args.gui and args.captura:
            ctrl.traci.gui.screenshot("View #0", str(args.captura.resolve()))
            ctrl.paso()  # la captura se escribe al dar el siguiente paso
        print(f"t_sim={ctrl.t:.0f} s · pasos={ctrl.pasos} · vehículos={ctrl.vistos_vehiculos} · "
              f"personas={ctrl.vistas_personas} · en red ahora={len(ctrl.vehiculos)} · "
              f"tiempo real={time.perf_counter() - inicio:.1f} s")


if __name__ == "__main__":
    main()
