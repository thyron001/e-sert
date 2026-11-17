"""`traci.modelo_plano`: el RF exportado a .npz sustituye al joblib solo cuando este no carga."""
from __future__ import annotations

import types

import numpy as np
import pytest

from traci import modelo_plano as mp


def _npz_dos_hojas(ruta):
    """Un bosque de 1 árbol: x0 <= 0,5 → clase 'a_pie'; si no → 'vehiculo'."""
    np.savez_compressed(
        ruta,
        _izq=np.array([1, -1, -1]), _der=np.array([2, -1, -1]), _feat=np.array([0, 0, 0]),
        _umbral=np.array([0.5, 0.0, 0.0], dtype=np.float32),
        _valor=np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]),
        _raices=np.array([0]), classes_=np.array(["a_pie", "vehiculo"]),
        _medianas=np.array([0.7]), _prof=np.array(1), n_arboles=np.array(1))
    return ruta


def _inf(modelo):
    return types.SimpleNamespace(_cargar_modelo=lambda: modelo)


def test_bosque_npz_predice_y_rellena_nan(tmp_path):
    b = mp.BosqueNpz(_npz_dos_hojas(tmp_path / "m.npz"))
    assert list(b.predict([[0.1], [0.9], [np.nan]])) == ["a_pie", "vehiculo", "vehiculo"]


def test_usa_npz_si_el_joblib_no_carga(tmp_path, monkeypatch):
    monkeypatch.setenv("ESERT_RF_PLANO", str(_npz_dos_hojas(tmp_path / "m.npz")))
    monkeypatch.delenv("ESERT_CLASIFICADOR", raising=False)
    inf = _inf(None)
    assert mp.instalar_si_falta(inf)
    assert isinstance(inf._cargar_modelo(), mp.BosqueNpz)
    assert mp.instalar_si_falta(inf) is None  # no se envuelve dos veces


def test_respeta_el_joblib_y_el_umbral(tmp_path, monkeypatch):
    monkeypatch.setenv("ESERT_RF_PLANO", str(_npz_dos_hojas(tmp_path / "m.npz")))
    propio = object()
    inf = _inf(propio)
    mp.instalar_si_falta(inf)
    assert inf._cargar_modelo() is propio
    sin = _inf(None)
    mp.instalar_si_falta(sin)
    monkeypatch.setenv("ESERT_CLASIFICADOR", "umbral")  # se decide al llamar, no al instalar
    assert sin._cargar_modelo() is None


@pytest.mark.parametrize("hay_npz", [False])
def test_sin_npz_no_toca_la_inferencia(tmp_path, monkeypatch, hay_npz):
    monkeypatch.setenv("ESERT_RF_PLANO", str(tmp_path / "no_existe.npz"))
    inf = _inf(None)
    original = inf._cargar_modelo
    assert mp.instalar_si_falta(inf) is None
    assert inf._cargar_modelo is original
