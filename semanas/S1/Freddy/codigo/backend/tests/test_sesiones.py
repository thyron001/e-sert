"""Ciclo de vida de la sesión y las 5 reglas de cobro de docs/CONTEXTO.md."""

import pytest

from backend.nucleo.errores import ErrorNucleo
from comun import esquemas as e

from .conftest import en

E, C, A = e.EstadoSesion, e.CodigoError, e.Aviso
U = "sim_veh42"


def _codigo(fn, *args, **kw):
    with pytest.raises(ErrorNucleo) as err:
        fn(*args, **kw)
    return err.value.codigo


def _salir(srv, sid, minutos, t_sim=None):
    srv.transicion(sid, E.SALIENDO, en(minutos))
    return srv.cerrar(sid, en(minutos), e.MotivoCierre.deteccion, t_sim=t_sim)


# --- Regla 1: saldo insuficiente al buscar/iniciar → recargar ($5 o más) -----------------


def test_regla1_saldo_insuficiente(sistema):
    _, bil, srv = sistema
    assert _codigo(srv.iniciar, U, "SIM-0042", "pa_mock0_0", en(0)) is C.SALDO_INSUFICIENTE
    assert bil.movimientos(U) == []  # no quedó nada a medias
    bil.recargar(U, 5)
    assert srv.iniciar(U, "SIM-0042", "pa_mock0_0", en(0)).estado is E.ESTACIONADO


# --- Regla 2: al confirmar la llegada se retiene el bloque mínimo ------------------------


def test_regla2_retiene_bloque_minimo(sistema):
    _, bil, srv = sistema
    bil.recargar(U, 5, ts=en(0))
    creada = srv.iniciar(U, "SIM-0042", "pa_mock0_0", en(1))
    assert creada.retenido == 0.25
    assert bil.estado(U)["disponible"] == 4.75
    assert srv.mapa.ocupados("pa_mock0_0") == 1


# --- Regla 3: al salir se debita el tiempo real (fracciones + mínimo) y se libera --------


def test_regla3_recargar_iniciar_cerrar_47_min(sistema):
    _, bil, srv = sistema
    bil.recargar(U, 5, ts=en(0))
    sid = srv.iniciar(U, "SIM-0042", "pa_mock0_0", en(0)).sesion_id
    srv.transicion(sid, E.A_PIE, en(2))
    srv.transicion(sid, E.REGRESANDO, en(44))
    cerrada = _salir(srv, sid, 47)
    assert (cerrada.minutos_reales, cerrada.minutos_cobrados, cerrada.debitado, cerrada.saldo) == (47, 50, 0.42, 4.58)
    assert bil.estado(U) == {"saldo": 4.58, "retenido": 0.0, "disponible": 4.58, "bloqueada": False}
    assert srv.mapa.ocupados("pa_mock0_0") == 0
    tipos = [m.tipo.value for m in bil.movimientos(U)]
    assert tipos == ["recarga", "retencion", "debito", "liberacion"]
    recibo = srv.recibo(sid)
    assert (recibo.tarjeta_sert_usd, recibo.ahorro_usd) == (0.50, 0.08)
    ses = srv.obtener(sid)
    assert ses.estado is E.CERRADA and ses.debitado == 0.42 and ses.fin == en(47)


def test_regla3_cobro_minimo_3_min(sistema):
    _, bil, srv = sistema
    bil.recargar(U, 5)
    sid = srv.iniciar(U, "SIM-0042", "pa_mock0_0", en(0)).sesion_id
    cerrada = _salir(srv, sid, 3)
    assert (cerrada.minutos_cobrados, cerrada.debitado) == (10, 0.08)


def test_regla3_duracion_con_t_sim(sistema):
    """Si hay t_sim al inicio y al cierre, manda el reloj de SUMO y no la hora UTC."""
    _, bil, srv = sistema
    bil.recargar(U, 5)
    sid = srv.iniciar(U, "SIM-0042", "pa_mock0_0", en(0), t_sim=1000.0).sesion_id
    cerrada = _salir(srv, sid, 1, t_sim=1000.0 + 12 * 60)
    assert (cerrada.minutos_reales, cerrada.minutos_cobrados, cerrada.debitado) == (12, 15, 0.13)


# --- Regla 4: saldo negativo permitido, bloqueo hasta recargar y aviso de saldo bajo -----


def test_regla4_saldo_negativo_bloquea_hasta_recargar(sistema):
    _, bil, srv = sistema
    bil.recargar(U, 5)
    sid = srv.iniciar(U, "SIM-0042", "pa_mock0_0", en(0)).sesion_id
    _salir(srv, sid, 570)  # 9 h 30 → $4.75; quedan $0.25
    sid = srv.iniciar(U, "SIM-0042", "pa_mock1_0", en(600)).sesion_id
    cerrada = _salir(srv, sid, 660)  # 60 min → $0.50; saldo −0.25, dentro del máximo
    assert cerrada.saldo == -0.25
    assert bil.estado(U)["bloqueada"] is True
    assert _codigo(srv.iniciar, U, "SIM-0042", "pa_mock0_0", en(700)) is C.SESIONES_BLOQUEADAS
    assert srv.avisos(sid, en(700)) == [A.saldo_bajo, A.sesiones_bloqueadas]
    bil.recargar(U, 5)
    assert bil.estado(U)["bloqueada"] is False
    assert srv.iniciar(U, "SIM-0042", "pa_mock0_0", en(710)).estado is E.ESTACIONADO


