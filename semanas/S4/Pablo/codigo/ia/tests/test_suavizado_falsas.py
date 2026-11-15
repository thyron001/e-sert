"""Tests del suavizador (mayoria / prob_media) y de la simulación de falsas liberaciones (S3-2)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ia import simular_falsas as sf
from ia.suavizado import CLASES, Suavizador


def oh(m):
    return np.eye(3)[CLASES.index(m)]


def res(m, conf=0.9, fuente="rf"):
    return {"modo": m, "confianza": conf, "fuente": fuente}


class TestSuavizador:
    def test_k1_no_suaviza(self):
        for metodo in ("mayoria", "prob_media"):
            sv = Suavizador(k=1, metodo=metodo)
            seq = ["vehiculo", "a_pie", "quieto", "vehiculo"]
            assert [sv.paso(oh(m)) for m in seq] == seq

    def test_mayoria_vota_sobre_las_ultimas_k(self):
        sv = Suavizador(k=3, metodo="mayoria")
        seq = ["vehiculo", "a_pie", "a_pie", "vehiculo", "vehiculo"]
        assert [sv.paso(oh(m)) for m in seq] == ["vehiculo", "a_pie", "a_pie", "a_pie", "vehiculo"]

    def test_mayoria_empate_gana_el_mas_reciente(self):
        sv = Suavizador(k=3, metodo="mayoria")
        for m in ("vehiculo", "a_pie"):
            sv.paso(oh(m))
        assert sv.paso(oh("quieto")) == "quieto"

    def test_prob_media_pesa_la_confianza(self):
        sv = Suavizador(k=3, metodo="prob_media")
        sv.paso(np.array([0.0, 0.0, 1.0]))
        sv.paso(np.array([0.45, 0.0, 0.55]))
        # dos ventanas a favor de vehiculo (1.0 y 0.55) contra una de a_pie (0.9)
        assert sv.paso(np.array([0.9, 0.0, 0.1])) == "vehiculo"
        sv.reset()
        assert sv.paso(np.array([0.9, 0.0, 0.1])) == "a_pie"

    def test_actualizar_respeta_resultado_modo(self):
        sv = Suavizador(k=3, metodo="mayoria")
        r = sv.actualizar(res("a_pie", fuente="umbral"))
        assert set(r) == {"modo", "confianza", "fuente"}
        assert r["modo"] == "a_pie" and r["fuente"] == "umbral" and 0 <= r["confianza"] <= 1

    def test_estado_independiente_por_instancia(self):
        a, b = Suavizador(k=3, metodo="mayoria"), Suavizador(k=3, metodo="mayoria")
        a.paso(oh("vehiculo"))
        assert b.paso(oh("quieto")) == "quieto"

    @pytest.mark.parametrize("kw", [{"k": 0}, {"metodo": "inventado"}])
    def test_parametros_invalidos(self, kw):
        with pytest.raises(ValueError):
            Suavizador(**kw)

    def test_metodos_antiguos_siguen_funcionando(self):
        assert Suavizador(metodo="histeresis", k=1).paso(oh("quieto")) == "quieto"
        assert Suavizador(metodo="media_movil", k=3).paso(oh("a_pie")) == "a_pie"


def episodio_sintetico():
    """Estacionado 80 s, camina hasta los 200 s, vuelve y se va."""
    t = np.arange(0, 260.0)
    modo = np.where(t < 80, "quieto", np.where(t < 200, "a_pie", "vehiculo"))
    return sf.Episodio("s_test", t, np.zeros_like(t), np.zeros_like(t), modo, (0.0, 0.0), 200.0)


def ventanas_sinteticas(ep, modo_clasificado, dist_inicio=5.0):
    te = np.arange(29.0, 259.0, 5.0)
    real = np.array([sf.IDX[ep.modo[int(x)]] for x in te])
    dist = np.where((te > 85) & (te < 190), 40.0, dist_inicio)
    dist[te >= 200] = 5.0 + 4.0 * (te[te >= 200] - 200)  # el auto acelera: la distancia crece gradual
    p = np.zeros((len(te), 3))
    for j, x in enumerate(te):
        p[j, sf.IDX[modo_clasificado(x)]] = 1
    return sf.VentanasEp(te, dist, real, {"rf": p, "umbral": p.copy()})


class TestSimulacion:
    def test_clasificador_perfecto_cierra_bien(self):
        ep = episodio_sintetico()
        w = ventanas_sinteticas(ep, lambda x: ep.modo[int(x)])
        r, ret = sf.simular_sesion(ep, w, "rf", "mayoria", 1)
        assert r == 0 and 5 <= ret <= 20

    def test_dos_ventanas_vehiculo_falsas_liberan_con_k1_y_no_con_k5(self):
        # deriva GPS: el auto sigue estacionado pero el telefono "se aleja" 25 m del puesto
        ep = episodio_sintetico()
        w = ventanas_sinteticas(ep, lambda x: "vehiculo" if 59 <= x < 69 else ep.modo[int(x)],
                                dist_inicio=25.0)
        assert sf.simular_sesion(ep, w, "rf", "mayoria", 1)[0] == 1
        assert sf.simular_sesion(ep, w, "rf", "mayoria", 5)[0] != 1

    def test_suavizar_aumenta_el_retardo(self):
        ep = episodio_sintetico()
        w = ventanas_sinteticas(ep, lambda x: ep.modo[int(x)])
        r1 = sf.simular_sesion(ep, w, "rf", "mayoria", 1)[1]
        r3 = sf.simular_sesion(ep, w, "rf", "mayoria", 3)[1]
        assert r3 > r1

    def test_suavizado_largo_puede_perder_el_cierre(self):
        # con k=5 el modo suavizado sigue en a_pie cuando el auto ya esta a > 30 m: la maquina de
        # estados pasa REGRESANDO -> A_PIE y ya no puede llegar a SALIENDO
        ep = episodio_sintetico()
        w = ventanas_sinteticas(ep, lambda x: ep.modo[int(x)])
        assert sf.simular_sesion(ep, w, "rf", "mayoria", 5)[0] == -1

    def test_sin_cierre_si_nunca_se_detecta_vehiculo(self):
        ep = episodio_sintetico()
        w = ventanas_sinteticas(ep, lambda x: "a_pie")
        assert sf.simular_sesion(ep, w, "rf", "mayoria", 1)[0] == -1
    def test_recomendar_prefiere_menor_k_dentro_del_ic(self):
        import pandas as pd

        t = pd.DataFrame([
            {"sistema": "rf", "metodo": "mayoria", "k": 3, "falsas_100": 1.0, "falsas_ic95_sup": 3.0,
             "cumple_retardo": True},
            {"sistema": "rf", "metodo": "mayoria", "k": 1, "falsas_100": 2.0, "falsas_ic95_sup": 4.0,
             "cumple_retardo": True},
            {"sistema": "rf", "metodo": "mayoria", "k": 5, "falsas_100": 0.5, "falsas_ic95_sup": 1.0,
             "cumple_retardo": False},
        ])
        assert sf.recomendar(t)["k"] == 1
