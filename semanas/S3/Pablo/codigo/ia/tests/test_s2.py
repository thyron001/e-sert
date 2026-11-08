"""Tests de S2-1: partición, ruido AR(1), no fuga, hash."""
import json
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DIR_IA = Path(__file__).resolve().parents[1]
RUTA_PARTICION = DIR_IA / "particion_usuarios.json"
DIR_DATOS = DIR_IA / "datos" / "procesados"


@pytest.fixture
def particion():
    with open(RUTA_PARTICION) as f:
        return json.load(f)


class TestParticion:
    def test_hash_no_cambia(self, particion):
        h = hashlib.sha256(
            json.dumps(sorted(particion["usuarios_prueba"]), ensure_ascii=False).encode()
        ).hexdigest()
        assert h == particion["hash_usuarios_prueba"]

    def test_semillas_sumo_reservadas(self, particion):
        assert particion["semillas_sumo_prueba"] == [101, 102, 103, 104, 105]

    def test_20_porciento(self, particion):
        total = particion["n_prueba"] + particion["n_entrenamiento"]
        ratio = particion["n_prueba"] / total
        assert 0.15 <= ratio <= 0.25

    def test_minutos_prueba(self, particion):
        for clase in ["a_pie", "vehiculo", "quieto"]:
            assert particion["minutos_prueba_por_clase"].get(clase, 0) >= 60


class TestRuidoAR1:
    def test_sigma_reproducible(self):
        from ia.ruido import aplicar_ruido_ar1
        rng = np.random.default_rng(42)
        n = 10000
        df = pd.DataFrame({
            "usuario_id": ["u1"] * n,
            "t": np.arange(n, dtype=float),
            "lat": np.full(n, -2.897),
            "lon": np.full(n, -79.004),
            "precision_m": np.full(n, np.nan),
            "velocidad_mps": np.zeros(n),
            "modo_real": ["a_pie"] * n,
        })
        sigma = 8.0
        out = aplicar_ruido_ar1(df, sigma_m=sigma, rho=0.8, p_perdida=0.0, semilla=42)
        dlat_m = (out["lat"].values - df["lat"].values[:len(out)]) * 111320
        sigma_emp = np.std(dlat_m)
        assert abs(sigma_emp - sigma) / sigma < 0.10, f"σ empírico={sigma_emp:.2f}, esperado≈{sigma}"

    def test_rho_reproducible(self):
        from ia.ruido import aplicar_ruido_ar1
        n = 10000
        df = pd.DataFrame({
            "usuario_id": ["u1"] * n,
            "t": np.arange(n, dtype=float),
            "lat": np.full(n, -2.897),
            "lon": np.full(n, -79.004),
            "precision_m": np.full(n, np.nan),
            "velocidad_mps": np.zeros(n),
            "modo_real": ["a_pie"] * n,
        })
        rho = 0.8
        out = aplicar_ruido_ar1(df, sigma_m=5.0, rho=rho, p_perdida=0.0, semilla=42)
        dlat_m = (out["lat"].values - df["lat"].values[:len(out)]) * 111320
        rho_emp = np.corrcoef(dlat_m[:-1], dlat_m[1:])[0, 1]
        assert abs(rho_emp - rho) < 0.05, f"ρ empírico={rho_emp:.3f}, esperado≈{rho}"


class TestNoFuga:
    def test_v2_sin_usuarios_prueba(self, particion):
        ruta = DIR_DATOS / "ventanas_v2.parquet"
        if not ruta.exists():
            pytest.skip("ventanas_v2.parquet no generado")
        df = pd.read_parquet(ruta, columns=["usuario_id"])
        usuarios_prueba = set(particion["usuarios_prueba"])
        fuga = set(df["usuario_id"].unique()) & usuarios_prueba
        assert not fuga, f"Usuarios de prueba en v2: {fuga}"

    def test_v2_sin_semillas_sumo_prueba(self, particion):
        ruta = DIR_DATOS / "ventanas_v2.parquet"
        if not ruta.exists():
            pytest.skip("ventanas_v2.parquet no generado")
        df = pd.read_parquet(ruta, columns=["usuario_id"])
        semillas_prueba = particion["semillas_sumo_prueba"]
        ids_sumo = [u for u in df["usuario_id"].unique() if u.startswith("sumo_")]
        for uid in ids_sumo:
            for s in semillas_prueba:
                assert f"_s{s}_" not in uid, f"Semilla de prueba {s} en v2: {uid}"

    def test_ventanas_no_mezclan_grupos(self):
        ruta = DIR_DATOS / "ventanas_v2.parquet"
        if not ruta.exists():
            pytest.skip("ventanas_v2.parquet no generado")
        df = pd.read_parquet(ruta, columns=["usuario_id", "grupo"])
        assert (df["usuario_id"] == df["grupo"]).all()


class TestPrueba:
    def test_prueba_solo_usuarios_prueba(self, particion):
        ruta = DIR_DATOS / "ventanas_prueba_geolife.parquet"
        if not ruta.exists():
            pytest.skip("ventanas_prueba_geolife.parquet no generado")
        df = pd.read_parquet(ruta, columns=["usuario_id"])
        usuarios_prueba = set(particion["usuarios_prueba"])
        assert set(df["usuario_id"].unique()).issubset(usuarios_prueba)

    def test_prueba_sin_aumentar(self, particion):
        ruta = DIR_DATOS / "ventanas_prueba_geolife.parquet"
        if not ruta.exists():
            pytest.skip("ventanas_prueba_geolife.parquet no generado")
        df = pd.read_parquet(ruta, columns=["aumentada"])
        assert not df["aumentada"].any()
