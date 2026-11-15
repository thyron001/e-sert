"""Tests del servicio de inferencia robusto (S3-1): validacion, fallback, lote y propiedades."""
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ia import inferencia
from ia.inferencia import clasificar, clasificar_lote, _reset_cache
from ia.validacion import limpiar

MODOS = {"a_pie", "quieto", "vehiculo"}
FUENTES = {"rf", "umbral"}
M = 1.0 / 111_320.0
REFERENCIA = Path(__file__).parent / "datos" / "referencia_sklearn_final.json"


def ventana(vel=5.0, n=30, t0=1_000_000.0, prec=5.0, paso=1.0):
    return [
        {"t": t0 + i * paso, "lat": -2.9 + vel * i * paso * M, "lon": -79.0, "precision_m": prec}
        for i in range(n)
    ]


@pytest.fixture(autouse=True)
def _limpio(monkeypatch):
    monkeypatch.delenv("ESERT_MODELO", raising=False)
    monkeypatch.delenv("ESERT_CLASIFICADOR", raising=False)
    _reset_cache()
    yield
    _reset_cache()


def _valido(r):
    assert set(r) == {"modo", "confianza", "fuente"}
    assert r["modo"] in MODOS
    assert r["fuente"] in FUENTES
    assert 0.0 <= r["confianza"] <= 1.0
    assert not math.isnan(r["confianza"])


# ── Contrato ────────────────────────────────────────────────────────────────


class TestContrato:
    @pytest.mark.parametrize("vel,esperado", [(0.0, "quieto"), (1.4, "a_pie"), (12.0, "vehiculo")])
    def test_modos_basicos(self, vel, esperado):
        r = clasificar(ventana(vel))
        _valido(r)
        assert r["fuente"] == "rf"
        assert r["modo"] == esperado

    def test_previo_es_opcional(self):
        assert clasificar(ventana(5)) == clasificar(ventana(5), None)

    @pytest.mark.parametrize("malo", [None, 5, "abc", {"t": 1}, [1, 2, 3], [None]])
    def test_entrada_no_lista_de_puntos(self, malo):
        with pytest.raises(TypeError):
            clasificar(malo)


# ── Casos borde ─────────────────────────────────────────────────────────────


