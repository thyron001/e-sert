"""KPIs de sistema (S3-1): casos unitarios con un `traci` falso e integración con SUMO.

Los unitarios corren en la computadora; la equivalencia con `isStoppedParking` y la corrida
`p50_rf_s1` necesitan el contenedor `van3twin` (SUMO 1.12).
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from traci.kpis_sistema import CLAVES_RESUMEN, KPIsSistema, comparar_mapa
from traci.puente_nucleo import PuenteNucleo
from traci.verdad import VerdadSUMO, estacionado

EN_CONTENEDOR = Path("/home/vanet/results").is_dir() and bool(os.environ.get("SUMO_HOME"))
VAR_STOPSTATE = 0xB5
PARKING = 2 | 1  # detenido y en parking (bit 2)


# ---------------------------------------------------------------------------- traci falso


class TraciFalso:
    """Lo mínimo de TraCI que usan `VerdadSUMO` y `KPIsSistema`. El test fija el mundo a mano."""

    def __init__(self):
        self.constants = SimpleNamespace(VAR_STOPSTATE=VAR_STOPSTATE)
        self.salidos = []          # getDepartedIDList del paso
        self.params = {}           # veh → con_app
        self.parqueados = set()    # isStoppedParking
        self.en_puesto = {}        # puesto → [veh]
        self.simulation = SimpleNamespace(getDepartedIDList=lambda: list(self.salidos))
        self.vehicle = SimpleNamespace(
            getParameter=lambda veh, clave: self.params.get(veh, "0") if clave == "con_app" else "",
            isStoppedParking=lambda veh: veh in self.parqueados,
        )
        self.parkingarea = SimpleNamespace(
            getVehicleCount=lambda pa: len(self.en_puesto.get(pa, [])),
            getVehicleIDs=lambda pa: list(self.en_puesto.get(pa, [])),
        )


class CtrlFalso:
    """`Controlador` sin SUMO: `paso(t)` llama a los hooks con el mundo que fijó el test."""

    def __init__(self):
        self.traci = TraciFalso()
        self.vehiculos = {}
        self.hooks = []

    def agregar_hook(self, hook):
        self.hooks.append(hook)

    def poner(self, veh, parqueado, con_app=True, puesto=None):
        """Mete o actualiza un vehículo (con app por defecto)."""
        tr = self.traci
        if veh not in self.vehiculos:
            tr.salidos.append(veh)
        tr.params[veh] = "1" if con_app else "0"
        self.vehiculos[veh] = {VAR_STOPSTATE: PARKING if parqueado else 0}
        if parqueado:
            tr.parqueados.add(veh)
            if puesto:
                tr.en_puesto.setdefault(puesto, [])
                if veh not in tr.en_puesto[puesto]:
                    tr.en_puesto[puesto].append(veh)
        else:
            tr.parqueados.discard(veh)
            for lista in tr.en_puesto.values():
                if veh in lista:
                    lista.remove(veh)

    def paso(self, t):
        for hook in self.hooks:
            hook(self, t)
        self.traci.salidos = []


PUESTOS_CSV = """puesto_id,edge,lane,calle,capacidad,lat,lon,x,y
pa_a_0,e1,e1_0,Calle A,1,-2.8970,-79.0040,0,0
pa_b_0,e2,e2_0,Calle B,2,-2.8971,-79.0041,10,0
pa_c_0,e3,e3_0,Calle C,2,-2.8972,-79.0042,20,0
pa_d_0,e4,e4_0,Calle D,3,-2.8973,-79.0043,30,0
"""


@pytest.fixture
def mundo(tmp_path):
    """Controlador falso, núcleo real (sqlite en memoria) con 4 puestos y `KPIsSistema`."""
    csv = tmp_path / "puestos.csv"
    csv.write_text(PUESTOS_CSV, encoding="utf-8")
    ctrl = CtrlFalso()
    nucleo = PuenteNucleo(csv, semilla=1, recarga_usd=(20.0, 20.0))
    kpis = KPIsSistema(ctrl, nucleo, intervalo_mapa_s=60)
    return ctrl, nucleo, kpis


def abrir(nucleo, veh, puesto, t):
    nucleo.registrar(f"sim_{veh}")
    sid = nucleo.iniciar(f"sim_{veh}", puesto, t)
    assert sid is not None
    return sid


def cerrar(nucleo, sid, t):
    """Cierre por detección como lo hace la máquina de estados: ESTACIONADO → SALIENDO → CERRADA."""
    nucleo.transicion(sid, "SALIENDO", t)
    nucleo.cerrar(sid, t)


# ---------------------------------------------------------------------------- unitarios


def test_bit_parking():
    assert estacionado(2) and estacionado(3) and estacionado(2 | 128)
    assert not estacionado(0) and not estacionado(1) and not estacionado(128)


def test_cierre_con_el_auto_estacionado_es_falsa_liberacion(mundo):
    ctrl, nucleo, kpis = mundo
    ctrl.poner("v1", parqueado=True, puesto="pa_b_0")
    ctrl.paso(100)
    sid = abrir(nucleo, "v1", "pa_b_0", 100)
    ctrl.paso(130)
    cerrar(nucleo, sid, 130)  # la máquina de estados cree que salió, pero sigue estacionado
    r = kpis.resumen()
    assert (r["n_sesiones"], r["n_falsas"], r["falsas_lib_100"]) == (1, 1, 100.0)
    assert math.isnan(r["retardo_cierre_mediana_s"])  # la falsa no cuenta para el retardo
    assert kpis.tomar_falsas() == [sid] and kpis.tomar_falsas() == []


def test_cierre_12_s_despues_de_salir(mundo):
    ctrl, nucleo, kpis = mundo
    ctrl.poner("v1", parqueado=True, puesto="pa_b_0")
    ctrl.paso(100)
    sid = abrir(nucleo, "v1", "pa_b_0", 100)
    ctrl.poner("v1", parqueado=False)
    ctrl.paso(1000)  # t_salida_real
    ctrl.paso(1012)
    cerrar(nucleo, sid, 1012)
    r = kpis.resumen()
    assert r["n_falsas"] == 0 and r["falsas_lib_100"] == 0.0
    assert r["retardo_cierre_mediana_s"] == r["retardo_cierre_p90_s"] == r["retardo_cierre_max_s"] == 12.0
    assert kpis.verdad.estadia("v1") == (100, 1000)


def test_estadia_de_47_min_cobrada_por_el_nucleo_error_cero(mundo):
    ctrl, nucleo, kpis = mundo
    ctrl.poner("v1", parqueado=True, puesto="pa_d_0")
    ctrl.paso(60)
    sid = abrir(nucleo, "v1", "pa_d_0", 60)
    ctrl.poner("v1", parqueado=False)
    t_salida = 60 + 47 * 60
    ctrl.paso(t_salida)
    cerrar(nucleo, sid, t_salida)  # cierre en el mismo paso de la salida: minutos reales = 47
    fila = kpis.detalle_sesiones().iloc[0] if _hay_pandas() else kpis._filas()[0]
    assert fila["minutos_reales_sumo"] == pytest.approx(47.0)
    assert fila["debitado"] == pytest.approx(0.50)  # 2 bloques de 30 min a $0,25
    r = kpis.resumen()
    assert r["error_fact_medio_usd"] == 0.0 and r["error_fact_abs_max_usd"] == 0.0
    assert r["ahorro_vs_tarjeta_medio_usd"] == pytest.approx(0.0)  # misma tarifa por bloques: sin ahorro


def test_precision_del_mapa_calculada_a_mano(mundo):
    """4 puestos; en la realidad hay 3 ocupados y el mapa conoce 2 (uno sin app)."""
    ctrl, nucleo, kpis = mundo
    ctrl.poner("v1", parqueado=True, puesto="pa_a_0")              # pa_a lleno (cap 1), con app
    ctrl.poner("v2", parqueado=True, puesto="pa_b_0")              # pa_b 1/2, con app
    ctrl.poner("v3", parqueado=True, con_app=False, puesto="pa_c_0")  # pa_c 1/2, sin app
    ctrl.paso(1)
    abrir(nucleo, "v1", "pa_a_0", 1)
    abrir(nucleo, "v2", "pa_b_0", 1)
    fila = kpis.medir_mapa(ctrl, 60)
    # total: mapa {a:1,b:1,c:0,d:0} vs real {a:1,b:1,c:1,d:0}: libre/lleno coincide en los 4
    assert fila["precision"] == 1.0 and fila["mae"] == pytest.approx(1 / 4) and fila["fantasmas"] == 0
    assert fila["precision_app"] == 1.0 and fila["mae_app"] == 0.0
    # si v3 hubiese llenado pa_a (cap 1) en vez de v1: el mapa lo ve libre → 1 libre fantasma
    m = comparar_mapa({"pa_a_0": 0, "pa_b_0": 1, "pa_c_0": 0, "pa_d_0": 0},
                      {"pa_a_0": 1, "pa_b_0": 1, "pa_c_0": 1, "pa_d_0": 0},
                      {"pa_a_0": 1, "pa_b_0": 2, "pa_c_0": 2, "pa_d_0": 3})
    assert m == {"exactitud": 0.75, "mae": 0.5, "fantasmas": 1}


def test_mapa_cada_60_s_y_sin_cierre(mundo):
    ctrl, nucleo, kpis = mundo
    ctrl.poner("v1", parqueado=True, puesto="pa_b_0")
    for t in range(0, 181):
        ctrl.paso(float(t))
    abrir(nucleo, "v1", "pa_b_0", 5)
    assert [m["t_sim"] for m in kpis.mapa] == [0.0, 60.0, 120.0, 180.0]
    r = kpis.resumen()
    assert r["sin_cierre"] == 1 and r["n_sesiones"] == 0 and math.isnan(r["falsas_lib_100"])
    assert set(CLAVES_RESUMEN) <= set(r)


def test_mensaje_kpi_sin_nan_y_con_nombres_del_contrato(mundo):
    ctrl, nucleo, kpis = mundo
    ctrl.paso(0)
    m = kpis.mensaje_kpi(10.0)
    assert m["tipo"] == "kpi" and m["t_sim"] == 10.0
    assert set(m["valores"]) == {"precision_mapa", "precision_mapa_app", "libres_fantasma"}
    assert all(not math.isnan(v) for v in m["valores"].values())


def test_vehiculos_sin_app_no_se_siguen():
    ctrl = CtrlFalso()
    verdad = VerdadSUMO()
    ctrl.agregar_hook(verdad.on_paso)
    ctrl.poner("x", parqueado=True, con_app=False, puesto="pa_a_0")
    ctrl.paso(1)
    assert verdad.estacionados_app() == [] and verdad.estadia("x") == (None, None)


def _hay_pandas() -> bool:
    try:
        import pandas  # noqa: F401
    except ImportError:
        return False
    return True


# ---------------------------------------------------------------------------- con SUMO


@pytest.mark.sumo
@pytest.mark.skipif(not EN_CONTENEDOR, reason="requiere el contenedor van3twin")
def test_bit_de_suscripcion_igual_a_isStoppedParking():
    """En una corrida corta, el bit de parking de la suscripción coincide con `isStoppedParking`."""
    from traci.controlador import ConfigControlador, Controlador
    from traci.correr_kpis import preparar_escenario

    cfg = preparar_escenario(50, 1)
    comparados, estacionados = 0, 0
    with Controlador(ConfigControlador(cfg=cfg, semilla=1, etiqueta="equivalencia")) as ctrl:
        verdad = VerdadSUMO()
        ctrl.agregar_hook(verdad.on_paso)
        for _ in range(900):
            ctrl.paso()
            for veh, datos in ctrl.vehiculos.items():
                bit = estacionado(datos[ctrl.traci.constants.VAR_STOPSTATE])
                assert bit == ctrl.traci.vehicle.isStoppedParking(veh), veh
                comparados += 1
                estacionados += bit
    assert comparados > 10_000 and estacionados > 1_000  # la corrida tiene autos estacionados


@pytest.mark.sumo
@pytest.mark.skipif(not EN_CONTENEDOR, reason="requiere el contenedor van3twin")
def test_integracion_p50_rf_s2_escribe_el_json():
    """Con el RF (`.npz` versionado en `ia/modelos/`), la semilla 2 cierra su primera sesión en
    t = 1 014 s: hasta 1 200 s hay sesiones cerradas. Antes la prueba usaba s1 hasta 900 s, que solo
    cerraba sesiones porque sin el `.npz` se caía al umbral."""
    from traci.correr_kpis import SALIDAS_KPI, main

    main(["--id", "p50_rf_s2", "--hasta", "1200"])
    datos = json.loads((SALIDAS_KPI / "ejemplo_p50_rf_s2.json").read_text(encoding="utf-8"))
    assert datos["clasificador_usado"] == "rf"
    kpis = datos["kpis"]
    assert set(CLAVES_RESUMEN) <= set(kpis)
    assert kpis["n_sesiones"] > 0 and kpis["n_muestras_mapa"] == 20
    assert kpis["precision_mapa_app"] >= 0.95
