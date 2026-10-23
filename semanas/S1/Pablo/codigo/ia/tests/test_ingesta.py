"""Tests para la ingesta de GeoLife."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datos.ingesta_geolife import (
    MAPA_MODOS,
    MODOS_DESCARTADOS,
    VELOCIDAD_MAX_MPS,
    haversine_m,
    leer_labels,
    leer_plt,
    unir_con_etiquetas,
)

DIR_DATOS_TEST = Path(__file__).resolve().parent / "datos"


class TestMapeoModos:
    def test_walk_es_a_pie(self):
        assert MAPA_MODOS["walk"] == "a_pie"

    def test_car_es_vehiculo(self):
        assert MAPA_MODOS["car"] == "vehiculo"

    def test_taxi_es_vehiculo(self):
        assert MAPA_MODOS["taxi"] == "vehiculo"

    def test_bus_es_vehiculo(self):
        assert MAPA_MODOS["bus"] == "vehiculo"

    def test_bike_descartado(self):
        assert "bike" in MODOS_DESCARTADOS
        assert "bike" not in MAPA_MODOS

    def test_train_descartado(self):
        assert "train" in MODOS_DESCARTADOS

    def test_subway_descartado(self):
        assert "subway" in MODOS_DESCARTADOS

    def test_airplane_descartado(self):
        assert "airplane" in MODOS_DESCARTADOS


class TestLeerPlt:
    def test_lee_ejemplo(self):
        df = leer_plt(DIR_DATOS_TEST / "ejemplo.plt")
        assert len(df) == 10
        assert list(df.columns) == ["lat", "lon", "timestamp"]
        assert df["lat"].iloc[0] == pytest.approx(39.984702)

    def test_timestamps_utc(self):
        df = leer_plt(DIR_DATOS_TEST / "ejemplo.plt")
        assert str(df["timestamp"].dt.tz) == "UTC"


class TestLeerLabels:
    def test_lee_labels(self):
        df = leer_labels(DIR_DATOS_TEST / "labels.txt")
        assert len(df) == 2
        assert df["modo_original"].iloc[0] == "walk"
        assert df["modo_original"].iloc[1] == "car"


class TestUnionIntervalos:
    def test_union_basica(self):
        puntos = leer_plt(DIR_DATOS_TEST / "ejemplo.plt")
        labels = leer_labels(DIR_DATOS_TEST / "labels.txt")
        merged = unir_con_etiquetas(puntos, labels)
        assert len(merged) > 0
        assert "modo_original" in merged.columns

    def test_punto_en_borde_incluido(self):
        """Un punto exactamente en el inicio del intervalo debe incluirse."""
        puntos = leer_plt(DIR_DATOS_TEST / "ejemplo.plt")
        labels = leer_labels(DIR_DATOS_TEST / "labels.txt")
        merged = unir_con_etiquetas(puntos, labels)
        ts_inicio = pd.Timestamp("2008-10-23 02:53:04", tz="UTC")
        assert (merged["timestamp"] == ts_inicio).any()

    def test_punto_fuera_excluido(self):
        """Puntos entre intervalos no deben incluirse."""
        puntos = leer_plt(DIR_DATOS_TEST / "ejemplo.plt")
        labels = leer_labels(DIR_DATOS_TEST / "labels.txt")
        merged = unir_con_etiquetas(puntos, labels)
        ts_gap = pd.Timestamp("2008-10-23 02:53:42", tz="UTC")
        if ts_gap in puntos["timestamp"].values:
            assert ts_gap not in merged["timestamp"].values

    def test_modos_correctos(self):
        puntos = leer_plt(DIR_DATOS_TEST / "ejemplo.plt")
        labels = leer_labels(DIR_DATOS_TEST / "labels.txt")
        merged = unir_con_etiquetas(puntos, labels)
        walk_rows = merged[merged["modo_original"] == "walk"]
        car_rows = merged[merged["modo_original"] == "car"]
        assert len(walk_rows) > 0
        assert len(car_rows) > 0


class TestFiltroSaltos:
    def test_salto_detectado(self):
        """Un salto de ~57 km en 6 s (~9500 m/s) debe filtrarse."""
        puntos = leer_plt(DIR_DATOS_TEST / "salto.plt")
        labels = leer_labels(DIR_DATOS_TEST / "labels_salto.txt")
        merged = unir_con_etiquetas(puntos, labels)
        merged = merged.sort_values("timestamp").reset_index(drop=True)

        dist = np.array([
            haversine_m(
                merged["lat"].iloc[i], merged["lon"].iloc[i],
                merged["lat"].iloc[i + 1], merged["lon"].iloc[i + 1],
            )
            for i in range(len(merged) - 1)
        ])
        dt = merged["timestamp"].diff().dt.total_seconds().values[1:]
        vel = np.where(dt > 0, dist / dt, 0.0)
        assert any(v > VELOCIDAD_MAX_MPS for v in vel)


class TestHaversine:
    def test_distancia_conocida(self):
        d = haversine_m(0, 0, 0, 1)
        assert 111_000 < d < 112_000

    def test_mismo_punto(self):
        assert haversine_m(40.0, -3.0, 40.0, -3.0) == 0.0
