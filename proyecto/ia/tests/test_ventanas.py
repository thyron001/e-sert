"""Tests para ventanas y características con trazas sintéticas."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia.ventanas import remuestrear, ventanear
from ia.caracteristicas import extraer, desplazamiento_neto


def _traza_lineal(vel_mps: float, duracion_s: int = 35, lat0: float = 0.0, lon0: float = 0.0):
    """Genera traza en línea recta a velocidad constante (rumbo este)."""
    t = np.arange(0, duracion_s)
    grados_por_m = 1.0 / 111_320.0
    lon = lon0 + np.cumsum(np.full(duracion_s, vel_mps * grados_por_m))
    lon = np.insert(lon[:-1], 0, lon0)
    return pd.DataFrame({
        "usuario_id": "test_lineal",
        "t": t + 1_000_000_000,
        "lat": np.full(duracion_s, lat0),
        "lon": lon,
        "precision_m": np.full(duracion_s, np.nan),
        "velocidad_mps": np.full(duracion_s, vel_mps),
        "modo_real": "a_pie" if vel_mps < 3 else "vehiculo",
        "segmento_id": "test_lineal_seg0",
        "fuente": "test",
    })


def _traza_fija_ruido(sigma_m: float = 5.0, duracion_s: int = 35):
    """Genera traza en un punto fijo con ruido gaussiano."""
    rng = np.random.default_rng(42)
    grados_por_m = 1.0 / 111_320.0
    lat = 0.0 + rng.normal(0, sigma_m * grados_por_m, duracion_s)
    lon = 0.0 + rng.normal(0, sigma_m * grados_por_m, duracion_s)
    return pd.DataFrame({
        "usuario_id": "test_fijo",
        "t": np.arange(0, duracion_s) + 1_000_000_000,
        "lat": lat,
        "lon": lon,
        "precision_m": np.full(duracion_s, sigma_m),
        "velocidad_mps": np.zeros(duracion_s),
        "modo_real": "a_pie",
        "segmento_id": "test_fijo_seg0",
        "fuente": "test",
    })


def _traza_con_hueco(duracion_s: int = 60):
    """Genera traza con un hueco de 20 s en el medio."""
    t1 = np.arange(0, 20)
    t2 = np.arange(40, duracion_s)
    t = np.concatenate([t1, t2]) + 1_000_000_000
    n = len(t)
    return pd.DataFrame({
        "usuario_id": "test_hueco",
        "t": t,
        "lat": np.zeros(n),
        "lon": np.linspace(0, 0.001, n),
        "precision_m": np.full(n, np.nan),
        "velocidad_mps": np.ones(n),
        "modo_real": "a_pie",
        "segmento_id": "test_hueco_seg0",
        "fuente": "test",
    })


def _traza_sumo_sintetica():
    """Simula una traza tipo SUMO con el formato del contrato."""
    duracion_s = 35
    vel_mps = 8.0
    t = np.arange(0, duracion_s)
    grados_por_m = 1.0 / 111_320.0
    lat = -2.897 + np.cumsum(np.full(duracion_s, vel_mps * grados_por_m * 0.5))
    lon = -79.004 + np.cumsum(np.full(duracion_s, vel_mps * grados_por_m * 0.5))
    return pd.DataFrame({
        "usuario_id": "sim_veh42",
        "t": t + 1_000_000_000,
        "lat": lat,
        "lon": lon,
        "precision_m": np.full(duracion_s, 2.0),
        "velocidad_mps": np.full(duracion_s, vel_mps),
        "modo_real": "vehiculo",
        "segmento_id": "sim_veh42_seg0",
        "fuente": "sumo",
    })


class TestRemuestreo:
    def test_basico(self):
        df = _traza_lineal(1.4, duracion_s=35)
        df_r = remuestrear(df)
        assert len(df_r) > 0
        assert "t" in df_r.columns

    def test_hueco_parte_segmento(self):
        df = _traza_con_hueco()
        df_r = remuestrear(df, max_hueco_s=10)
        segmentos = df_r["segmento_id"].unique()
        assert len(segmentos) >= 2, "El hueco debería partir el segmento"


class TestVentaneo:
    def test_genera_ventanas(self):
        df = _traza_lineal(1.4, duracion_s=40)
        df_r = remuestrear(df)
        ventanas = ventanear(df_r)
        assert len(ventanas) > 0
        assert ventanas[0]["modo_real"] == "a_pie"

    def test_quieto_derivado(self):
        df = _traza_fija_ruido(sigma_m=5.0, duracion_s=40)
        df_r = remuestrear(df)
        ventanas = ventanear(df_r)
        modos = [v["modo_real"] for v in ventanas]
        assert "quieto" in modos, f"Debería derivar quieto, obtuve: {set(modos)}"

    def test_vehiculo_no_es_quieto(self):
        df = _traza_lineal(10.0, duracion_s=40)
        df_r = remuestrear(df)
        ventanas = ventanear(df_r)
        modos = [v["modo_real"] for v in ventanas]
        assert "quieto" not in modos


class TestCaracteristicas:
    def test_linea_recta_velocidad(self):
        df = _traza_lineal(1.4, duracion_s=40)
        df_r = remuestrear(df)
        ventanas = ventanear(df_r)
        assert len(ventanas) > 0
        feats = extraer(ventanas[0]["_ventana"])
        assert abs(feats["vel_media"] - 1.4) < 0.3, f"vel_media={feats['vel_media']}"

    def test_punto_fijo_rectitud_baja(self):
        df = _traza_fija_ruido(sigma_m=5.0, duracion_s=40)
        df_r = remuestrear(df)
        ventanas = ventanear(df_r)
        assert len(ventanas) > 0
        feats = extraer(ventanas[0]["_ventana"])
        assert feats["rectitud"] < 0.5, f"rectitud={feats['rectitud']}"

    def test_velocidad_alta(self):
        df = _traza_lineal(10.0, duracion_s=40)
        df_r = remuestrear(df)
        ventanas = ventanear(df_r)
        assert len(ventanas) > 0
        feats = extraer(ventanas[0]["_ventana"])
        assert feats["vel_media"] > 5.0, f"vel_media={feats['vel_media']}"

    def test_18_caracteristicas(self):
        df = _traza_lineal(1.4, duracion_s=40)
        df_r = remuestrear(df)
        ventanas = ventanear(df_r)
        feats = extraer(ventanas[0]["_ventana"])
        assert len(feats) >= 18, f"Solo {len(feats)} features"

    def test_independiente_del_orden(self):
        df = _traza_lineal(1.4, duracion_s=40)
        df_r = remuestrear(df)
        ventanas = ventanear(df_r)
        feats1 = extraer(ventanas[0]["_ventana"])
        df_shuffled = df.sample(frac=1, random_state=99).reset_index(drop=True)
        df_r2 = remuestrear(df_shuffled)
        ventanas2 = ventanear(df_r2)
        feats2 = extraer(ventanas2[0]["_ventana"])
        assert abs(feats1["vel_media"] - feats2["vel_media"]) < 0.01

    def test_traza_sumo(self):
        df = _traza_sumo_sintetica()
        df_r = remuestrear(df)
        ventanas = ventanear(df_r)
        assert len(ventanas) > 0
        feats = extraer(ventanas[0]["_ventana"])
        assert feats["vel_media"] > 3.0
        assert len(feats) >= 18
