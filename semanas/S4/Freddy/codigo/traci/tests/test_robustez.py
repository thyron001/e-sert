"""Robustez (S3-2): teléfono apagado, política de datos pobres, ráfagas de pérdida y libsumo.

Los casos unitarios usan un `traci` falso y corren en la computadora; los marcados `sumo`
necesitan el contenedor `van3twin`.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from traci.clasificacion import ClasificadorUsuario, _clasificar_mock
from traci.estados import ControlSesiones, MaquinaSesion, datos_pobres
from traci.gps import EmuladorGPS, conversor_plano
from traci.puente_nucleo import PuenteNucleo

EN_CONTENEDOR = Path("/home/vanet/results").is_dir() and bool(os.environ.get("SUMO_HOME"))
VAR_POSITION, VAR_STOPSTATE = 0x42, 0xB5
PUESTO = "pa_x_0"
CONVERSOR = conversor_plano()


# ---------------------------------------------------------------------------- política (pura)


def test_datos_pobres():
    assert datos_pobres(0.3, "rf", 0.9)          # menos del 50 % de las muestras
    assert datos_pobres(0.9, "umbral", 0.4)      # fallback poco confiable
    assert not datos_pobres(0.9, "umbral", 0.9)
    assert not datos_pobres(0.6, "rf", 0.4)      # el rf con poca confianza sí decide


def test_politica_retiene_el_estado_con_ventanas_incompletas():
    m = MaquinaSesion("sim_v")
    for k in range(10):  # 10 ventanas "vehiculo" lejos del puesto, pero con 30 % de muestras
        assert m.actualizar("vehiculo", 80.0, 5.0 * k, cobertura=0.3, fuente="umbral", confianza=0.3) == []
    assert m.estado == "ESTACIONADO" and m.retenidas == 10
    # con datos completos bastan dos ventanas seguidas para salir
    m.actualizar("vehiculo", 80.0, 60.0)
    assert m.actualizar("vehiculo", 80.0, 65.0)[-1].hacia == "CERRADA"


def test_ventana_pobre_no_cuenta_para_las_dos_ventanas_en_vehiculo():
    m = MaquinaSesion("sim_v")
    m.actualizar("vehiculo", 80.0, 0.0)
    m.actualizar("vehiculo", 80.0, 5.0, cobertura=0.2)  # retenida: ni suma ni reinicia la cuenta
    assert m.estado == "ESTACIONADO"
    assert m.actualizar("vehiculo", 80.0, 10.0)[-1].hacia == "CERRADA"


def test_sin_politica_la_ventana_pobre_si_decide():
    m = MaquinaSesion("sim_v", politica_datos_pobres=False)
    m.actualizar("vehiculo", 80.0, 0.0, cobertura=0.2)
    assert m.actualizar("vehiculo", 80.0, 5.0, cobertura=0.2)[-1].hacia == "CERRADA"


# ---------------------------------------------------------------------------- ráfagas (GPS puro)


def test_rafagas_gilbert_elliott_fraccion_y_duracion():
    gps = EmuladorGPS(semilla=7, p_perdida=0.0, rafaga_s=60.0, frac_rafaga=0.3)
    perdidas = [gps.observar("u", float(t), 0.0, 0.0, "quieto", CONVERSOR) is None for t in range(200_000)]
    frac = sum(perdidas) / len(perdidas)
    rachas, n = [], 0
    for p in perdidas:
        if p:
            n += 1
        elif n:
            rachas.append(n)
            n = 0
    assert frac == pytest.approx(0.30, abs=0.03)
    assert sum(rachas) / len(rachas) == pytest.approx(60, rel=0.15)


def test_sin_rafagas_el_emulador_no_cambia():
    """Con `rafaga_s=None` la secuencia es la misma que antes de S3-2 (mismos números al azar)."""
    a = EmuladorGPS(semilla=3)
    b = EmuladorGPS(semilla=3, rafaga_s=None)
    fa = [a.observar("u", float(t), t * 1.0, 0.0, "vehiculo", CONVERSOR) for t in range(50)]
    fb = [b.observar("u", float(t), t * 1.0, 0.0, "vehiculo", CONVERSOR) for t in range(50)]
    assert fa == fb


# ---------------------------------------------------------------------------- ControlSesiones con traci falso


class Mundo:
    """Un auto que estaciona en `PUESTO` y su conductor, con un `traci` falso y el núcleo real."""

    def __init__(self, tmp_path: Path):
        csv = tmp_path / "puestos.csv"
        csv.write_text("puesto_id,edge,lane,calle,capacidad,lat,lon,x,y\n"
                       f"{PUESTO},x,x_0,Calle X,5,{CONVERSOR(0, 0)[0]},{CONVERSOR(0, 0)[1]},0,0\n", encoding="utf-8")
        self.puente = PuenteNucleo(csv, semilla=1, recarga_usd=(20.0, 20.0))
        self.puente.registrar("sim_v1")  # en la corrida real la recarga inicial la hace `Guia`
        self.cerradas = []
        self.puente.al_cerrar.append(self.cerradas.append)
        self.llegan = []
        self.parqueado = True
        self.pos_auto = (0.0, 0.0)
        self.pos_ped = None  # None: el conductor está en el auto
        tr = SimpleNamespace(
            constants=SimpleNamespace(VAR_POSITION=VAR_POSITION, VAR_STOPSTATE=VAR_STOPSTATE),
            simulation=SimpleNamespace(getParkingStartingVehiclesIDList=lambda: list(self.llegan)),
            vehicle=SimpleNamespace(
                getParameter=lambda veh, k: {"clase": "busca", "con_app": "1"}[k],
                getStops=lambda veh, *a: [SimpleNamespace(stoppingPlaceID=PUESTO)],
                getPosition=lambda veh: self.pos_auto,
                isStoppedParking=lambda veh: self.parqueado),
            person=SimpleNamespace(getStage=lambda ped: SimpleNamespace(description="caminando", type=2)),
        )
        self.ctrl = SimpleNamespace(traci=tr, vehiculos={}, personas={}, a_geo=CONVERSOR,
                                    estacionado=lambda d: bool(d[VAR_STOPSTATE] & 2))

    def paso(self, ses: ControlSesiones, t: float, en_red: bool = True) -> None:
        self.ctrl.vehiculos = {"v1": {VAR_POSITION: self.pos_auto, VAR_STOPSTATE: 3 if self.parqueado else 0}} \
            if en_red else {}
        self.ctrl.personas = {} if self.pos_ped is None else {"ped_v1": {VAR_POSITION: self.pos_ped}}
        ses.on_paso(self.ctrl, t)
        self.llegan = []


def _sesiones(mundo: Mundo, tmp_path: Path, **kw) -> ControlSesiones:
    gps = EmuladorGPS(semilla=1, sigma_m=0.5, p_perdida=0.0)
    clf = ClasificadorUsuario(clasificar=_clasificar_mock)
    return ControlSesiones(gps, tmp_path / "salidas", "test", clasificador=clf, puente=mundo.puente,
                           solo_con_app=True, **kw)


def test_telefono_apagado_no_libera_y_cierra_al_tope(tmp_path):
    mundo = Mundo(tmp_path)
    ses = _sesiones(mundo, tmp_path, frac_apagado=1.0, tiempo_maximo_s=600)
    mundo.llegan = ["v1"]
    for t in range(0, 40):            # el conductor sigue en el auto
        mundo.paso(ses, float(t))
    for k, t in enumerate(range(40, 120)):  # camina alejándose a 1,4 m/s
        mundo.pos_ped = (1.4 * k, 0.0)
        mundo.paso(ses, float(t))
    assert ses.apagados_efectivos == 1, "el teléfono debió apagarse al pasar a A_PIE"
    mundo.pos_ped = None
    for t in range(120, 400):         # silencio; a los 120 s sin datos se marca sin_senal
        mundo.paso(ses, float(t))
    assert "v1" in ses.sin_senal and ses.marcadas_sin_senal == 1
    assert mundo.cerradas == [] and ses.falsas_liberaciones == 0  # el silencio nunca cierra
    mundo.parqueado = False
    for t in range(400, 700):         # el auto se va sin teléfono: espera al tope (600 s)
        mundo.paso(ses, float(t), en_red=t < 410)
    assert len(mundo.cerradas) == 1 and ses.falsas_liberaciones == 0
    cierre = mundo.cerradas[0]
    assert cierre["motivo"] == "timeout_sin_senal" and cierre["t_fin"] == 600
    assert cierre["minutos_reales"] == pytest.approx(10.0) and cierre["debitado"] == pytest.approx(0.08)


def test_sin_telefono_apagado_la_salida_sin_deteccion_es_manual(tmp_path):
    mundo = Mundo(tmp_path)
    ses = _sesiones(mundo, tmp_path)
    mundo.llegan = ["v1"]
    for t in range(0, 50):
        mundo.paso(ses, float(t))
    mundo.paso(ses, 50.0, en_red=False)
    assert [c["motivo"] for c in mundo.cerradas] == ["manual"]


def test_rafagas_del_30_por_ciento_sin_falsas_por_ventanas_incompletas(tmp_path):
    """Auto estacionado 2 h con el teléfono adentro y ráfagas del 30 %: ninguna falsa liberación
    se decide con una ventana incompleta (la política las retiene)."""
    mundo = Mundo(tmp_path)
    gps = EmuladorGPS(semilla=5, sigma_m=5.0, p_perdida=0.02, rafaga_s=60.0, frac_rafaga=0.3)
    ses = ControlSesiones(gps, tmp_path / "salidas", "rafagas", puente=mundo.puente, solo_con_app=True,
                          clasificador=ClasificadorUsuario(clasificar=_clasificar_mock))
    mundo.llegan = ["v1"]
    for t in range(0, 7200):
        mundo.paso(ses, float(t))
        if "v1" not in ses.maquinas:
            break
    assert ses.ventanas_retenidas > 0
    assert ses.falsas_con_datos_pobres == 0


# ---------------------------------------------------------------------------- con SUMO


@pytest.mark.sumo
@pytest.mark.skipif(not EN_CONTENEDOR, reason="requiere el contenedor van3twin")
def test_libsumo_y_traci_dan_los_mismos_kpis():
    from traci.correr_kpis import correr

    a = correr("p50_umbral_s1", 300, sufijo="_test_traci", libsumo=False, guardar_csv=False)
    b = correr("p50_umbral_s1", 300, sufijo="_test_libsumo", libsumo=True, guardar_csv=False)
    ka, kb = a["kpis"], b["kpis"]
    assert ka.keys() == kb.keys()
    for k in ka:
        assert (ka[k] == kb[k]) or (isinstance(ka[k], float) and math.isnan(ka[k]) and math.isnan(kb[k])), k
    sa = {k: v for k, v in a["sesiones_maquina"].items() if k != "clasificador"}
    sb = {k: v for k, v in b["sesiones_maquina"].items() if k != "clasificador"}
    assert sa == sb and sa["sesiones"] > 0


@pytest.mark.sumo
@pytest.mark.skipif(not EN_CONTENEDOR, reason="requiere el contenedor van3twin")
def test_conteo_de_puestos_por_eventos_igual_a_getVehicleCount():
    from traci.controlador import ConfigControlador, Controlador
    from traci.correr_kpis import SUMO, preparar_escenario
    from traci.verdad import VerdadSUMO

    puestos = [ln.split(",")[0] for ln in (SUMO / "parqueos" / "puestos.csv").read_text().splitlines()[1:]]
    with Controlador(ConfigControlador(cfg=preparar_escenario(80, 1), semilla=1, libsumo=True)) as ctrl:
        ctrl.config.filtro_vehiculos = lambda v: ctrl.parametro(v, "clase") == "busca"
        verdad = VerdadSUMO()
        ctrl.agregar_hook(verdad.on_paso)
        for k in range(900):
            ctrl.paso()
            if k % 60 == 59:
                ev = verdad.ocupacion(ctrl, puestos)
                assert all(ev[p][0] == ctrl.traci.parkingarea.getVehicleCount(p) for p in puestos), ctrl.t
        assert sum(n for n, _ in ev.values()) > 1000
