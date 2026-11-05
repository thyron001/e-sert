"""Guiado, sesiones y cobro (S2-3). Las pruebas puras usan un `traci` falso; las marcadas `sumo`
corren el escenario mínimo con SUMO dentro del contenedor van3twin (`pytest traci/tests -m sumo`).
"""

import os
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

ESCENARIO = Path(__file__).resolve().parents[1] / "escenario" / "tyrone" / "sumo"
EN_CONTENEDOR = Path("/home/vanet/results").is_dir() and bool(os.environ.get("SUMO_HOME"))


# ----------------------------------------------------------------------------- pruebas puras

class _TraciFalso:
    """Lo mínimo de `traci` que usa `Guia.on_paso`."""

    def __init__(self):
        self.salidas = []
        self.llegadas = []
        self.params = {}
        self.conteo = {}
        self.reroutes = []
        self.simulation = SimpleNamespace(
            getDepartedIDList=lambda: list(self.salidas),
            getParkingStartingVehiclesIDList=lambda: list(self.llegadas),
        )
        self.vehicle = SimpleNamespace(
            getParameter=lambda veh, clave: self.params[veh][clave],
            rerouteParkingArea=lambda veh, pid: self.reroutes.append((veh, pid)),
        )
        self.parkingarea = SimpleNamespace(getVehicleCount=lambda pid: self.conteo.get(pid, 0),
                                           getLaneID=lambda pid: f"{pid}_lane")
        self.lane = SimpleNamespace(getEdgeID=lambda lane: lane.replace("_lane", "_edge"))
        self.inalcanzables = set()  # puestos a los que no hay ruta desde el auto
        self.vehicle.getRoadID = lambda veh: "origen"
        self.simulation.findRoute = lambda desde, hasta, **k: SimpleNamespace(
            edges=[] if hasta.replace("_edge", "") in self.inalcanzables else [desde, hasta])


def _entorno(fuente="mapa"):
    from traci.guiado import Guia
    from traci.puente_nucleo import PuenteNucleo

    puente = PuenteNucleo(ESCENARIO / "parqueos" / "puestos.csv", semilla=1)
    guia = Guia(puente, ESCENARIO / "demanda" / "destinos.csv", fuente, max_reasignaciones=3,
                periodo_revision_s=10.0)
    tr = _TraciFalso()
    ctrl = SimpleNamespace(traci=tr)
    return puente, guia, tr, ctrl


def _puestos_cercanos(puente, destino, n=3):
    """Los n puestos más cercanos al destino (lat, lon), del más cercano al más lejano."""
    from traci.puente_nucleo import distancia_m

    lat, lon = destino
    return sorted(puente.mapa.puestos.values(),
                  key=lambda p: distancia_m(lat, lon, p.lat, p.lon))[:n]


def _llenar(puente, pid):
    puente.mapa.fijar(pid, puente.mapa.puestos[pid].capacidad)


def _dar_salida(tr, veh, destino="Parque Calderón", con_app="1"):
    tr.params[veh] = {"clase": "busca", "con_app": con_app, "destino": destino}
    tr.salidas = [veh]


def test_recomendar_elige_el_libre_mas_cercano_y_excluye():
    from traci.guiado import recomendar

    puestos = {"A": (0.0, 0.0, 5), "B": (0.0, 0.01, 5), "C": (0.0, 0.02, 5)}
    libres = {"A": 0, "B": 3, "C": 3}
    assert recomendar((0.0, 0.0), puestos, libres.get) == "B"  # A está lleno
    assert recomendar((0.0, 0.0), puestos, libres.get, excluir=["B"]) == "C"
    assert recomendar((0.0, 0.0), puestos, {p: 0 for p in puestos}.get) is None


def test_nunca_asigna_un_puesto_lleno_segun_su_fuente():
    puente, guia, tr, ctrl = _entorno("mapa")
    destino = guia.destinos["Parque Calderón"][:2]
    cercano = _puestos_cercanos(puente, destino)[0]
    _llenar(puente, cercano.puesto_id)  # el sistema sabe que está lleno (sesiones abiertas)
    _dar_salida(tr, "v1")
    guia.on_paso(ctrl, 0.0)
    assert tr.reroutes == [("v1", tr.reroutes[0][1])]
    assert tr.reroutes[0][1] != cercano.puesto_id
    assert puente.mapa.libres(tr.reroutes[0][1]) > 0


def test_fuente_verdad_usa_la_ocupacion_real_de_sumo():
    puente, guia, tr, ctrl = _entorno("verdad")
    destino = guia.destinos["Parque Calderón"][:2]
    cercano = _puestos_cercanos(puente, destino)[0]
    tr.conteo[cercano.puesto_id] = cercano.capacidad  # SUMO sabe que está lleno; el mapa, no
    _dar_salida(tr, "v1")
    guia.on_paso(ctrl, 0.0)
    assert tr.reroutes[0][1] != cercano.puesto_id


def test_reasigna_al_llenarse_el_puesto_asignado():
    puente, guia, tr, ctrl = _entorno("mapa")
    _dar_salida(tr, "v1")
    guia.on_paso(ctrl, 0.0)
    primero = tr.reroutes[0][1]
    _llenar(puente, primero)  # se llena antes de llegar
    tr.salidas = []
    guia.on_paso(ctrl, 10.0)  # primera revisión
    assert len(tr.reroutes) == 2
    assert tr.reroutes[1][1] != primero
    assert guia.reasignaciones["v1"] == 1


