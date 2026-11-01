"""Billetera: libro de movimientos, atomicidad y regla de recarga mínima (regla 1)."""

import pytest

from backend.nucleo.db import Movimiento
from backend.nucleo.errores import ErrorNucleo
from comun import esquemas as e
from sqlalchemy import func, select

from .conftest import en


def test_usuario_nuevo_tiene_saldo_cero(sistema):
    _, bil, _ = sistema
    assert bil.estado("app_00000000-0000-4000-8000-000000000000") == {
        "saldo": 0.0, "retenido": 0.0, "disponible": 0.0, "bloqueada": False}


def test_recarga_minima(sistema):
    _, bil, _ = sistema
    with pytest.raises(ErrorNucleo) as err:
        bil.recargar("sim_v1", 4.99)
    assert err.value.codigo is e.CodigoError.RECARGA_MINIMA and err.value.http == 422
    bil.recargar("sim_v1", 5.00, referencia_payphone="PP-1", ts=en(0))
    assert bil.estado("sim_v1")["saldo"] == 5.0


def test_retener_debitar_liberar(sistema):
    bd, bil, srv = sistema
    bil.recargar("sim_v1", 5, ts=en(0))
    ses = srv.iniciar("sim_v1", "SIM-0001", "pa_mock0_0", ts=en(1))
    assert bil.estado("sim_v1") == {"saldo": 5.0, "retenido": 0.25, "disponible": 4.75, "bloqueada": False}
    with pytest.raises(ValueError):
        bil.liberar("sim_v1", 26, ses.sesion_id)
    with pytest.raises(ValueError):
        bil.debitar("sim_v1", 0, ses.sesion_id)
    movs = bil.movimientos("sim_v1")
    assert [m.tipo for m in movs] == [e.TipoMovimiento.recarga, e.TipoMovimiento.retencion]
    assert movs[1].sesion_id == ses.sesion_id
    contrato = bil.como_contrato("sim_v1")
    assert isinstance(contrato, e.Billetera) and contrato.disponible == 4.75


def test_transaccion_atomica(sistema):
    """Si algo falla dentro de la transacción, no queda ningún movimiento a medias."""
    bd, bil, _ = sistema
    with pytest.raises(RuntimeError):
        with bd.transaccion() as s:
            bil.recargar("sim_v2", 5, s=s)
            bil.recargar("sim_v2", 5, s=s)
            raise RuntimeError("falla a mitad de camino")
    with bd.fabrica() as s:
        assert s.scalar(select(func.count()).select_from(Movimiento)) == 0
    assert bil.estado("sim_v2")["saldo"] == 0.0


def test_error_nucleo_cuerpo_contrato():
    err = ErrorNucleo(e.CodigoError.PUESTO_LLENO, "lleno", {"puesto_id": "pa_a_0"})
    cuerpo = err.cuerpo().model_dump(mode="json")
    assert cuerpo == {"error": {"codigo": "PUESTO_LLENO", "mensaje": "lleno", "detalle": {"puesto_id": "pa_a_0"}}}
    assert err.http == 409
