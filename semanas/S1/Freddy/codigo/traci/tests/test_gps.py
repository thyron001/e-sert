"""Emulador de GPS: ruido AR(1), pérdidas, precisión, velocidad por diferencias y etiquetas.

Son tests puros: no necesitan SUMO y corren en la computadora.
"""

import math
import statistics

import pytest

from traci.gps import (STAGE_CAMINANDO, STAGE_EN_VEHICULO, STAGE_ESPERANDO, STAGE_ESPERANDO_SALIR,
                       EmuladorGPS, conversor_plano, modo_real_persona, modo_real_vehiculo)

A_GEO = conversor_plano()
N = 20_000


def _serie(sigma=5.0, rho=0.8, semilla=7, p_perdida=0.0):
    """Errores (ex, ey) de un agente quieto en el origen durante N segundos."""
    gps = EmuladorGPS(semilla=semilla, sigma_m=sigma, p_perdida=p_perdida, rho=rho)
    ex, ey = [], []
    for t in range(N):
        gps.observar("ped_x", float(t), 0.0, 0.0, "quieto", A_GEO)
        e = gps.error_actual("ped_x")
        ex.append(e[0])
        ey.append(e[1])
    return ex, ey


def _autocorr(xs, lag=1):
    m = statistics.fmean(xs)
    num = sum((xs[i] - m) * (xs[i + lag] - m) for i in range(len(xs) - lag))
    den = sum((x - m) ** 2 for x in xs)
    return num / den


@pytest.mark.parametrize("sigma", [3.0, 5.0, 15.0])
def test_desviacion_estandar_esperada(sigma):
    """La desviación estándar del error por eje es sigma_m (±10 %)."""
    ex, ey = _serie(sigma=sigma)
    for eje in (ex, ey):
        assert statistics.pstdev(eje) == pytest.approx(sigma, rel=0.10)


def test_autocorrelacion_lag1():
    """El ruido está correlacionado en el tiempo: autocorrelación lag 1 ≈ 0,8."""
    ex, ey = _serie()
    assert _autocorr(ex) == pytest.approx(0.8, abs=0.03)
    assert _autocorr(ey) == pytest.approx(0.8, abs=0.03)
    assert _autocorr(ex, lag=5) == pytest.approx(0.8 ** 5, abs=0.05)


def test_no_es_ruido_blanco():
    ex, _ = _serie(rho=0.0)
    assert abs(_autocorr(ex)) < 0.03


def test_error_en_el_csv_coincide_con_el_proceso():
    """La posición publicada es la verdadera más el error AR(1)."""
    gps = EmuladorGPS(semilla=3, p_perdida=0.0)
    fila = gps.observar("sim_v", 0.0, 100.0, 50.0, "vehiculo", A_GEO)
    ex, ey = gps.error_actual("sim_v")
    lat, lon = A_GEO(100.0 + ex, 50.0 + ey)
    assert (fila["lat"], fila["lon"]) == (round(lat, 7), round(lon, 7))


def test_perdidas_de_muestra():
    gps = EmuladorGPS(semilla=11, p_perdida=0.02)
    filas = [gps.observar("sim_v", float(t), 0.0, 0.0, "vehiculo", A_GEO) for t in range(N)]
    perdidas = sum(f is None for f in filas) / N
    assert perdidas == pytest.approx(0.02, abs=0.005)


def test_precision_reportada():
    gps = EmuladorGPS(semilla=5, sigma_m=5.0)
    precisiones = [f["precision_m"] for t in range(2000)
                   if (f := gps.observar("sim_v", float(t), 0, 0, "vehiculo", A_GEO))]
    assert min(precisiones) >= 4.0 and max(precisiones) <= 7.5
    assert statistics.fmean(precisiones) == pytest.approx(5.0 * 1.15, rel=0.03)


def test_velocidad_por_diferencia_de_posiciones_ruidosas():
    """Sin ruido, la velocidad es la real; con ruido, un agente quieto 'se mueve' (como un teléfono)."""
    gps = EmuladorGPS(semilla=1, sigma_m=1e-9, p_perdida=0.0)
    filas = [gps.observar("sim_v", float(t), 10.0 * t, 0.0, "vehiculo", A_GEO) for t in range(5)]
    assert filas[0]["velocidad_mps"] is None
    assert all(f["velocidad_mps"] == pytest.approx(10.0, abs=1e-3) for f in filas[1:])

    ruidoso = EmuladorGPS(semilla=2, sigma_m=5.0, p_perdida=0.0)
    v = [f["velocidad_mps"] for t in range(3000)
         if (f := ruidoso.observar("ped_q", float(t), 0, 0, "quieto", A_GEO))["velocidad_mps"] is not None]
    # Diferencia de dos AR(1): σ·sqrt(2(1−ρ)) por eje → media Rayleigh ≈ 3,96 m/s.
    esperado = 5.0 * math.sqrt(2 * (1 - 0.8)) * math.sqrt(math.pi / 2)
    assert statistics.fmean(v) == pytest.approx(esperado, rel=0.08)


def test_velocidad_tras_una_perdida_usa_el_tiempo_real():
    gps = EmuladorGPS(semilla=1, sigma_m=1e-9, p_perdida=0.0)
    gps.observar("sim_v", 0.0, 0.0, 0.0, "vehiculo", A_GEO)
    gps.observar("sim_v", 3.0, 30.0, 0.0, "vehiculo", A_GEO)  # hueco de 3 s
    assert gps.observar("sim_v", 4.0, 40.0, 0.0, "vehiculo", A_GEO)["velocidad_mps"] == pytest.approx(10.0)


def test_tasa_y_olvidar():
    gps = EmuladorGPS(semilla=1, tasa_hz=0.5)
    assert gps.toca_muestra("a", 0.0)
    gps.observar("a", 0.0, 0, 0, "quieto", A_GEO)
    assert not gps.toca_muestra("a", 1.0) and gps.toca_muestra("a", 2.0)
    gps.olvidar("a")
    assert gps.toca_muestra("a", 1.0)
    with pytest.raises(ValueError):
        EmuladorGPS(semilla=1, rho=1.0)


def test_misma_semilla_mismas_trazas():
    a = EmuladorGPS(semilla=42)
    b = EmuladorGPS(semilla=42)
    for t in range(50):
        assert a.observar("x", float(t), t, 0, "a_pie", A_GEO) == b.observar("x", float(t), t, 0, "a_pie", A_GEO)


def test_etiquetas_modo_real():
    assert modo_real_vehiculo(estacionado=False) == "vehiculo"  # circulando o detenido en tráfico
    assert modo_real_vehiculo(estacionado=True) == "quieto"  # estacionado, persona adentro
    assert modo_real_persona(STAGE_CAMINANDO) == "a_pie"
    assert modo_real_persona(STAGE_ESPERANDO) == "quieto"
    assert modo_real_persona(STAGE_ESPERANDO_SALIR) == "quieto"
    assert modo_real_persona(STAGE_EN_VEHICULO) == "vehiculo"
