"""Colores de sumo-gui (2026-11-18): la misma paleta que el visor web.

- autos de la app web (los espejos): amarillo y resaltados con un círculo;
- autos que buscan parqueo: naranja buscando, violeta guiados por la app, azul estacionados;
- tráfico de paso y autos de fondo: gris (para que se distinga lo demás);
- peatones de la app web: azul (SUMO 1.12 no resalta personas).

Solo se instala con `--gui` (en el VPS, `sumo.tesisucuenca.com`): en los experimentos no cuesta nada.
Cada color se pone una vez por cambio de estado, no en cada paso.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .controlador import parametro

Color = Tuple[int, int, int, int]
GRIS: Color = (150, 150, 150, 255)
BUSCANDO: Color = (255, 159, 28, 255)
GUIADO: Color = (167, 139, 250, 255)
ESTACIONADO: Color = (96, 165, 250, 255)
PROPIO: Color = (255, 214, 10, 255)
PEATON: Color = (37, 99, 235, 255)
PERIODO_S = 2.0


class ColoresGui:
    """Hook `on_paso` del `Controlador`."""

    def __init__(self, guia):
        self.guia = guia
        self._puesto: Dict[str, Color] = {}
        self._peatones: set = set()
        self._ultimo = -PERIODO_S

    def _color(self, tr, veh: str, color: Color) -> None:
        if self._puesto.get(veh) != color:
            self._puesto[veh] = color
            tr.vehicle.setColor(veh, color)

    def on_paso(self, ctrl, t: float) -> None:
        tr = ctrl.traci
        if not getattr(self, "_esquema", False):
            # el archivo de vista trae el esquema «esert» (autos 3,5× más grandes), pero sumo-gui 1.12
            # arranca con «standard»: se elige aquí
            self._esquema = True
            try:
                tr.gui.setSchema("View #0", "esert")
            except tr.exceptions.TraCIException:
                pass
        for veh in tr.simulation.getDepartedIDList():
            if tr.vehicle.getParameter(veh, "web") == "1":
                self._color(tr, veh, PROPIO)
                tr.vehicle.highlight(veh, PROPIO, size=-1)
            elif parametro(ctrl, veh, "clase") == "busca":
                self._color(tr, veh, BUSCANDO)
            else:
                self._color(tr, veh, GRIS)
        for veh in tr.simulation.getArrivedIDList():
            self._puesto.pop(veh, None)
        if t - self._ultimo < PERIODO_S:
            return
        self._ultimo = t
        for veh, est in list(self.guia.estado.items()):
            if veh in self.guia.web or veh not in self._puesto:
                continue
            color = {"GUIADO": GUIADO, "ESTACIONADO": ESTACIONADO}.get(est, BUSCANDO)
            self._color(tr, veh, color)
        for ped in tr.person.getIDList():
            if ped.startswith("ped_web_") and ped not in self._peatones:
                self._peatones.add(ped)
                tr.person.setColor(ped, PEATON)

