"""Tarifa del núcleo (regla 3 de cobro: fracciones de 5 min con mínimo de 10 min)."""

import pytest

from backend.nucleo import tarifa as tar


@pytest.mark.parametrize("reales,cobrados", [(12, 15), (3, 10), (0, 10), (10, 10), (30, 30), (47, 50), (120, 120)])
def test_minutos_cobrables(reales, cobrados):
    assert tar.minutos_cobrables(reales) == cobrados


def test_costo_y_retencion():
    assert tar.costo(12) == 0.13  # 15 min · 0,50/60 = 0,125 → 0,13
    assert tar.costo(3) == 0.08  # mínimo 10 min
    assert tar.costo(47) == 0.42
    assert tar.retencion() == 0.25
    assert tar.costo_en_curso(12.5) == 0.10


@pytest.mark.parametrize("reales,usd", [(1, 0.25), (30, 0.25), (31, 0.50), (60, 0.50), (61, 0.75), (120, 1.00)])
def test_tarjeta_sert_bloques_30(reales, usd):
    assert tar.costo_tarjeta_sert(reales) == usd


def test_tarjeta_nunca_cobra_menos_que_real():
    for decimas in range(10, 1201):
        m = decimas / 10
        assert tar.costo_tarjeta_sert(m) >= tar.costo(m)


def test_centavos_ida_y_vuelta():
    assert tar.centavos(0.125) == 13
    assert tar.usd(tar.centavos(4.58)) == 4.58
