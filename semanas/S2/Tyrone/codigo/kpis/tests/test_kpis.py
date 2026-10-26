"""Tests de kpis.lectores y kpis.kpis con XML sintéticos en formato SUMO.

Cada test lee un XML de `tests/datos/` con los lectores y luego aplica las
funciones puras, comparando con valores calculados a mano.
"""
import math

import pandas as pd
import pytest

from kpis import kpis, lectores


def _ruta_de(df, vid):
    """Filas de leer_vehroutes de un vehículo, ordenadas por `orden`."""
    return df[df["id"] == vid].sort_values("orden").reset_index(drop=True)


def _inicio_parqueo(stops, vid):
    """Instante `started` de la parada en parkingArea del vehículo."""
    return float(stops.loc[stops["id"] == vid, "started"].iloc[0])


# ---------------------------------------------------------------------------
# Obligatorios
# ---------------------------------------------------------------------------

def test_busqueda_a_la_primera(datos):
    """Entra a eObj (100 m) en t=10 y estaciona en t=15 sin salir del edge.

    Esperado: inicio 10, tiempo de búsqueda 5 s, distancia 0 m.
    """
    rutas = lectores.leer_vehroutes(datos / "vehroutes.xml")
    stops = lectores.leer_stops(datos / "stops.xml")
    ruta = _ruta_de(rutas, "v1")
    longitudes = {"e0": 100.0, "eObj": 100.0}

    inicio = kpis.inicio_busqueda(ruta, {"eObj"})
    fin = _inicio_parqueo(stops, "v1")

    assert inicio == pytest.approx(10.0)
    assert fin - inicio == pytest.approx(5.0)
    assert kpis.distancia_busqueda_m(ruta, inicio, fin, longitudes) == pytest.approx(0.0)


def test_vuelta_de_tres_edges(datos):
    """Ruta e0 e1 e2 e3 e1, exitTimes 100 110 120 130 (el último e1 sin salida).

    Objetivo e1, estaciona en 135. Esperado: inicio 100, tiempo 35 s y
    distancia 300 m (e1 + e2 + e3; el e1 final no se cuenta).
    """
    rutas = lectores.leer_vehroutes(datos / "vehroutes.xml")
    stops = lectores.leer_stops(datos / "stops.xml")
    ruta = _ruta_de(rutas, "v2")

    # Se usa la última <route> hija directa del vehicle, no la de routeDistribution.
    assert list(ruta["edge"]) == ["e0", "e1", "e2", "e3", "e1"]
    assert list(ruta["salida"].iloc[:4]) == pytest.approx([100.0, 110.0, 120.0, 130.0])
    assert math.isnan(ruta["salida"].iloc[4])
    assert float(ruta["depart"].iloc[0]) == pytest.approx(90.0)

    longitudes = {"e0": 100.0, "e1": 100.0, "e2": 100.0, "e3": 100.0}
    inicio = kpis.inicio_busqueda(ruta, {"e1"})
    fin = _inicio_parqueo(stops, "v2")

    assert inicio == pytest.approx(100.0)
    assert fin == pytest.approx(135.0)
    assert fin - inicio == pytest.approx(35.0)
    assert kpis.distancia_busqueda_m(ruta, inicio, fin, longitudes) == pytest.approx(300.0)


def test_inicio_busqueda_en_primer_edge_y_nunca(datos):
    """Si el objetivo es el primer edge, el inicio es `depart`; si no aparece, None."""
    ruta = _ruta_de(lectores.leer_vehroutes(datos / "vehroutes.xml"), "v2")
    assert kpis.inicio_busqueda(ruta, {"e0"}) == pytest.approx(90.0)
    assert kpis.inicio_busqueda(ruta, {"no_existe"}) is None


def test_ocupacion_solapada(datos):
    """Estancias [0,120) y [60,180), capacidad 2, fin 240, paso 60.

    Esperado: t = [0, 60, 120, 180], ocupados = [1, 2, 1, 0].
    """
    stops = lectores.leer_stops(datos / "ocupacion.xml")
    serie = kpis.serie_ocupacion(stops, capacidad_total=2, fin=240, paso_s=60)

    assert list(serie["t"]) == [0, 60, 120, 180]
    assert list(serie["ocupados"]) == [1, 2, 1, 0]
    assert list(serie["ocupacion"]) == pytest.approx([0.5, 1.0, 0.5, 0.0])


def test_ocupacion_ended_menos_uno(datos):
    """Una estancia con ended=-1 (desde t=60) se toma como abierta hasta el fin.

    Con otra estancia [0,60): ocupados = [1, 1, 1, 1] en t = [0, 60, 120, 180].
    """
    stops = lectores.leer_stops(datos / "ocupacion_abierta.xml")
    assert (stops["ended"] < 0).any()
    serie = kpis.serie_ocupacion(stops, capacidad_total=2, fin=240, paso_s=60)

    assert list(serie["t"]) == [0, 60, 120, 180]
    assert list(serie["ocupados"]) == [1, 1, 1, 1]
    assert list(serie["ocupacion"]) == pytest.approx([0.5, 0.5, 0.5, 0.5])


