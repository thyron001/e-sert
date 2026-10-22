"""Tests para ia.inferencia.clasificar según el contrato."""
import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ia.inferencia import clasificar, _reset_cache


def _ventana_auto(vel_mps=12.0, duracion_s=30):
    """Ventana de auto a velocidad constante rumbo este."""
    grados_por_m = 1.0 / 111_320.0
    puntos = []
    lon = -79.0
    for i in range(duracion_s):
        puntos.append({
            "t": float(1_000_000_000 + i),
            "lat": -2.9,
            "lon": lon,
            "precision_m": 5.0,
        })
        lon += vel_mps * grados_por_m
    return puntos


def _ventana_apie(vel_mps=1.2, duracion_s=30):
    """Ventana de peatón a velocidad lenta."""
    grados_por_m = 1.0 / 111_320.0
    puntos = []
    lat = -2.9
    for i in range(duracion_s):
        puntos.append({
            "t": float(1_000_000_000 + i),
            "lat": lat,
            "lon": -79.0,
            "precision_m": 5.0,
        })
        lat += vel_mps * grados_por_m
    return puntos


def _ventana_quieta(duracion_s=30):
    """Ventana de punto fijo con ruido."""
    rng = np.random.default_rng(42)
    grados_por_m = 1.0 / 111_320.0
    puntos = []
    for i in range(duracion_s):
        puntos.append({
            "t": float(1_000_000_000 + i),
            "lat": -2.9 + rng.normal(0, 3 * grados_por_m),
            "lon": -79.0 + rng.normal(0, 3 * grados_por_m),
            "precision_m": 3.0,
        })
    return puntos


class TestInferenciaUmbral:
    """Tests con fallback a umbral (sin modelo RF cargado)."""

    def setup_method(self):
        _reset_cache()
        import os
        os.environ["ESERT_CLASIFICADOR"] = "umbral"

    def teardown_method(self):
        _reset_cache()
        import os
        os.environ.pop("ESERT_CLASIFICADOR", None)

    def test_auto_es_vehiculo(self):
        r = clasificar(_ventana_auto(vel_mps=12.0))
        assert r["modo"] == "vehiculo", f"Esperado vehiculo, obtuve {r['modo']}"
        assert r["fuente"] == "umbral"

    def test_peaton_es_apie(self):
        r = clasificar(_ventana_apie(vel_mps=1.2))
        assert r["modo"] == "a_pie", f"Esperado a_pie, obtuve {r['modo']}"
        assert r["fuente"] == "umbral"

    def test_modelo_ausente_usa_umbral(self):
        _reset_cache()
        import os
        os.environ.pop("ESERT_CLASIFICADOR", None)
        os.environ["ESERT_MODELO"] = "/ruta/inexistente/modelo.joblib"
        try:
            r = clasificar(_ventana_auto())
            assert r["fuente"] == "umbral"
        finally:
            os.environ.pop("ESERT_MODELO", None)
            _reset_cache()


class TestLatencia:
    def setup_method(self):
        _reset_cache()
        import os
        os.environ["ESERT_CLASIFICADOR"] = "umbral"

    def teardown_method(self):
        _reset_cache()
        import os
        os.environ.pop("ESERT_CLASIFICADOR", None)

    def test_latencia_menor_10ms(self):
        ventana = _ventana_auto()
        # Warm up
        clasificar(ventana)

        tiempos = []
        for _ in range(50):
            inicio = time.perf_counter()
            clasificar(ventana)
            tiempos.append(time.perf_counter() - inicio)

        media_ms = np.mean(tiempos) * 1000
        assert media_ms < 10, f"Latencia media = {media_ms:.2f} ms, debe ser < 10 ms"


class TestResultadoFormato:
    def setup_method(self):
        _reset_cache()
        import os
        os.environ["ESERT_CLASIFICADOR"] = "umbral"

    def teardown_method(self):
        _reset_cache()
        import os
        os.environ.pop("ESERT_CLASIFICADOR", None)

    def test_formato_resultado(self):
        r = clasificar(_ventana_auto())
        assert "modo" in r
        assert "confianza" in r
        assert "fuente" in r
        assert r["modo"] in ("a_pie", "quieto", "vehiculo")
        assert 0 <= r["confianza"] <= 1
        assert r["fuente"] in ("rf", "umbral")

    def test_ventana_corta_usa_umbral(self):
        puntos = _ventana_auto()[:10]
        r = clasificar(puntos)
        assert r["fuente"] == "umbral"
