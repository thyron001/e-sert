"""Tests de ia.analisis_errores: bins, recall a mano, tipo de error y segmentacion."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ia.analisis_errores import (SIN_DATO, _segmentar_por_modo, bin_precision, bin_velocidad,
                                 clasificar_error, matriz_confusion, metricas_por_clase)

M = 1.0 / 111_320.0


@pytest.mark.parametrize("kmh,esperado", [
    (0.0, "0-3"), (2.99, "0-3"), (3.0, "3-8"), (7.99, "3-8"), (8.0, "8-15"),
    (14.99, "8-15"), (15.0, ">15"), (200.0, ">15"), (np.nan, SIN_DATO), (-1.0, SIN_DATO),
])
def test_bins_velocidad(kmh, esperado):
    assert bin_velocidad(kmh) == esperado


@pytest.mark.parametrize("m,esperado", [
    (0.0, "<10"), (9.99, "<10"), (10.0, "10-25"), (24.9, "10-25"), (25.0, ">25"), (np.nan, SIN_DATO), (None, SIN_DATO),
])
def test_bins_precision(m, esperado):
    assert bin_precision(m) == esperado


def test_recall_y_precision_a_mano():
    real = ["vehiculo"] * 4 + ["quieto"] * 2 + ["a_pie"] * 2
    pred = ["vehiculo", "vehiculo", "vehiculo", "a_pie", "quieto", "a_pie", "a_pie", "vehiculo"]
    m = matriz_confusion(real, pred)
    assert m.loc["vehiculo", "vehiculo"] == 3 and m.loc["vehiculo", "a_pie"] == 1
    met = metricas_por_clase(real, pred).set_index("clase")
    assert met.loc["vehiculo", "recall"] == pytest.approx(3 / 4)
    assert met.loc["vehiculo", "precision"] == pytest.approx(3 / 4)
    assert met.loc["quieto", "recall"] == pytest.approx(1 / 2)
    assert met.loc["quieto", "precision"] == pytest.approx(1.0)
    assert met.loc["a_pie", "recall"] == pytest.approx(1 / 2)
    assert met.loc["a_pie", "precision"] == pytest.approx(1 / 3)


def test_clase_sin_datos_da_nan_no_error():
    met = metricas_por_clase([], []).set_index("clase")
    assert met["n_clase"].sum() == 0 and met["recall"].isna().all()


def _ventana(vel, n=30):
    return np.column_stack([np.arange(n, dtype=float), -2.9 + vel * np.arange(n) * M,
                            np.full(n, -79.0), np.full(n, 5.0)])


def test_tipo_de_error():
    assert clasificar_error("vehiculo", _ventana(0.0))[0] == "error_de_etiqueta"
    assert clasificar_error("vehiculo", _ventana(10.0))[0] == "error_del_modelo"
    assert clasificar_error("quieto", _ventana(5.0))[0] == "error_de_etiqueta"
    assert clasificar_error("quieto", _ventana(0.0))[0] == "error_del_modelo"
    # con sigma = 15 m, un desplazamiento de 45 m cae dentro del ruido (umbral 60 m)
    assert clasificar_error("quieto", _ventana(1.5), sigma=15)[0] == "error_del_modelo"
    assert clasificar_error("quieto", _ventana(1.5), sigma=5)[0] == "error_de_etiqueta"
    assert clasificar_error("a_pie", _ventana(8.0))[0] == "error_de_etiqueta"
    assert clasificar_error("a_pie", _ventana(1.4))[0] == "error_del_modelo"


def test_segmentar_por_modo_corta_en_cambios_y_huecos():
    d = pd.DataFrame({
        "usuario_id": ["u"] * 6 + ["v"] * 2,
        "t": [0, 1, 2, 3, 4, 30, 0, 1],
        "modo_real": ["a_pie", "a_pie", "quieto", "quieto", "a_pie", "a_pie", "a_pie", "a_pie"],
    })
    s = _segmentar_por_modo(d)
    u = s[s.usuario_id == "u"]
    assert u["segmento_id"].nunique() == 4  # a_pie | quieto | a_pie | (hueco) a_pie
    assert s[s.usuario_id == "v"]["segmento_id"].nunique() == 1
