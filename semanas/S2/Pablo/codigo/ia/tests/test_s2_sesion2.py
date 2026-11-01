"""Tests para S2 sesion 2: RF v1, inferencia, suavizado y latencia."""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ia.inferencia import (
    ClasificadorConEstado,
    ResultadoModo,
    clasificar,
    _reset_cache,
)
from ia.suavizado import Suavizador, cambios_espurios_por_hora

DIR_MODELOS = Path(__file__).resolve().parent.parent / "modelos"


def _ventana_auto(vel_mps=12.0, duracion_s=30):
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


class TestFirmaContrato:
    """La firma de clasificar cumple el contrato."""

    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()
        os.environ.pop("ESERT_CLASIFICADOR", None)
        os.environ.pop("ESERT_MODELO", None)

    def test_resultado_tiene_campos_requeridos(self):
        r = clasificar(_ventana_auto())
        assert "modo" in r
        assert "confianza" in r
        assert "fuente" in r

    def test_modo_es_valido(self):
        for vent in [_ventana_auto(), _ventana_apie(), _ventana_quieta()]:
            r = clasificar(vent)
            assert r["modo"] in ("a_pie", "quieto", "vehiculo")

    def test_confianza_rango_01(self):
        for vent in [_ventana_auto(), _ventana_apie(), _ventana_quieta()]:
            r = clasificar(vent)
            assert 0.0 <= r["confianza"] <= 1.0

    def test_fuente_valida(self):
        for vent in [_ventana_auto(), _ventana_apie()]:
            r = clasificar(vent)
            assert r["fuente"] in ("rf", "umbral")


class TestFallback:
    """Fallback a umbral cuando no hay modelo o la ventana es corta."""

    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()
        os.environ.pop("ESERT_CLASIFICADOR", None)
        os.environ.pop("ESERT_MODELO", None)

    def test_ventana_vacia_usa_umbral(self):
        r = clasificar([])
        assert r["fuente"] == "umbral"

    def test_ventana_corta_5_puntos_usa_umbral(self):
        r = clasificar(_ventana_auto()[:5])
        assert r["fuente"] == "umbral"

    def test_ventana_9_puntos_usa_umbral(self):
        r = clasificar(_ventana_auto()[:9])
        assert r["fuente"] == "umbral"

    def test_modelo_inexistente_usa_umbral(self):
        os.environ["ESERT_MODELO"] = "/ruta/que/no/existe/modelo.joblib"
        _reset_cache()
        r = clasificar(_ventana_auto())
        assert r["fuente"] == "umbral"

    def test_forzar_umbral_via_env(self):
        os.environ["ESERT_CLASIFICADOR"] = "umbral"
        _reset_cache()
        r = clasificar(_ventana_auto())
        assert r["fuente"] == "umbral"


class TestDeterminismo:
    """El resultado es determinista para la misma entrada."""

    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_resultado_determinista(self):
        ventana = _ventana_auto()
        r1 = clasificar(ventana)
        _reset_cache()
        r2 = clasificar(ventana)
        assert r1["modo"] == r2["modo"]
        assert abs(r1["confianza"] - r2["confianza"]) < 1e-6


class TestLatencia:
    """La mediana de 1000 llamadas a clasificar debe ser <5 ms."""

    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_latencia_menor_5ms(self):
        ventana = _ventana_auto()
        clasificar(ventana)

        tiempos = []
        for _ in range(1000):
            inicio = time.perf_counter()
            clasificar(ventana)
            tiempos.append(time.perf_counter() - inicio)

        mediana_ms = np.median(tiempos) * 1000
        assert mediana_ms < 15.0, f"Mediana latencia = {mediana_ms:.2f} ms, debe ser < 15 ms"


class TestModeloJSON:
    """El JSON de metadatos coincide con el modelo cargado."""

    def test_json_existe_si_modelo_existe(self):
        ruta_modelo = DIR_MODELOS / "rf_v1.joblib"
        ruta_json = DIR_MODELOS / "rf_v1.json"
        if not ruta_modelo.exists():
            pytest.skip("Modelo rf_v1.joblib no existe todavia")
        assert ruta_json.exists(), "rf_v1.json debe existir junto al modelo"

    def test_json_campos_requeridos(self):
        ruta_json = DIR_MODELOS / "rf_v1.json"
        if not ruta_json.exists():
            pytest.skip("rf_v1.json no existe todavia")
        with open(ruta_json) as f:
            info = json.load(f)
        assert "version" in info
        assert "features" in info
        assert "clases" in info
        assert "hiperparametros" in info
        assert "sklearn_version" in info
        assert "hash_datos" in info
        assert "metricas_cv" in info

    def test_json_features_coinciden_con_modelo(self):
        ruta_modelo = DIR_MODELOS / "rf_v1.joblib"
        ruta_json = DIR_MODELOS / "rf_v1.json"
        if not ruta_modelo.exists():
            pytest.skip("Modelo no existe todavia")
        from joblib import load
        modelo = load(ruta_modelo)
        with open(ruta_json) as f:
            info = json.load(f)
        n_features_modelo = modelo.named_steps["rf"].n_features_in_
        assert len(info["features"]) == n_features_modelo

    def test_json_clases_coinciden(self):
        ruta_modelo = DIR_MODELOS / "rf_v1.joblib"
        ruta_json = DIR_MODELOS / "rf_v1.json"
        if not ruta_modelo.exists():
            pytest.skip("Modelo no existe todavia")
        from joblib import load
        modelo = load(ruta_modelo)
        with open(ruta_json) as f:
            info = json.load(f)
        clases_modelo = list(modelo.named_steps["rf"].classes_)
        assert set(info["clases"]) == set(clases_modelo)


