"""Propiedad del libro: con 200 operaciones aleatorias, el saldo siempre cuadra."""

import random

import pytest

from backend.nucleo import tarifa as tar
from backend.nucleo.errores import ErrorNucleo
from comun import esquemas as e

from .conftest import armar, en

TM = e.TipoMovimiento


def _invariantes(bil, srv, usuarios):
    for u in usuarios:
        movs = bil.movimientos(u)
        suma = {t: sum(tar.centavos(m.monto) for m in movs if m.tipo is t) for t in TM}
        est = bil.estado_centavos(u)
        assert est["saldo"] == suma[TM.recarga] - suma[TM.debito]
        assert est["retenido"] == suma[TM.retencion] - suma[TM.liberacion]
        assert est["disponible"] == est["saldo"] - est["retenido"]
        abierta = srv.sesion_abierta(u)
        assert est["retenido"] == (tar.centavos(tar.retencion()) if abierta else 0)

    # El mapa coincide con las sesiones abiertas (de todos los usuarios).
    usuarios = [f"sim_veh{i}" for i in range(8)]
    abiertas = [srv.obtener(srv.sesion_abierta(u)).puesto_id for u in usuarios if srv.sesion_abierta(u)]
    for pid in srv.mapa.puestos:
        assert srv.mapa.ocupados(pid) == abiertas.count(pid)


@pytest.mark.parametrize("semilla", [0, 1, 2, 3, 4])
def test_saldo_igual_recargas_menos_debitos(semilla):
    rnd = random.Random(semilla)
    _, bil, srv = armar()
    usuarios = [f"sim_veh{i}" for i in range(8)]
    reloj = {u: 0.0 for u in usuarios}
    errores = 0
    for _ in range(200):
        u = rnd.choice(usuarios)
        reloj[u] += rnd.uniform(1, 300)
        accion = rnd.random()
        try:
            if accion < 0.25:
                bil.recargar(u, rnd.choice([5, 5, 10, 4]), ts=en(reloj[u]))
            elif accion < 0.6:
                srv.iniciar(u, "SIM-0001", rnd.choice(list(srv.mapa.puestos)), en(reloj[u]))
            else:
                sid = srv.sesion_abierta(u)
                if sid is not None:
                    srv.cerrar(sid, en(reloj[u]), e.MotivoCierre.manual)
        except ErrorNucleo:
            errores += 1
        _invariantes(bil, srv, [u])  # el usuario tocado, en cada paso
    _invariantes(bil, srv, usuarios)  # todos, al final
    assert errores > 0  # también se ejercitaron los caminos de error