class TestBordes:
    def test_lista_vacia(self):
        r = clasificar([])
        _valido(r)
        assert r["confianza"] == 0.0 and r["fuente"] == "umbral"

    def test_un_punto(self):
        r = clasificar(ventana(5, n=1))
        _valido(r)
        assert r["confianza"] == 0.0

    def test_todos_iguales(self):
        v = [{"t": 100.0, "lat": -2.9, "lon": -79.0, "precision_m": 5.0}] * 30
        _valido(clasificar(v))

    def test_quieto_con_mismos_puntos_en_t_distintos(self):
        v = [{"t": float(i), "lat": -2.9, "lon": -79.0, "precision_m": 5.0} for i in range(30)]
        r = clasificar(v)
        _valido(r)
        assert r["modo"] == "quieto"

    def test_t_desordenado_equivale_a_ordenado(self):
        v = ventana(10)
        rng = np.random.default_rng(0)
        mezclado = [v[i] for i in rng.permutation(len(v))]
        assert clasificar(mezclado) == clasificar(v)

    def test_duplicados_no_cambian_el_resultado(self):
        v = ventana(10)
        assert clasificar(v + v[5:12]) == clasificar(v)

    def test_nan_en_coordenadas(self):
        v = ventana(10)
        for i in (3, 4, 10):
            v[i]["lat"] = float("nan")
        v[7]["lon"] = float("inf")
        r = clasificar(v)
        _valido(r)
        assert r["modo"] == "vehiculo"

    def test_todo_nan(self):
        v = [{"t": float(i), "lat": float("nan"), "lon": float("nan")} for i in range(30)]
        r = clasificar(v)
        _valido(r)
        assert r["confianza"] == 0.0

    def test_hueco_de_15s_no_usa_rf(self):
        v = [p for p in ventana(10, n=45) if not 10 <= p["t"] - 1_000_000.0 < 25]
        r = clasificar(v)
        _valido(r)
        assert r["fuente"] == "umbral"

    def test_hueco_de_4s_se_interpola_y_usa_rf(self):
        v = [p for p in ventana(10) if not 10 <= p["t"] - 1_000_000.0 < 14]
        cal = limpiar(v)[1]
        assert cal.hueco_max_s <= 1.0 and cal.cobertura > 0.99
        assert clasificar(v)["fuente"] == "rf"

    def test_precision_200_descarta_todo(self):
        r = clasificar(ventana(10, prec=200.0))
        _valido(r)
        assert r["confianza"] == 0.0

    def test_precision_mixta_descarta_solo_los_malos(self):
        v = ventana(10)
        for i in range(0, 30, 3):
            v[i]["precision_m"] = 200.0
        arr, cal = limpiar(v)
        assert (arr[:, 3] <= 50).all()
        assert cal.precision_mediana_m <= 50

    def test_precision_max_parametrizable(self):
        _, c1 = limpiar(ventana(5, prec=30.0), precision_max_m=20.0)
        _, c2 = limpiar(ventana(5, prec=30.0), precision_max_m=50.0)
        assert c1.n_validos == 0 and c2.n_validos == 30

    def test_salto_imposible_se_elimina(self):
        v = ventana(5)
        v[12]["lat"] += 1.0  # ~111 km en 1 s
        arr, cal = limpiar(v)
        assert np.abs(arr[:, 1] - (-2.9)).max() < 0.01
        assert clasificar(v)["modo"] in MODOS

    def test_tiempos_absurdos_no_revientan_memoria(self):
        v = ventana(5)
        v[0]["t"] = -1e15
        v[-1]["t"] = 1e15
        _valido(clasificar(v))

    def test_valores_no_numericos(self):
        v = ventana(5)
        v[2]["lat"] = "x"
        v[3]["t"] = None
        _valido(clasificar(v))

    def test_precision_none(self):
        v = ventana(10)
        for p in v:
            p["precision_m"] = None
        r = clasificar(v)
        _valido(r)
        assert r["fuente"] == "rf"

    def test_sin_clave_precision(self):
        v = [{k: p[k] for k in ("t", "lat", "lon")} for p in ventana(10)]
        assert clasificar(v)["fuente"] == "rf"

    def test_cobertura_baja_usa_umbral_con_confianza_proporcional(self):
        v = [p for p in ventana(10, n=30) if p["t"] - 1_000_000.0 in (0, 1, 2, 3, 4, 5, 20, 21, 22, 29)]
        arr, cal = limpiar(v)
        r = clasificar(v)
        assert r["fuente"] == "umbral"
        assert r["confianza"] == pytest.approx(cal.cobertura)
        assert r["modo"] == "vehiculo"


class TestPrevio:
    prev = {"modo": "vehiculo", "confianza": 0.8, "fuente": "rf"}

    def test_pocos_puntos_devuelven_previo_con_confianza_a_la_mitad(self):
        r = clasificar(ventana(5, n=3), self.prev)
        assert r["modo"] == "vehiculo"
        assert r["confianza"] == pytest.approx(0.4)

    def test_lista_vacia_con_previo(self):
        assert clasificar([], self.prev)["confianza"] == pytest.approx(0.4)

    def test_sin_previo_umbral_confianza_cero(self):
        r = clasificar(ventana(5, n=3))
        assert r["fuente"] == "umbral" and r["confianza"] == 0.0

    def test_previo_no_se_usa_con_datos_suficientes(self):
        assert clasificar(ventana(0.0), self.prev)["modo"] == "quieto"

    def test_previo_no_se_muta(self):
        copia = dict(self.prev)
        clasificar(ventana(5, n=2), self.prev)
        assert self.prev == copia


