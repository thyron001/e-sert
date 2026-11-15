"""Mapa de ocupación según los eventos de la app y recomendación del puesto más cercano."""

import random

import pytest

from backend.nucleo.db import distancia_m
from backend.nucleo.ocupacion import InfoPuesto, MapaOcupacion
from comun import esquemas as e

from .conftest import armar, en


def _mapa():
    return MapaOcupacion([
        InfoPuesto("pa_cerca_0", -2.8973, -79.0045, "A", 1),
        InfoPuesto("pa_medio_0", -2.8980, -79.0045, "B", 2),
        InfoPuesto("pa_lejos_0", -2.9000, -79.0045, "C", 3),
    ])


def test_recomendar_elige_el_mas_cercano_libre():
    m = _mapa()
    assert m.recomendar(-2.8973, -79.0045).puesto_id == "pa_cerca_0"
    m.ocupar("pa_cerca_0")
    assert m.recomendar(-2.8973, -79.0045).puesto_id == "pa_medio_0"
    assert m.recomendar(-2.8973, -79.0045, excluir=["pa_medio_0"]).puesto_id == "pa_lejos_0"


def test_recomendar_none_si_todo_lleno():
    m = _mapa()
    for p in m.puestos.values():
        for _ in range(p.capacidad):
            m.ocupar(p.puesto_id)
    assert m.recomendar(-2.8973, -79.0045) is None
    assert m.libres_cerca(-2.8973, -79.0045, 10_000) == []


@pytest.mark.parametrize("semilla", range(5))
def test_recomendar_nunca_devuelve_puesto_lleno(semilla):
    """Llenando puestos al azar, la recomendación siempre tiene plazas libres."""
    rnd = random.Random(semilla)
    _, _, srv = armar()
    m = srv.mapa
    for _ in range(200):
        pid = rnd.choice(list(m.puestos))
        if m.hay_lugar(pid):
            m.ocupar(pid)
        r = m.recomendar(-2.897 + rnd.uniform(-0.005, 0.005), -79.004 + rnd.uniform(-0.005, 0.005))
        if r is None:
            assert all(not m.hay_lugar(p) for p in m.puestos)
        else:
            assert m.hay_lugar(r.puesto_id) and r.libres == m.libres(r.puesto_id)


def test_libres_cerca_radio_y_orden():
    m = _mapa()
    cerca = m.libres_cerca(-2.8973, -79.0045, 100)
    assert [c.puesto_id for c in cerca] == ["pa_cerca_0", "pa_medio_0"]
    assert cerca[0].distancia_m < cerca[1].distancia_m <= 100


def test_ocupar_y_liberar_con_limites():
    m = _mapa()
    m.ocupar("pa_cerca_0")
    with pytest.raises(ValueError):
        m.ocupar("pa_cerca_0")
    m.liberar("pa_cerca_0")
    with pytest.raises(ValueError):
        m.liberar("pa_cerca_0")


def test_mapa_se_reconstruye_desde_bd_y_contrato():
    bd, bil, srv = armar()
    bil.recargar("sim_v1", 5)
    srv.iniciar("sim_v1", "SIM-0001", "pa_mock3_0", en(0))
    m2 = MapaOcupacion.desde_bd(bd)
    assert m2.ocupados("pa_mock3_0") == 1 and len(m2.puestos) == 20
    puestos = m2.como_contrato()
    assert all(isinstance(p, e.Puesto) for p in puestos)
    assert {o.puesto_id: o.ocupados for o in m2.ocupacion()}["pa_mock3_0"] == 1


def test_haversine():
    # 0,001° de latitud ≈ 111,2 m
    assert distancia_m(-2.897, -79.004, -2.898, -79.004) == pytest.approx(111.19, abs=0.1)