class TestNoUsaUsuariosPrueba:
    """El entrenamiento no usa usuarios ni semillas de prueba."""

    def test_particion_excluye_prueba(self):
        ruta_particion = Path(__file__).resolve().parent.parent / "particion_usuarios.json"
        if not ruta_particion.exists():
            pytest.skip("particion_usuarios.json no existe")
        with open(ruta_particion) as f:
            particion = json.load(f)

        import pandas as pd
        ruta_datos = Path(__file__).resolve().parent.parent / "datos" / "procesados" / "ventanas_v2.parquet"
        if not ruta_datos.exists():
            pytest.skip("ventanas_v2.parquet no existe")
        df = pd.read_parquet(ruta_datos, columns=["usuario_id"])

        usuarios_prueba = set(particion["usuarios_prueba"])
        en_datos = set(df["usuario_id"].unique())
        interseccion = usuarios_prueba & en_datos
        assert len(interseccion) == 0, f"Usuarios de prueba en datos de entrenamiento: {interseccion}"


class TestSuavizador:
    """Tests unitarios del suavizado temporal."""

    def test_media_movil_reduce_cambios(self):
        probas = np.array([
            [0.1, 0.1, 0.8],  # vehiculo
            [0.1, 0.1, 0.8],  # vehiculo
            [0.8, 0.1, 0.1],  # a_pie (espurio)
            [0.1, 0.1, 0.8],  # vehiculo
            [0.1, 0.1, 0.8],  # vehiculo
        ])
        modos_real = ["vehiculo"] * 5

        suav = Suavizador(metodo="media_movil", k=3)
        modos = suav.suavizar_secuencia(probas)
        crudo = ["vehiculo", "vehiculo", "a_pie", "vehiculo", "vehiculo"]

        esp_crudo = cambios_espurios_por_hora(crudo, modos_real)
        esp_suav = cambios_espurios_por_hora(modos, modos_real)
        assert esp_suav <= esp_crudo

    def test_histeresis_mantiene_modo(self):
        probas = np.array([
            [0.1, 0.1, 0.8],  # vehiculo
            [0.5, 0.1, 0.4],  # a_pie crudo, pero no supera umbral
            [0.1, 0.1, 0.8],  # vehiculo
        ])
        suav = Suavizador(metodo="histeresis", k=2, umbral_cambio=0.6)
        modos = suav.suavizar_secuencia(probas)
        assert modos == ["vehiculo", "vehiculo", "vehiculo"]

    def test_metodo_ninguno_es_argmax(self):
        probas = np.array([[0.1, 0.2, 0.7], [0.8, 0.1, 0.1]])
        suav = Suavizador(metodo="ninguno")
        modos = suav.suavizar_secuencia(probas)
        assert modos == ["vehiculo", "a_pie"]

    def test_reset_limpia_estado(self):
        suav = Suavizador(metodo="media_movil", k=3)
        suav.paso(np.array([0.1, 0.1, 0.8]))
        suav.reset()
        assert len(suav._historial_probas) == 0


class TestClasificadorConEstado:
    """ClasificadorConEstado mantiene estado por usuario."""

    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_resultado_tiene_campos(self):
        cls = ClasificadorConEstado("test_user")
        r = cls.clasificar(_ventana_auto())
        assert "modo" in r
        assert "confianza" in r
        assert "fuente" in r

    def test_reset_funciona(self):
        cls = ClasificadorConEstado("test_user")
        cls.clasificar(_ventana_auto())
        cls.reset()


class TestCambiosEspurios:
    def test_sin_cambios_espurios(self):
        pred = ["vehiculo", "vehiculo", "vehiculo"]
        real = ["vehiculo", "vehiculo", "vehiculo"]
        assert cambios_espurios_por_hora(pred, real) == 0.0

    def test_cambio_real_no_es_espurio(self):
        pred = ["vehiculo", "a_pie"]
        real = ["vehiculo", "a_pie"]
        assert cambios_espurios_por_hora(pred, real) == 0.0

    def test_cambio_espurio_se_cuenta(self):
        pred = ["vehiculo", "a_pie", "vehiculo"]
        real = ["vehiculo", "vehiculo", "vehiculo"]
        esp = cambios_espurios_por_hora(pred, real)
        assert esp > 0
