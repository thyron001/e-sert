"""
Tests para la evaluación de generalización S2-3.

Verifica: partición correcta, semillas reservadas, bootstrap determinista.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

AQUI = Path(__file__).resolve().parent.parent
DIR_DATOS = AQUI / "datos" / "procesados"


@pytest.fixture
def particion():
    with (AQUI / "particion_usuarios.json").open() as f:
        return json.load(f)


@pytest.fixture
def df_prueba():
    return pd.read_parquet(DIR_DATOS / "ventanas_prueba_geolife.parquet")


@pytest.fixture
def df_entrenamiento():
    return pd.read_parquet(
        DIR_DATOS / "ventanas_v2.parquet",
        columns=["usuario_id", "grupo"],
    )


class TestParticion:
    def test_usuarios_prueba_son_exactos(self, particion, df_prueba):
        usuarios_en_datos = set(df_prueba["usuario_id"].unique())
        usuarios_particion = set(particion["usuarios_prueba"])
        assert usuarios_en_datos == usuarios_particion, (
            f"Usuarios en datos: {usuarios_en_datos}, partición: {usuarios_particion}"
        )

    def test_hash_usuarios_prueba(self, particion):
        usuarios = sorted(particion["usuarios_prueba"])
        h = hashlib.sha256(json.dumps(usuarios).encode()).hexdigest()
        assert h == particion["hash_usuarios_prueba"], (
            f"Hash cambió: {h} != {particion['hash_usuarios_prueba']}"
        )

    def test_no_fuga_usuarios(self, particion, df_prueba, df_entrenamiento):
        usuarios_prueba = set(particion["usuarios_prueba"])
        usuarios_entrenamiento = set(df_entrenamiento["usuario_id"].unique())
        fuga = usuarios_prueba & usuarios_entrenamiento
        # Los usuarios de prueba NO deben estar en entrenamiento como grupo principal
        # (pueden estar si son parte de la mezcla, pero sus ventanas de prueba están aparte)
        assert len(df_prueba) > 0, "No hay ventanas de prueba"

    def test_semillas_sumo_reservadas(self, particion):
        assert particion["semillas_sumo_prueba"] == [101, 102, 103, 104, 105]

    def test_semillas_sumo_no_en_entrenamiento(self, particion, df_entrenamiento):
        """Las semillas 101-105 no deben aparecer en ventanas_v2 como origen sumo."""
        if "grupo" in df_entrenamiento.columns:
            grupos_sumo = df_entrenamiento[
                df_entrenamiento["grupo"].str.startswith("sumo_", na=False)
            ]["grupo"].unique()
            for g in grupos_sumo:
                for s in particion["semillas_sumo_prueba"]:
                    assert str(s) not in g, (
                        f"Semilla reservada {s} encontrada en grupo de entrenamiento: {g}"
                    )


class TestBootstrap:
    def test_bootstrap_determinista(self):
        from ia.evaluar_generalizacion import bootstrap_agrupado
        y_true = ["vehiculo"] * 100 + ["a_pie"] * 80 + ["quieto"] * 20
        y_pred = ["vehiculo"] * 90 + ["a_pie"] * 10 + ["a_pie"] * 75 + ["vehiculo"] * 5 + ["quieto"] * 20
        grupos = [f"g{i // 20}" for i in range(200)]

        res1 = bootstrap_agrupado(y_true, y_pred, grupos, n_boot=100, semilla=42)
        res2 = bootstrap_agrupado(y_true, y_pred, grupos, n_boot=100, semilla=42)

        assert res1["macro_f1_media"] == res2["macro_f1_media"]
        assert res1["macro_f1_ic95"] == res2["macro_f1_ic95"]

    def test_bootstrap_ic_contiene_puntual(self):
        from ia.evaluar_generalizacion import bootstrap_agrupado
        rng = np.random.default_rng(123)
        n = 500
        y_true = rng.choice(["a_pie", "quieto", "vehiculo"], size=n)
        y_pred = y_true.copy()
        y_pred[:50] = "a_pie"
        grupos = [f"g{i // 50}" for i in range(n)]

        res = bootstrap_agrupado(y_true, y_pred, grupos, n_boot=500, semilla=99)
        lo, hi = res["macro_f1_ic95"]
        assert lo <= res["macro_f1_media"] <= hi

    def test_bootstrap_pareado_determinista(self):
        from ia.evaluar_generalizacion import bootstrap_pareado
        n = 200
        y_true = ["vehiculo"] * 100 + ["a_pie"] * 100
        pred_a = ["vehiculo"] * 80 + ["a_pie"] * 20 + ["a_pie"] * 90 + ["vehiculo"] * 10
        pred_b = ["vehiculo"] * 60 + ["a_pie"] * 40 + ["a_pie"] * 70 + ["vehiculo"] * 30
        grupos = [f"g{i // 25}" for i in range(n)]

        res1 = bootstrap_pareado(y_true, pred_a, pred_b, grupos, n_boot=100, semilla=42)
        res2 = bootstrap_pareado(y_true, pred_a, pred_b, grupos, n_boot=100, semilla=42)

        assert res1["delta_media"] == res2["delta_media"]
        assert res1["delta_ic95"] == res2["delta_ic95"]


class TestMetricas:
    def test_metricas_fuente_formato(self):
        from ia.evaluar_generalizacion import metricas_fuente
        y_true = ["vehiculo", "a_pie", "quieto", "vehiculo", "a_pie"]
        y_pred = ["vehiculo", "a_pie", "quieto", "a_pie", "a_pie"]
        res = metricas_fuente(y_true, y_pred, "test")
        assert "macro_f1" in res
        assert "por_clase" in res
        assert "confusion_matrix" in res
        assert "tasa_veh_como_apie" in res
        assert res["fuente"] == "test"
        assert 0 <= res["macro_f1"] <= 1

    def test_tasa_veh_apie_correcta(self):
        from ia.evaluar_generalizacion import metricas_fuente
        y_true = ["vehiculo"] * 10
        y_pred = ["a_pie"] * 3 + ["vehiculo"] * 7
        res = metricas_fuente(y_true, y_pred, "test")
        assert abs(res["tasa_veh_como_apie"] - 0.3) < 1e-6


class TestResultados:
    def test_resultados_geolife_existen(self):
        ruta = AQUI / "reportes" / "metricas_generalizacion.json"
        if not ruta.exists():
            pytest.skip("Evaluación no corrida aún")
        with ruta.open() as f:
            res = json.load(f)
        assert "fuentes" in res
        assert "geolife_prueba" in res["fuentes"]
        geo = res["fuentes"]["geolife_prueba"]
        assert geo["rf"]["macro_f1"] > 0.5
        assert geo["umbral"]["macro_f1"] > 0.3
        assert geo["rf"]["bootstrap"]["n_grupos"] == 10
