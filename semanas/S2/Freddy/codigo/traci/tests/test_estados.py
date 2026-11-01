"""Máquina de estados y buffer de clasificación: pruebas puras, sin SUMO."""

from traci.clasificacion import ClasificadorUsuario
from traci.estados import MaquinaSesion


def correr(maquina, ventanas):
    """Aplica una lista de (modo, distancia_m) y devuelve todas las transiciones."""
    salida = []
    for i, (modo, distancia) in enumerate(ventanas):
        salida += maquina.actualizar(modo, distancia, t_sim=5.0 * i)
    return salida


def test_secuencia_normal_estaciona_camina_vuelve_y_cierra():
    m = MaquinaSesion("sim_veh1")
    trans = correr(m, [
        ("a_pie", 30),       # sale del auto: ESTACIONADO → A_PIE
        ("quieto", 200),     # en la diligencia, lejos: sigue A_PIE
        ("a_pie", 100),      # camina de vuelta
        ("a_pie", 25),       # < 30 m: REGRESANDO
        ("quieto", 0),       # ya está en el auto
        ("vehiculo", 25),    # maneja, 1.ª ventana
        ("vehiculo", 30),    # maneja, 2.ª ventana: SALIENDO → CERRADA
    ])
    assert [(t.desde, t.hacia) for t in trans] == [
        ("ESTACIONADO", "A_PIE"),
        ("A_PIE", "REGRESANDO"),
        ("REGRESANDO", "SALIENDO"),
        ("SALIENDO", "CERRADA"),
    ]
    assert m.estado == "CERRADA"


def test_conductor_que_camina_200_m_nunca_cierra():
    m = MaquinaSesion("sim_veh2")
    trans = correr(m, [("a_pie", 200)] * 60)  # cinco minutos caminando lejos
    assert [t.hacia for t in trans] == ["A_PIE"]
    assert m.estado == "A_PIE"


def test_auto_en_trafico_lento_cerca_del_puesto_no_libera():
    # Tráfico lento clasificado a_pie a 10 m del puesto: no pasa de ESTACIONADO.
    m = MaquinaSesion("sim_veh3")
    assert correr(m, [("a_pie", 10)] * 20) == []
    assert m.estado == "ESTACIONADO"


def test_una_sola_ventana_vehiculo_no_basta_para_salir():
    m = MaquinaSesion("sim_veh4")
    correr(m, [("a_pie", 40), ("quieto", 0)])  # A_PIE → REGRESANDO
    trans = correr(m, [("vehiculo", 50), ("quieto", 50)])
    assert "SALIENDO" not in [t.hacia for t in trans]
    assert m.estado == "REGRESANDO"


def test_quieto_dentro_del_auto_se_queda_estacionado():
    # p_espera_en_auto: el peatón se queda dentro; modo quieto a 0 m del puesto.
    m = MaquinaSesion("sim_veh5")
    assert correr(m, [("quieto", 0)] * 30) == []
    assert m.estado == "ESTACIONADO"


def test_regreso_corto_vuelve_a_alejarse():
    # p_regreso_corto: vuelve al auto, espera y sale otra vez.
    m = MaquinaSesion("sim_veh6")
    trans = correr(m, [
        ("a_pie", 30), ("quieto", 0), ("a_pie", 40), ("a_pie", 20),
    ])
    assert [t.hacia for t in trans] == ["A_PIE", "REGRESANDO", "A_PIE", "REGRESANDO"]


def test_cerrada_es_terminal():
    m = MaquinaSesion("sim_veh7")
    correr(m, [("vehiculo", 30), ("vehiculo", 30)])
    assert m.estado == "CERRADA"
    assert correr(m, [("a_pie", 200)]) == []


class _Fija:
    """Clasificador de prueba: devuelve un modo fijo y cuenta las llamadas."""

    __module__ = "prueba"

    def __init__(self):
        self.llamadas = 0

    def __call__(self, ventana):
        self.llamadas += 1
        return {"modo": "quieto", "confianza": 1.0, "fuente": "prueba"}


def _muestra(t):
    return {"t": float(t), "lat": -2.9, "lon": -79.0, "precision_m": 5.0, "modo_real": "quieto"}


def test_buffer_evalua_cada_5_s_con_30_s_de_datos():
    fija = _Fija()
    c = ClasificadorUsuario(clasificar=fija)
    evaluaciones = []
    for t in range(0, 61):
        c.observar("sim_veh1", _muestra(t))
        if c.evaluar("sim_veh1", float(t)) is not None:
            evaluaciones.append(t)
    # primera evaluación cuando el buffer cubre 29 s (t=29), luego cada 5 s
    assert evaluaciones[0] == 29
    assert all(b - a == 5 for a, b in zip(evaluaciones, evaluaciones[1:]))
    assert fija.llamadas == len(evaluaciones)


def test_buffer_descarta_muestras_fuera_de_la_ventana():
    c = ClasificadorUsuario(clasificar=_Fija())
    for t in range(0, 100):
        c.observar("sim_veh1", _muestra(t))
    buf = c._buffers["sim_veh1"]
    assert buf[0]["t"] == 70.0 and buf[-1]["t"] == 99.0
