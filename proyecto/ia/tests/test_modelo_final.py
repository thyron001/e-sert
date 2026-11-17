"""Tests del modelo congelado `rf_final` (S4-1): hash, salidas golden, robustez, latencia, fallback y no fuga."""
import hashlib
import json
import logging
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ia import inferencia
from ia.caracteristicas import NOMBRES_FEATURES
from ia.inferencia import clasificar, _reset_cache

MODELOS = Path(inferencia.DIR_MODELOS)
JOBLIB = MODELOS / "rf_final.joblib"
META = json.loads((MODELOS / "rf_final.json").read_text())
GOLDEN = json.loads((Path(__file__).parent / "datos" / "ventanas_golden.json").read_text())
PARTICION = json.loads((Path(__file__).resolve().parent.parent / "particion_usuarios.json").read_text())
DATOS_ENTRENAMIENTO = Path(__file__).resolve().parent.parent / "reportes" / "entrenamiento_final_datos.json"


@pytest.fixture(autouse=True)
def _limpio(monkeypatch):
    monkeypatch.delenv("ESERT_MODELO", raising=False)
    monkeypatch.delenv("ESERT_CLASIFICADOR", raising=False)
    _reset_cache()
    yield
    _reset_cache()


def sha256(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


class TestMeta:
    def test_hash_del_archivo_coincide_con_el_json(self):
        assert sha256(JOBLIB) == META["sha256_modelo"]

    def test_campos_del_json(self):
        import sklearn

        assert META["congelado"] is True
        assert META["sklearn_version"] == sklearn.__version__
        assert META["features"] == NOMBRES_FEATURES
        assert META["clases"] == ["a_pie", "quieto", "vehiculo"]
        assert META["ventana_s"] == 30 and META["paso_s"] == 5
        assert META["suavizado"] == {"metodo": "mayoria", "k": 1}
        assert {"cobertura_min", "hueco_max_s", "puntos_min"} <= set(META["fallback"])
        assert META["hiperparametros"]["random_state"] == 42
        assert META["fecha"] and META["metricas"] and META["entrenamiento"]["sha256_entradas"]
        assert all(len(h) == 64 for h in META["entrenamiento"]["sha256_entradas"].values())

    def test_requirements_fija_la_version_de_sklearn(self):
        req = (Path(__file__).resolve().parent.parent / "requirements.txt").read_text()
        assert f"scikit-learn=={META['sklearn_version']}" in req

    def test_reproducibilidad_registrada(self):
        assert META["reproducibilidad"]["sha256_iguales"] is True

    def test_tamano_menor_de_50_mb(self):
        assert JOBLIB.stat().st_size < 50e6


class TestGolden:
    def test_30_ventanas_10_por_clase_con_3_de_trafico_lento(self):
        assert len(GOLDEN) == 30
        for clase in ("a_pie", "quieto", "vehiculo"):
            assert sum(g["modo_real"] == clase for g in GOLDEN) == 10
        assert sum(g["contexto"] == "sumo_trafico_lento" for g in GOLDEN) == 3

    def test_salidas_identicas_a_las_guardadas(self):
        for g in GOLDEN:
            r = clasificar(g["ventana"])
            e = g["esperado"]
            assert r["modo"] == e["modo"] and r["fuente"] == e["fuente"], g["id"]
            assert r["confianza"] == pytest.approx(e["confianza"], abs=1e-9), g["id"]

    def test_carga_rf_final_por_defecto(self):
        assert inferencia._cargar_modelo() is not None
        assert clasificar(GOLDEN[0]["ventana"])["fuente"] == "rf"


class TestRobustez:
    def test_ventana_con_huecos(self):
        v = [p for i, p in enumerate(GOLDEN[0]["ventana"]) if not 8 <= i < 20]
        r = clasificar(v)
        assert r["modo"] in {"a_pie", "quieto", "vehiculo"} and 0 <= r["confianza"] <= 1

    def test_un_punto_y_vacia(self):
        assert clasificar(GOLDEN[0]["ventana"][:1])["confianza"] == 0.0
        assert clasificar([])["confianza"] == 0.0


class TestLatencia:
    def test_p99_menor_de_5_ms(self):
        ventanas = [g["ventana"] for g in GOLDEN] * 34
        for v in ventanas[:50]:
            clasificar(v)
        ms = []
        for v in ventanas:
            t0 = time.perf_counter_ns()
            clasificar(v)
            ms.append((time.perf_counter_ns() - t0) / 1e6)
        assert np.percentile(ms, 99) < 5.0


class TestFallback:
    def test_hash_distinto_cae_al_umbral_con_aviso_en_el_log(self, tmp_path, monkeypatch, caplog):
        malo = tmp_path / "rf_final.joblib"
        shutil.copy(JOBLIB, malo)
        shutil.copy(MODELOS / "rf_final.json", tmp_path / "rf_final.json")
        datos = bytearray(malo.read_bytes())
        datos[len(datos) // 2] ^= 0xFF
        malo.write_bytes(bytes(datos))
        monkeypatch.setenv("ESERT_MODELO", str(malo))
        _reset_cache()
        with caplog.at_level(logging.WARNING, logger="ia.inferencia"):
            r = clasificar(GOLDEN[0]["ventana"])
        assert r["fuente"] == "umbral"
        assert any("SHA-256" in m for m in caplog.messages)

    def test_modelo_ausente_cae_al_umbral(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setenv("ESERT_MODELO", str(tmp_path / "no_existe.joblib"))
        _reset_cache()
        with caplog.at_level(logging.WARNING, logger="ia.inferencia"):
            assert clasificar(GOLDEN[0]["ventana"])["fuente"] == "umbral"
        assert caplog.messages

    def test_sin_hash_de_referencia_cae_al_umbral(self, tmp_path, monkeypatch):
        shutil.copy(JOBLIB, tmp_path / "rf_final.joblib")
        meta = dict(META)
        meta.pop("sha256_modelo")
        (tmp_path / "rf_final.json").write_text(json.dumps(meta))
        monkeypatch.setenv("ESERT_MODELO", str(tmp_path / "rf_final.joblib"))
        _reset_cache()
        assert clasificar(GOLDEN[0]["ventana"])["fuente"] == "umbral"


class TestNoFuga:
    def test_usuarios_de_prueba_y_semillas_101_105_no_entran(self):
        assert not set(META["entrenamiento"]["semillas_sumo"]) & set(PARTICION["semillas_sumo_prueba"])
        if DATOS_ENTRENAMIENTO.exists():
            usuarios = set(json.loads(DATOS_ENTRENAMIENTO.read_text()).get("usuarios_geolife", []))
            assert usuarios and not usuarios & set(PARTICION["usuarios_prueba"])

    def test_ventanas_de_entrenamiento_si_estan_disponibles(self):
        ruta = Path(__file__).resolve().parent.parent / "datos" / "procesados" / "ventanas_final.parquet"
        if not ruta.exists():
            pytest.skip("ventanas_final.parquet no esta (se regenera con ia.datos.construir_entrenamiento_final)")
        import pandas as pd

        df = pd.read_parquet(ruta, columns=["usuario_id", "origen", "semilla_sumo"])
        geo = df[df["origen"] == "geolife"]
        sumo = df[df["origen"] == "sumo"]
        assert not set(geo["usuario_id"]) & set(PARTICION["usuarios_prueba"])
        assert not set(sumo["semilla_sumo"].astype(int)) & set(PARTICION["semillas_sumo_prueba"])