# ── Fallback ────────────────────────────────────────────────────────────────


class TestFallback:
    def test_modelo_roto_usa_umbral_y_avisa_una_vez(self, monkeypatch):
        monkeypatch.setenv("ESERT_MODELO", "/ruta/que/no/existe.joblib")
        _reset_cache()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            rs = [clasificar(ventana(12)) for _ in range(4)]
        for r in rs:
            _valido(r)
            assert r["fuente"] == "umbral" and r["modo"] == "vehiculo"
        avisos = [x for x in w if "Modelo RF no disponible" in str(x.message)]
        assert len(avisos) == 1

    def test_predict_que_lanza_cae_al_umbral(self, monkeypatch):
        class Roto:
            classes_ = np.array(["a_pie", "quieto", "vehiculo"])

            def predict_proba(self, X):
                raise RuntimeError("boom")

        _reset_cache()
        with monkeypatch.context() as m, warnings.catch_warnings(record=True) as w:
            m.setattr(inferencia, "_cargar_modelo", lambda: Roto())
            warnings.simplefilter("always")
            r1 = clasificar(ventana(12))
            r2 = clasificar(ventana(0.0))
            lote = clasificar_lote([ventana(12), ventana(0.0)])
        assert r1["fuente"] == r2["fuente"] == "umbral"
        assert r1["modo"] == "vehiculo" and r2["modo"] == "quieto"
        assert [x["fuente"] for x in lote] == ["umbral", "umbral"]
        assert len([x for x in w if "predict_proba" in str(x.message)]) == 1

    def test_forzar_umbral_por_entorno(self, monkeypatch):
        monkeypatch.setenv("ESERT_CLASIFICADOR", "umbral")
        _reset_cache()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert clasificar(ventana(12))["fuente"] == "umbral"

    def test_lote_sin_modelo(self, monkeypatch):
        monkeypatch.setenv("ESERT_MODELO", "/no/existe.joblib")
        _reset_cache()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rs = clasificar_lote([ventana(12), ventana(0.0), ventana(1.4)])
        assert [r["fuente"] for r in rs] == ["umbral"] * 3
        assert [r["modo"] for r in rs] == ["vehiculo", "quieto", "a_pie"]


# ── Lote ────────────────────────────────────────────────────────────────────


class TestLote:
    def _mezcla(self, n=60):
        rng = np.random.default_rng(3)
        vs = []
        for i in range(n):
            v = ventana(float(rng.choice([0, 1.4, 10])), n=int(rng.choice([30, 30, 25, 12, 4, 0])))
            if i % 7 == 0 and len(v) > 12:
                v = v[:5] + v[20:]
            if i % 11 == 0 and v:
                v[0]["lat"] = float("nan")
            vs.append(v)
        return vs

    def test_lote_igual_a_individual(self):
        vs = self._mezcla()
        uno = [clasificar(v) for v in vs]
        lote = clasificar_lote(vs)
        assert len(lote) == len(uno)
        for a, b in zip(uno, lote):
            assert a["modo"] == b["modo"] and a["fuente"] == b["fuente"]
            assert a["confianza"] == pytest.approx(b["confianza"], abs=1e-9)

    def test_lote_con_previos(self):
        prev = {"modo": "a_pie", "confianza": 0.6, "fuente": "rf"}
        r = clasificar_lote([ventana(5, n=2), ventana(12)], [prev, None])
        assert r[0]["modo"] == "a_pie" and r[0]["confianza"] == pytest.approx(0.3)
        assert r[1]["modo"] == "vehiculo"

    def test_lote_vacio(self):
        assert clasificar_lote([]) == []

    def test_lote_rechaza_entradas_malas(self):
        with pytest.raises(TypeError):
            clasificar_lote([ventana(5), "x"])


# ── Equivalencia con S2 ─────────────────────────────────────────────────────


