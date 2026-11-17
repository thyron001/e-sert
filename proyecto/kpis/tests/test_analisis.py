"""Tests del análisis estadístico y de las figuras (S3-2). Corren en la computadora:

    kpis/.venv/bin/python -m pytest -q kpis/tests/test_analisis.py
"""
import math

import numpy as np
import pandas as pd
import pytest

from kpis import analisis as an

COLS = ["id", "penetracion", "clasificador", "semilla", "n_veh", "n_busca", "busqueda_media_s", "busqueda_p90_s",
        "distancia_busqueda_media_m", "co2_busqueda_kg", "ocupacion_media", "falsas_lib_100",
        "retardo_cierre_mediana_s", "error_fact_medio_usd", "precision_mapa", "teleports", "duracion_real_s"]


def sintetico(nan_sistema=False, semillas=(1, 2, 3)):
    """24 filas: búsqueda = 300 − 2·pen + semilla (umbral +10); KPIs de sistema opcionalmente NaN."""
    filas = []
    for s in semillas:
        for p in (0, 20, 50, 80):
            for c in ("umbral", "rf"):
                b = 300 - 2 * p + s + (10 if (c == "umbral" and p > 0) else 0)
                filas.append({"id": f"p{p:02d}_{c}_s{s}", "penetracion": p, "clasificador": c, "semilla": s,
                              "n_veh": 7000, "n_busca": 900, "busqueda_media_s": b, "busqueda_p90_s": 2 * b,
                              "distancia_busqueda_media_m": 3 * b, "co2_busqueda_kg": b / 10, "ocupacion_media": 0.88,
                              "falsas_lib_100": np.nan if (nan_sistema or p == 0) else (20 if c == "umbral" else 5) + s,
                              "retardo_cierre_mediana_s": np.nan if (nan_sistema or p == 0) else 30 + s,
                              "error_fact_medio_usd": np.nan if (nan_sistema or p == 0) else -0.1,
                              "precision_mapa": np.nan if nan_sistema else 0.6 + p / 400,
                              "teleports": 0, "duracion_real_s": 100})
    return pd.DataFrame(filas, columns=COLS)


def test_ic95_de_1_2_3():
    r = an.ic95([1, 2, 3])
    assert r["media"] == pytest.approx(2.0)
    assert r["n"] == 3
    assert r["semiancho"] == pytest.approx(4.302652729 / math.sqrt(3), rel=1e-6)  # ≈ 2,484
    assert r["semiancho"] == pytest.approx(2.484, abs=1e-3)


def test_ic95_con_nan_y_un_solo_valor():
    assert an.ic95([1.0, float("nan"), 3.0])["n"] == 2
    uno = an.ic95([5.0])
    assert uno["n"] == 1 and uno["media"] == 5.0 and math.isnan(uno["semiancho"])
    assert an.ic95([])["n"] == 0


def test_pareado_da_la_diferencia_conocida():
    df = sintetico()
    par = an.pareado(df, "busqueda_media_s").set_index(["penetracion", "clasificador"])
    # rf: d_s = −2·pen exactamente en cada semilla → IC de ancho 0
    assert par.loc[(50, "rf"), "dif_media"] == pytest.approx(-100)
    assert par.loc[(50, "rf"), "dif_lo"] == pytest.approx(-100)
    assert par.loc[(50, "umbral"), "dif_media"] == pytest.approx(-90)
    base = np.array([301, 302, 303])
    assert par.loc[(50, "rf"), "rel_media_pct"] == pytest.approx(np.mean(-100 / base * 100))
    assert not par.loc[(50, "rf"), "ic_cruza_cero"]


def test_umbral_vs_rf_y_holm():
    df = sintetico()
    t = an.umbral_vs_rf(df, "falsas_lib_100")
    assert list(t["penetracion"]) == [20, 50, 80]
    assert (t["dif_rf_menos_umbral"] == -15).all()
    assert t["p_holm"].notna().all()
    assert (t["p_holm"] >= t["p"]).all()


def test_resumen_con_nan_cuenta_n_real():
    df = sintetico()
    df.loc[df["id"] == "p50_rf_s3", "busqueda_media_s"] = np.nan  # corrida fallida
    r = an.resumen(df, "busqueda_media_s").set_index(["penetracion", "clasificador"])
    assert r.loc[(50, "rf"), "n"] == 2
    assert r.loc[(80, "rf"), "n"] == 3


def test_tabla_hallazgos_y_base(tmp_path):
    df = sintetico()
    t = an.tabla(df)
    assert len(t) == 8
    assert "±" in t.iloc[0, 3]
    md, tex = an.escribir_tablas(t, tmp_path)
    assert "booktabs" in tex.read_text() and "\\toprule" in tex.read_text()
    frases = an.hallazgos(df)
    assert len(frases) >= 5
    assert any("IC 95 %" in f for f in frases)
    b = an.exportar_base(df, tmp_path / "base.json")
    import json

    datos = json.loads(b.read_text())
    assert datos["base"]["busqueda_media_s"] == pytest.approx(302)


@pytest.mark.parametrize("nan_sistema", [False, True])
def test_figuras_con_csv_sintetico(tmp_path, nan_sistema):
    from kpis import figuras

    csv = tmp_path / "experimentos.csv"
    sintetico(nan_sistema).to_csv(csv, index=False)
    rutas = figuras.generar(csv, tmp_path / "fig", tmp_path / "no_hay_vehiculos", tmp_path / "no_hay_sesiones")
    nombres = {r.name for r in rutas}
    for f in ("F1_busqueda_vs_penetracion", "F2_distancia_busqueda", "F3_co2_busqueda", "F4_falsas_liberaciones",
              "F5_retardo_cierre", "F6_error_facturacion", "F7_precision_mapa", "F8_cdf_busqueda"):
        assert f"{f}.png" in nombres and f"{f}.pdf" in nombres
    assert all(r.stat().st_size > 1000 for r in rutas)
