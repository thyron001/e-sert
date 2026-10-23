"""Regresiones de los bugs que encontró el verificador independiente (S1-2, vuelta 3)."""

import math

import pytest

from backend.nucleo.billetera import Billetera
from backend.nucleo.errores import ErrorNucleo
from backend.nucleo.ocupacion import MapaOcupacion
from backend.nucleo.sesiones import ServicioSesiones
from comun import esquemas as e

from .conftest import en

C, A = e.CodigoError, e.Aviso


def test_puesto_lleno_con_dos_servicios_sobre_la_misma_base(chico):
    """Dos procesos (p. ej. controlador TraCI y FastAPI) no pueden sobrellenar un puesto."""
    bd, bil, s1 = chico
    s2 = ServicioSesiones(bd, Billetera(bd), MapaOcupacion.desde_bd(bd))
    bil.recargar("sim_a", 5)
    bil.recargar("sim_b", 5)
    s1.iniciar("sim_a", "SIM-0001", "pa_a_0", en(0))
    with pytest.raises(ErrorNucleo) as err:
        s2.iniciar("sim_b", "SIM-0002", "pa_a_0", en(1))
    assert err.value.codigo is C.PUESTO_LLENO
    assert s2.mapa.ocupados("pa_a_0") == 1  # el mapa desactualizado se sincronizó


def test_sesion_activa_con_dos_servicios(chico):
    bd, bil, s1 = chico
    s2 = ServicioSesiones(bd, Billetera(bd), MapaOcupacion.desde_bd(bd))
    bil.recargar("sim_a", 10)
    s1.iniciar("sim_a", "SIM-0001", "pa_a_0", en(0))
    with pytest.raises(ErrorNucleo) as err:
        s2.iniciar("sim_a", "SIM-0001", "pa_b_0", en(1))
    assert err.value.codigo is C.SESION_ACTIVA


def test_indice_unico_impide_dos_abiertas(chico):
    """Aunque se salte la validación, la base rechaza una segunda sesión abierta del usuario."""
    bd, bil, srv = chico
    bil.recargar("sim_a", 10)
    srv.iniciar("sim_a", "SIM-0001", "pa_a_0", en(0))
    srv._abierta_de = lambda usuario, s: None  # simula la carrera entre consultar e insertar
    with pytest.raises(ErrorNucleo) as err:
        srv.iniciar("sim_a", "SIM-0001", "pa_b_0", en(1))
    assert err.value.codigo is C.SESION_ACTIVA
    assert bil.estado("sim_a")["retenido"] == 0.25


def test_liberar_retener_debitar_exigen_duenio(sistema):
    _, bil, srv = sistema
    bil.recargar("sim_a", 5)
    bil.recargar("sim_b", 5)
    sid = srv.iniciar("sim_a", "SIM-0001", "pa_mock0_0", en(0)).sesion_id
    for op in (bil.liberar, bil.retener, bil.debitar):
        with pytest.raises(ValueError):
            op("sim_b", 25, sid)
    assert bil.estado("sim_b") == {"saldo": 5.0, "retenido": 0.0, "disponible": 5.0, "bloqueada": False}


def test_retener_no_supera_el_disponible(sistema):
    _, bil, srv = sistema
    bil.recargar("sim_a", 5)
    sid = srv.iniciar("sim_a", "SIM-0001", "pa_mock0_0", en(0)).sesion_id
    with pytest.raises(ErrorNucleo) as err:
        bil.retener("sim_a", 100_000, sid)
    assert err.value.codigo is C.SALDO_INSUFICIENTE


def test_avisos_fuera_de_sesion(sistema):
    """§5: `saldo_bajo` también fuera de una sesión, según el disponible."""
    _, bil, srv = sistema
    assert srv.avisos_usuario("sim_nuevo") == [A.saldo_bajo]
    bil.recargar("sim_a", 5)
    assert srv.avisos_usuario("sim_a") == []
    sid = srv.iniciar("sim_a", "SIM-0001", "pa_mock0_0", en(0)).sesion_id
    srv.cerrar(sid, en(595))  # 595 → 595 min = $4.96; quedan $0.04 < costo de 10 min ($0.08)
    assert srv.avisos(sid, en(600)) == [A.saldo_bajo]


@pytest.mark.parametrize("monto", [math.nan, math.inf, "5"])
def test_recarga_no_numerica(sistema, monto):
    _, bil, _ = sistema
    with pytest.raises(ErrorNucleo) as err:
        bil.recargar("sim_a", monto)
    assert err.value.codigo is C.VALIDACION
