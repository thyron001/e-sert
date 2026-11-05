"""Corre un escenario con guiado, sesiones y cobro en la simulación (S2-3).

Se ejecuta **dentro del contenedor** `van3twin`, desde `semanas/S3/Freddy/codigo`:

    python3 -m traci.correr_guiado --escenario app50_s1          # 75 min simulados, en segundo plano
    python3 -m traci.correr_guiado --escenario base_s1           # línea base sin app, para comparar
    python3 -m traci.correr_guiado --escenario app50_s1 --fuente verdad   # oráculo de comparación
    python3 -m traci.correr_guiado --escenario app50_s1 --publicar http://localhost:8000

Escribe en `traci/salidas/` (ignorada por git): `sesiones_<esc>.csv`, `libro_<esc>.json`,
`busqueda_<esc>.csv` y `resumen_guiado_<esc>.json`.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from .controlador import ConfigControlador, Controlador
from .estados import ControlSesiones
from .gps import EmuladorGPS
from .guiado import Guia, RegistroBusqueda
from .peatones import GestorPeatones
from .puente_nucleo import Publicador, PuenteNucleo
from .sumo import cargar_sumolib

AQUI = Path(__file__).resolve().parent
SUMO = AQUI / "escenario" / "tyrone" / "sumo"
SALIDAS = AQUI / "salidas"


class PublicadorSnapshots:
    """Hook: cada segundo simulado empuja el estado del mundo (contrato §4.4) al backend."""

    def __init__(self, publicador: Publicador, sesiones: ControlSesiones, guia: Optional[Guia],
                 registro: RegistroBusqueda, peatones: GestorPeatones, net, kpis=None):
        self.publicador = publicador
        # S3-1: con `kpis` (KPIsSistema), el campo `verdad` lleva la ocupación real de SUMO, los
        # autos con app estacionados y las falsas liberaciones del paso (contrato §4.4 y §6).
        self.kpis = kpis
        self.net = net  # sumolib: convierte (x, y) a lon/lat sin llamadas TraCI
        self.sesiones = sesiones
        self.guia = guia
        self.registro = registro
        self.peatones = peatones
        self._ultimo_s = -1

    def on_paso(self, ctrl, t: float) -> None:
        if int(t) == self._ultimo_s:
            return
        self._ultimo_s = int(t)
        tc = ctrl.traci.constants
        vehiculos = []
        for veh, es_app in self.registro.con_app.items():
            if not es_app or veh not in ctrl.vehiculos:
                continue
            x, y = ctrl.vehiculos[veh][tc.VAR_POSITION]
            lat, lon = self._latlon(x, y)
            vehiculos.append({"id": f"sim_{veh}", "lat": lat, "lon": lon,
                              "estado": self._estado(veh), "con_app": True})
        peatones = []
        for ped in self.peatones.activos.values():
            if ped.ped in ctrl.personas:
                x, y = ctrl.personas[ped.ped][tc.VAR_POSITION]
                lat, lon = self._latlon(x, y)
                peatones.append({"id": ped.ped, "lat": lat, "lon": lon})
        cuerpo = {
            "t_sim": round(t, 1),
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "vehiculos": vehiculos,
            "peatones": peatones,
            "verdad": self._verdad(ctrl),
        }
        self.publicador.publicar(cuerpo)

    def _verdad(self, ctrl) -> dict:
        if self.kpis is None:
            return {"puestos": [], "estacionados": [], "falsas_liberaciones": []}
        cap = self.kpis.capacidad
        real = self.kpis.verdad.ocupacion(ctrl, cap)
        return {
            "puestos": [{"puesto_id": pid, "ocupados": min(r[0], cap[pid]), "capacidad": cap[pid]}
                        for pid, r in real.items()],
            "estacionados": [f"sim_{veh}" for veh in self.kpis.verdad.estacionados_app()],
            "falsas_liberaciones": self.kpis.tomar_falsas(),
        }

    def _latlon(self, x: float, y: float) -> tuple:
        lon, lat = self.net.convertXY2LonLat(x, y)
        return round(lat, 7), round(lon, 7)

    def _estado(self, veh: str) -> Optional[str]:
        if veh in self.sesiones.maquinas:
            return self.sesiones.maquinas[veh].estado
        if self.guia is not None and veh in self.guia.estado:
            estado = self.guia.estado[veh]
            return "BUSCANDO" if estado == "A_CIEGAS" else estado
        return None


def _progreso(ctrl, t: float) -> None:
    """Línea cada 300 s simulados: si SUMO cae, el log dice en qué segundo fue."""
    if int(t) % 300 == 0 and int(t) != _progreso.ultimo:
        _progreso.ultimo = int(t)
        print(f"progreso t={int(t)} s, autos en red={len(ctrl.vehiculos)}", flush=True)


_progreso.ultimo = -1


def main(argv: Optional[Sequence[str]] = None) -> dict:
    ap = argparse.ArgumentParser(description="Guiado, sesiones y cobro sobre un escenario de S2-3")
    ap.add_argument("--escenario", choices=["app50_s1", "base_s1"], default="app50_s1")
    ap.add_argument("--hasta", type=float, default=4500, help="Segundo de simulación final (75 min)")
    ap.add_argument("--fuente", choices=["mapa", "verdad"], default="mapa")
    ap.add_argument("--max-reasignaciones", type=int, default=3)
    ap.add_argument("--periodo-revision", type=float, default=10.0)
    ap.add_argument("--sin-guia", action="store_true", help="Solo sesiones, sin guiado (línea base con app)")
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--gps-semilla", type=int, default=1)
    ap.add_argument("--publicar", default=None, help="URL del backend (sin ruta), p. ej. http://localhost:8000")
    ap.add_argument("--gui", action="store_true")
    args, extra = ap.parse_known_args(argv)

    cfg = SUMO / f"{args.escenario}.sumocfg"
    # las salidas llevan la fuente de ocupación si no es la del sistema, para no mezclar corridas
    esc = args.escenario if (args.fuente == "mapa" or args.sin_guia) else f"{args.escenario}_{args.fuente}"
    puente = PuenteNucleo(SUMO / "parqueos" / "puestos.csv", semilla=args.semilla)
    guia = None if args.sin_guia else Guia(puente, SUMO / "demanda" / "destinos.csv", args.fuente,
                                           args.max_reasignaciones, args.periodo_revision)
    gps = EmuladorGPS(semilla=args.gps_semilla)
    peatones = GestorPeatones(SUMO / "demanda" / "destinos.csv", semilla=args.semilla,
                              registrar_trayectorias=False)
    sesiones = ControlSesiones(gps, SALIDAS, esc, puente=puente, solo_con_app=True)
    registro = RegistroBusqueda()
    publicador = None
    net = None
    if args.publicar:
        publicador = Publicador(args.publicar, token=os.environ.get("ESERT_TOKEN_SIM"))
        net = cargar_sumolib().net.readNet(str(SUMO / "red" / "centro.net.xml"))

    # Cada corrida escribe sus salidas de SUMO en su propia carpeta (no comparten el .sumocfg)
    carpeta_sumo = SUMO / "salidas" / esc
    carpeta_sumo.mkdir(parents=True, exist_ok=True)
    salidas_sumo = ["--stop-output", str(carpeta_sumo / "stops.xml"),
                    "--tripinfo-output", str(carpeta_sumo / "tripinfo.xml"),
                    "--statistic-output", str(carpeta_sumo / "estadisticas.xml")]
    config = ConfigControlador(cfg=cfg, gui=args.gui, semilla=args.semilla, args_extra=extra + salidas_sumo,
                               etiqueta=f"s3_{esc}")
    inicio = time.perf_counter()
    try:
        with Controlador(config) as ctrl:
            ctrl.agregar_hook(peatones.on_paso)
            if guia is not None:
                ctrl.agregar_hook(guia.on_paso)
            ctrl.agregar_hook(sesiones.on_paso)
            ctrl.agregar_hook(registro.on_paso)
            if publicador is not None:
                ctrl.agregar_hook(PublicadorSnapshots(publicador, sesiones, guia, registro, peatones,
                                                      net).on_paso)
            ctrl.agregar_hook(_progreso)
            ctrl.correr(args.hasta)
            t_final = ctrl.t
    finally:
        sesiones.cerrar()
        if publicador is not None:
            publicador.cerrar()
    tiempo_real = time.perf_counter() - inicio

    SALIDAS.mkdir(parents=True, exist_ok=True)
    puente.guardar_sesiones(SALIDAS / f"sesiones_{esc}.csv")
    puente.guardar_libro(SALIDAS / f"libro_{esc}.json")
    registro.guardar(SALIDAS / f"busqueda_{esc}.csv", guia)
    resumen = {
        "escenario": esc,
        "t_sim_final": t_final,
        "tiempo_real_s": round(tiempo_real, 1),
        "velocidad_sim_x_real": round(t_final / tiempo_real, 3) if tiempo_real else None,
        "guia": guia.resumen() if guia else None,
        "sesiones_maquina": sesiones.resumen(),
        "nucleo": puente.resumen(),
        "publicador": publicador.resumen() if publicador else None,
        "peatones": peatones.resumen(),
    }
    (SALIDAS / f"resumen_guiado_{esc}.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    return resumen


if __name__ == "__main__":
    main()