def test_regla4_aviso_saldo_bajo_y_agotado(sistema):
    _, bil, srv = sistema
    bil.recargar(U, 5)
    sid = srv.iniciar(U, "SIM-0042", "pa_mock0_0", en(0)).sesion_id
    assert srv.avisos(sid, en(5)) == []
    # Con $5 caben 600 min: el aviso salta cuando quedan menos de 10 min de saldo.
    assert A.saldo_bajo not in srv.avisos(sid, en(589))
    assert A.saldo_bajo in srv.avisos(sid, en(591))
    # Agotado: el costo en curso alcanza saldo + 0,50 → 660 min.
    assert A.saldo_agotado not in srv.avisos(sid, en(650))
    assert A.saldo_agotado in srv.avisos(sid, en(660))


# --- Regla 5: tope de tiempo SERT con aviso previo ---------------------------------------


def test_regla5_tope_de_tiempo(sistema):
    _, bil, srv = sistema
    bil.recargar(U, 10)
    sid = srv.iniciar(U, "SIM-0042", "pa_mock0_0", en(0), t_sim=0.0).sesion_id
    assert srv.avisos(sid, t_sim=109 * 60) == []
    assert srv.avisos(sid, t_sim=110 * 60) == [A.tiempo_maximo_cerca]
    assert srv.avisos(sid, t_sim=121 * 60) == [A.tiempo_maximo_superado]


# --- Validaciones del ciclo de vida -------------------------------------------------------


def test_puesto_lleno(chico):
    _, bil, srv = chico
    bil.recargar("sim_a", 5)
    bil.recargar("sim_b", 5)
    srv.iniciar("sim_a", "SIM-0001", "pa_a_0", en(0))
    assert _codigo(srv.iniciar, "sim_b", "SIM-0002", "pa_a_0", en(1)) is C.PUESTO_LLENO
    assert bil.estado("sim_b")["retenido"] == 0.0


def test_puesto_no_existe_sesion_activa_y_validacion(sistema):
    _, bil, srv = sistema
    bil.recargar(U, 5)
    assert _codigo(srv.iniciar, U, "SIM-0042", "pa_inexistente_0") is C.PUESTO_NO_EXISTE
    assert _codigo(srv.iniciar, U, "placa mala", "pa_mock0_0") is C.VALIDACION
    srv.iniciar(U, "SIM-0042", "pa_mock0_0")
    assert srv.sesion_abierta(U) is not None
    assert _codigo(srv.iniciar, U, "SIM-0042", "pa_mock1_0") is C.SESION_ACTIVA


def test_transiciones(sistema):
    _, bil, srv = sistema
    bil.recargar(U, 5)
    sid = srv.iniciar(U, "SIM-0042", "pa_mock0_0", en(0)).sesion_id
    assert _codigo(srv.transicion, sid, E.REGRESANDO) is C.TRANSICION_INVALIDA
    assert _codigo(srv.transicion, sid, E.CERRADA) is C.TRANSICION_INVALIDA
    # Cierre por detección solo desde SALIENDO; el manual vale desde cualquier estado abierto.
    assert _codigo(srv.cerrar, sid, en(5), e.MotivoCierre.deteccion) is C.TRANSICION_INVALIDA
    for estado in (E.A_PIE, E.REGRESANDO, E.A_PIE, E.REGRESANDO, E.SALIENDO):
        assert srv.transicion(sid, estado, en(1)).estado is estado
    srv.cerrar(sid, en(20), e.MotivoCierre.manual)
    assert _codigo(srv.transicion, sid, E.A_PIE) is C.SESION_YA_CERRADA
    assert _codigo(srv.cerrar, sid, en(21)) is C.SESION_YA_CERRADA
    assert _codigo(srv.obtener, "ses_00000000-0000-4000-8000-000000000000") is C.SESION_NO_EXISTE
    assert srv.avisos(sid, en(30)) == []


def test_cierre_antes_del_inicio_y_recibo_abierta(sistema):
    _, bil, srv = sistema
    bil.recargar(U, 5)
    sid = srv.iniciar(U, "SIM-0042", "pa_mock0_0", en(10)).sesion_id
    with pytest.raises(ValueError):
        srv.recibo(sid)
    assert _codigo(srv.cerrar, sid, en(5)) is C.VALIDACION
    assert srv.obtener(sid).estado is E.ESTACIONADO  # el fallo no dejó rastros