def test_como_maximo_tres_reasignaciones_y_luego_a_ciegas():
    puente, guia, tr, ctrl = _entorno("mapa")
    _dar_salida(tr, "v1")
    guia.on_paso(ctrl, 0.0)
    tr.salidas = []
    for t in (10.0, 20.0, 30.0, 40.0):  # cada vez se llena el puesto asignado
        _llenar(puente, tr.reroutes[-1][1])
        guia.on_paso(ctrl, t)
    assert guia.reasignaciones["v1"] == 3
    assert guia.estado["v1"] == "A_CIEGAS"
    assert len(tr.reroutes) == 4  # la asignación inicial + 3 reasignaciones; ninguna más


def test_haversine_no_falla_con_puntos_casi_antipodas():
    from traci.clasificacion import haversine_m

    assert haversine_m(-2.9, -79.0, -2.9, -79.0) == pytest.approx(0.0, abs=1e-6)
    # antípodas exactos: el término a puede pasar de 1 por redondeo y no debe lanzar ValueError
    assert haversine_m(45.0, 0.0, -45.0, 180.0) == pytest.approx(20015086.8, rel=1e-3)


def test_no_reencamina_a_un_puesto_inalcanzable():
    puente, guia, tr, ctrl = _entorno("mapa")
    destino = guia.destinos["Parque Calderón"][:2]
    cercano = _puestos_cercanos(puente, destino)[0]
    tr.inalcanzables.add(cercano.puesto_id)  # SUMO no tiene ruta hasta ese puesto desde el auto
    _dar_salida(tr, "v1")
    guia.on_paso(ctrl, 0.0)
    assert tr.reroutes and tr.reroutes[0][1] != cercano.puesto_id
    assert guia.contadores["inalcanzables"] >= 1


def test_publicador_con_url_caida_no_bloquea_la_simulacion():
    from traci.puente_nucleo import Publicador

    pub = Publicador("http://127.0.0.1:9", timeout_s=0.5, reintentos=2, backoff_s=0.01)
    inicio = time.monotonic()
    for i in range(200):
        pub.publicar({"t_sim": float(i)})
    assert time.monotonic() - inicio < 0.5  # encolar no espera a la red
    pub.cerrar(espera_s=0.5)


# ----------------------------------------------------------------------------- SUMO

@pytest.mark.sumo
@pytest.mark.skipif(not EN_CONTENEDOR, reason="requiere el contenedor van3twin")
def test_cada_auto_con_app_tiene_una_sesion_y_el_libro_cuadra(escenario_mini, tmp_path):
    from traci.controlador import ConfigControlador, Controlador
    from traci.estados import ControlSesiones
    from traci.gps import EmuladorGPS
    from traci.guiado import Guia, RegistroBusqueda
    from traci.peatones import GestorPeatones
    from traci.puente_nucleo import PuenteNucleo

    # El escenario mínimo con los cinco autos de búsqueda con app
    ruta = escenario_mini.parent / "demanda" / "mini.rou.xml"
    raiz = ET.parse(ruta).getroot()
    for v in raiz:
        if v.tag in ("trip", "vehicle") and any(p.get("key") == "clase" and p.get("value") == "busca"
                                                  for p in v.findall("param")):
            for p in v.findall("param"):
                if p.get("key") == "con_app":
                    p.set("value", "1")
            if not any(p.get("key") == "con_app" for p in v.findall("param")):
                ET.SubElement(v, "param", key="con_app", value="1")
    ET.ElementTree(raiz).write(ruta)

    puente = PuenteNucleo(ESCENARIO / "parqueos" / "puestos.csv", semilla=1)
    guia = Guia(puente, ESCENARIO / "demanda" / "destinos.csv", "mapa")
    sesiones = ControlSesiones(EmuladorGPS(semilla=1), tmp_path, "mini", puente=puente, solo_con_app=True)
    peatones = GestorPeatones(ESCENARIO / "demanda" / "destinos.csv", semilla=1)
    registro = RegistroBusqueda()
    try:
        with Controlador(ConfigControlador(cfg=escenario_mini, etiqueta="s3_mini")) as ctrl:
            for hook in (peatones.on_paso, guia.on_paso, sesiones.on_paso, registro.on_paso):
                ctrl.agregar_hook(hook)
            ctrl.correr(16000)
    finally:
        sesiones.cerrar()

    cerradas = Counter(f["usuario_id"] for f in puente.cerradas)
    abiertas = Counter(v["usuario_id"] for v in puente.abiertas.values())
    assert sesiones.llegadas >= 1
    for veh in sesiones.puesto_de:  # cada auto con app que estacionó
        usuario = f"sim_{veh}"
        assert cerradas[usuario] + abiertas[usuario] == 1, usuario
    assert max(cerradas.values(), default=0) == 1  # nunca dos sesiones cerradas del mismo auto

    from backend.nucleo import tarifa as tar
    from comun.esquemas import TipoMovimiento as TM

    bloque = tar.centavos(tar.retencion())  # bloque mínimo que retiene cada sesión abierta
    for usuario in puente.recargas:
        t = puente.billetera.sumas(usuario)
        assert t[TM.recarga] - t[TM.debito] == puente.billetera.estado_centavos(usuario)["saldo"]
        assert t[TM.retencion] - t[TM.liberacion] == bloque * abiertas[usuario]
