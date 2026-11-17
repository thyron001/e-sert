"""`correr_kpis.volcado` (S4-1): el JSON que leen las pruebas e2e cuadra con el núcleo. Sin SUMO."""

from types import SimpleNamespace

from traci.clasificacion import buscar_proyecto
from traci.correr_kpis import volcado
from traci.puente_nucleo import PuenteNucleo


def test_volcado_cuadra_saldo_con_recargas_y_debitos():
    puente = PuenteNucleo(buscar_proyecto() / "sumo" / "parqueos" / "puestos.csv", semilla=1)
    pid = next(iter(puente.mapa.puestos))
    for i, (inicio, fin) in enumerate([(0, 600), (100, 4000)]):
        u = f"sim_veh{i}"
        puente.registrar(u)
        sid = puente.iniciar(u, pid, inicio)
        puente.transicion(sid, "SALIENDO", fin)
        puente.cerrar(sid, fin)
    kpis = SimpleNamespace(sesiones=[{**f, "veh": f["usuario_id"][4:], "falsa": False} for f in puente.cerradas])

    d = volcado(puente, kpis, {"kpis": {"precision_mapa_app": 1.0}})

    assert set(d["recargas_usd"]) == {"sim_veh0", "sim_veh1"} and d["abiertas"] == 0
    for u, recarga in d["recargas_usd"].items():
        debitos = sum(round(s["debitado"] * 100) for s in d["cerradas"] if s["usuario_id"] == u)
        assert d["libro"][u]["recarga_centavos"] == round(recarga * 100)
        assert d["libro"][u]["debito_centavos"] == debitos > 0
        assert d["estado_billetera_centavos"][u]["saldo"] == round(recarga * 100) - debitos
        assert d["estado_billetera_centavos"][u]["retenido"] == 0
    assert [s["falsa"] for s in d["sesiones_kpi"]] == [False, False]