class TestEquivalenciaS2:
    @pytest.mark.skipif(not REFERENCIA.exists(), reason="falta referencia_sklearn_final.json")
    def test_ventanas_limpias_coinciden_al_100_por_ciento(self):
        ref = json.loads(REFERENCIA.read_text())
        assert len(ref) >= 100
        for caso in ref:
            r = clasificar(caso["ventana"])
            assert r["fuente"] == "rf"
            assert r["modo"] == caso["modo"]
            assert r["confianza"] == pytest.approx(caso["confianza"], abs=1e-4)

    def test_bosque_plano_igual_a_sklearn(self):
        import joblib

        ruta = Path(inferencia.DIR_MODELOS) / "rf_final.joblib"
        sk = joblib.load(ruta)
        plano = inferencia._cargar_modelo()
        rng = np.random.default_rng(0)
        X = rng.normal(size=(500, 18)) * rng.uniform(0.1, 30, 18)
        X[::5, 15] = np.nan
        a, b = plano.predict_proba(X), sk.predict_proba(X)
        assert np.abs(a - b).max() < 1e-6
        assert (a.argmax(1) == b.argmax(1)).all()


class TestMeta:
    def test_json_del_modelo_y_hash_correcto(self):
        import hashlib

        meta = json.loads((Path(inferencia.DIR_MODELOS) / "rf_final.json").read_text())
        for k in ("features", "sklearn_version", "sha256_modelo", "fecha", "hiperparametros", "suavizado", "fallback"):
            assert k in meta
        h = hashlib.sha256((Path(inferencia.DIR_MODELOS) / "rf_final.joblib").read_bytes()).hexdigest()
        assert h == meta["sha256_modelo"]
        assert meta["features"] == inferencia.NOMBRES_FEATURES


# ── Propiedades (hypothesis) ────────────────────────────────────────────────

flotante = st.one_of(
    st.floats(allow_nan=True, allow_infinity=True),
    st.floats(-1e6, 1e6),
)
lat_s = st.one_of(st.floats(-3.0, -2.8), st.floats(-100, 100), st.just(float("nan")), st.just(float("inf")))
lon_s = st.one_of(st.floats(-79.1, -78.9), st.floats(-200, 200), st.just(float("nan")))
t_s = st.one_of(st.floats(0, 60), st.integers(0, 60).map(float), st.floats(-1e12, 1e12), st.just(float("nan")))
prec_s = st.one_of(st.none(), st.floats(0, 300), st.just(float("nan")))
punto_s = st.fixed_dictionaries({"t": t_s, "lat": lat_s, "lon": lon_s, "precision_m": prec_s})
ventana_s = st.lists(punto_s, min_size=0, max_size=60)

CFG = settings(
    max_examples=300,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)


class TestPropiedades:
    @CFG
    @given(ventana_s)
    def test_clasificar_nunca_lanza_y_cumple_el_contrato(self, v):
        _valido(clasificar(v))

    @CFG
    @given(ventana_s, st.sampled_from([None, {"modo": "quieto", "confianza": 0.9, "fuente": "umbral"}]))
    def test_con_previo(self, v, prev):
        _valido(clasificar(v, prev))

    @CFG
    @given(st.lists(ventana_s, max_size=6))
    def test_lote_nunca_lanza_y_es_consistente(self, vs):
        lote = clasificar_lote(vs)
        assert len(lote) == len(vs)
        for r, v in zip(lote, vs):
            _valido(r)
            u = clasificar(v)
            assert r["modo"] == u["modo"] and r["fuente"] == u["fuente"]

    @CFG
    @given(ventana_s)
    def test_limpiar_devuelve_calidad_coherente(self, v):
        arr, cal = limpiar(v)
        assert arr.ndim == 2 and arr.shape[1] == 4
        assert cal.n_validos == arr.shape[0]
        assert 0.0 <= cal.cobertura <= 1.0
        assert cal.hueco_max_s >= 0.0
        if arr.shape[0] > 1:
            assert (np.diff(arr[:, 0]) > 0).all()
            assert np.isfinite(arr[:, :3]).all()