def test_co2_tres_periodos(datos):
    """v1 emite 1000 mg/s en t=0,10,20 (y en t=30, fuera del intervalo).

    Con inicio 0, fin 30 y periodo 10: 3 * 1000 mg/s * 10 s = 30 g.
    v2 (5000 mg/s) no debe contar.
    """
    todas = lectores.leer_emisiones(datos / "emisiones.xml")
    assert set(todas["id"]) == {"v1", "v2"}

    emis = lectores.leer_emisiones(datos / "emisiones.xml", ids={"v1"})
    assert set(emis["id"]) == {"v1"}
    assert len(emis) == 4

    assert kpis.co2_busqueda_g(emis, 0.0, 30.0, periodo_s=10.0) == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# Extra
# ---------------------------------------------------------------------------

def test_leer_red_ignora_internos(datos):
    """leer_red descarta edges con function="internal" y usa el primer lane."""
    red = lectores.leer_red(datos / "red.net.xml")
    assert set(red["edge"]) == {"e_cerca", "e_lejos"}

    cerca = red[red["edge"] == "e_cerca"].iloc[0]
    assert cerca["longitud"] == pytest.approx(100.0)
    assert [tuple(p) for p in cerca["forma"]] == [(0.0, 0.0), (100.0, 0.0)]


def test_edges_cerca(datos):
    """Punto (50, 50): e_cerca a 50 m entra en radio 100; e_lejos a 500 m no."""
    red = lectores.leer_red(datos / "red.net.xml")
    assert kpis.edges_cerca(red, 50.0, 50.0, 100.0) == {"e_cerca"}
    assert kpis.edges_cerca(red, 50.0, 50.0, 10.0) == set()


def test_leer_stops_descarta_sin_parking_area(datos):
    """La parada del bus (sin parkingArea) no aparece; ended=-1 se conserva."""
    stops = lectores.leer_stops(datos / "stops.xml")
    assert set(stops["id"]) == {"v1", "v2"}
    assert set(stops["parkingArea"]) == {"pa1", "pa2"}
    assert float(stops.loc[stops["id"] == "v2", "ended"].iloc[0]) == pytest.approx(-1.0)


def test_leer_demanda_params(datos):
    """Lee los params de <trip>; un <vehicle> sin params queda con cadenas vacías."""
    dem = lectores.leer_demanda(datos / "demanda.rou.xml").set_index("id")
    assert dem.loc["busca1", "clase"] == "buscador"
    assert dem.loc["busca1", "con_app"] == "si"
    assert dem.loc["busca1", "destino"] == "catedral"
    assert dem.loc["busca1", "pa_objetivo"] == "pa1"
    for col in ("clase", "con_app", "destino", "pa_objetivo"):
        assert dem.loc["paso1", col] == ""


def test_leer_tripinfo(datos):
    """Lee los campos numéricos básicos de tripinfo."""
    trip = lectores.leer_tripinfo(datos / "tripinfo.xml")
    fila = trip.iloc[0]
    assert fila["id"] == "v1"
    assert fila["depart"] == pytest.approx(0.0)
    assert fila["arrival"] == pytest.approx(60.0)
    assert fila["duration"] == pytest.approx(60.0)
    assert fila["routeLength"] == pytest.approx(195.0)


def test_resumen_estadistico():
    """Media 4, mediana 3; el IC95 bootstrap contiene la media; p90 en rango."""
    r = kpis.resumen_estadistico([1, 2, 3, 4, 10], n_boot=500, semilla=0)
    assert r["n"] == 5
    assert r["media"] == pytest.approx(4.0)
    assert r["mediana"] == pytest.approx(3.0)
    assert r["mediana"] <= r["p90"] <= 10
    lo, hi = r["ic95"]
    assert lo <= r["media"] <= hi

    # Reproducible con la misma semilla.
    assert kpis.resumen_estadistico([1, 2, 3, 4, 10], n_boot=500, semilla=0)["ic95"] == \
        pytest.approx(r["ic95"])


def test_resumen_estadistico_vacio():
    """Sin valores, todas las métricas son None."""
    r = kpis.resumen_estadistico([])
    for clave in ("media", "mediana", "p90", "ic95"):
        assert r[clave] is None
    assert r["n"] in (0, None)


def test_exit_times_negativos_son_no_recorridos(tmp_path):
    """SUMO escribe -1 en los edges que un vehículo sin terminar aún no ha dejado."""
    ruta = tmp_path / "vehroutes.xml"
    ruta.write_text('<routes><vehicle id="v9" depart="100.00">'
                    '<route edges="a b c" exitTimes="110.00 -1 -1"/></vehicle></routes>',
                    encoding="utf-8")
    rutas = lectores.leer_vehroutes(ruta)
    assert rutas["salida"].isna().tolist() == [False, True, True]
    # El edge objetivo "c" nunca se alcanzó: no hay inicio de búsqueda (antes daba -1)
    assert kpis.inicio_busqueda(rutas, {"c"}) is None
