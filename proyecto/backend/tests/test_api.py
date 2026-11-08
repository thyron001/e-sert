"""Tests de la capa REST (FastAPI) sobre SQLite en memoria (contrato §4)."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from backend.api import ejemplos as ej
from backend.api.main import Config, crear_app, openapi_json
from comun import esquemas as e

PREF = "/api/v1"
P1, P2 = "pa_a_0", "pa_b_0"
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _csv(tmp_path, filas):
    ruta = tmp_path / "puestos.csv"
    ruta.write_text("puesto_id,edge,lane,calle,capacidad,lat,lon,x,y\n"
                    + "".join(f"{p},e,l,{c},{cap},{la},{lo},0,0\n" for p, c, cap, la, lo in filas),
                    encoding="utf-8")
    return str(ruta)


@pytest.fixture
def cliente(tmp_path):
    """Dos puestos de capacidad 1 cerca del Parque Calderón."""
    csv = _csv(tmp_path, [(P1, "A", 1, -2.8970, -79.0040), (P2, "B", 1, -2.8990, -79.0060)])
    app = crear_app(Config(db_url="sqlite:///:memory:", puestos_csv=csv, token_sim="secreto", visor_dir=None))
    with TestClient(app) as c:
        yield c


def _error(r, estado, codigo):
    assert r.status_code == estado, r.text
    cuerpo = r.json()
    e.CuerpoError.model_validate(cuerpo)
    assert set(cuerpo) == {"error"} and cuerpo["error"]["codigo"] == codigo
    assert r.headers["X-Contrato-Version"] == "1"
    return cuerpo


def _recargar(c, usuario="sim_veh42", monto=5):
    return c.post(f"{PREF}/billetera/{usuario}/recarga", json={"monto": monto})


def _iniciar(c, usuario="sim_veh42", puesto=P1, **extra):
    return c.post(f"{PREF}/sesiones", json={"usuario_id": usuario, "placa": "SIM-0042", "puesto_id": puesto,
                                            "ts": "2026-10-20T14:00:00Z", **extra})


TOKEN = {"X-Sim-Token": "secreto"}


# ---------------------------------------------------------------- flujo feliz


def test_flujo_feliz_47_minutos(cliente):
    r = _recargar(cliente)
    assert r.status_code == 201 and r.json()["saldo"] == 5.0
    assert re.fullmatch(rf"mov_{UUID}", r.json()["movimiento_id"])

    r = _iniciar(cliente)
    assert r.status_code == 201
    creada = e.SesionCreada.model_validate(r.json())
    assert creada.retenido == 0.25
    sid = creada.sesion_id

    r = cliente.get(f"{PREF}/sesiones/{sid}")
    ses = e.Sesion.model_validate(r.json())
    assert ses.estado is e.EstadoSesion.ESTACIONADO and ses.fin is None and ses.debitado is None

    b = cliente.get(f"{PREF}/billetera/sim_veh42").json()
    assert (b["saldo"], b["retenido"], b["disponible"]) == (5.0, 0.25, 4.75)
    assert cliente.get(f"{PREF}/puestos").json()[0]["ocupados"] == 1

    r = cliente.post(f"{PREF}/sesiones/{sid}/cerrar", json={"ts": "2026-10-20T14:47:00Z", "motivo": "manual"})
    cerrada = e.SesionCerrada.model_validate(r.json())
    # 47 min → 50 cobrados (fracciones de 5) → 50 · 0,50 / 60 = 0,4167 → $0,42
    assert (cerrada.minutos_reales, cerrada.minutos_cobrados, cerrada.debitado, cerrada.saldo) == (47.0, 50, 0.42, 4.58)

    b = e.Billetera.model_validate(cliente.get(f"{PREF}/billetera/sim_veh42").json())
    assert (b.saldo, b.retenido, b.disponible, b.bloqueada) == (4.58, 0.0, 4.58, False)
    assert sorted(m.tipo.value for m in b.movimientos) == ["debito", "liberacion", "recarga", "retencion"]
    assert cliente.get(f"{PREF}/sesiones/{sid}").json()["estado"] == "CERRADA"
    assert cliente.get(f"{PREF}/puestos").json()[0]["ocupados"] == 0


def test_cobro_con_t_sim_y_ciclo_de_deteccion(cliente):
    _recargar(cliente)
    sid = _iniciar(cliente, t_sim=100.0).json()["sesion_id"]
    for estado in ("A_PIE", "REGRESANDO", "SALIENDO"):
        r = cliente.post(f"{PREF}/sesiones/{sid}/transicion", headers=TOKEN,
                         json={"estado": estado, "ts": "2026-10-20T14:10:00Z"})
        assert r.status_code == 200 and r.json() == {"sesion_id": sid, "estado": estado}
    # El reloj de SUMO manda: 100 s → 1300 s son 20 min aunque `ts` diga otra cosa.
    r = cliente.post(f"{PREF}/sesiones/{sid}/cerrar",
                     json={"ts": "2026-10-20T18:00:00Z", "t_sim": 1300.0, "motivo": "deteccion"})
    assert r.json()["minutos_reales"] == 20.0 and r.json()["debitado"] == round(20 * 0.5 / 60 + 1e-9, 2)
    ses = cliente.get(f"{PREF}/sesiones/{sid}").json()
    assert ses["t_sim_inicio"] == 100.0 and ses["t_sim_fin"] == 1300.0


def test_billetera_implicita_con_saldo_cero(cliente):
    b = cliente.get(f"{PREF}/billetera/app_7f1c2d3e-4a5b-4c6d-8e7f-001122334455").json()
    assert b == {"saldo": 0.0, "retenido": 0.0, "disponible": 0.0, "bloqueada": False, "movimientos": []}


# ---------------------------------------------------------------- guía y puestos


def test_guia_nunca_devuelve_puesto_lleno_y_404_sin_libres(cliente):
    q = {"lat": -2.8970, "lon": -79.0040, "destino_lat": -2.8970, "destino_lon": -79.0040}
    g = e.Guia.model_validate(cliente.get(f"{PREF}/guia", params=q).json())
    assert g.puesto_id == P1 and g.distancia_m == 0.0

    _recargar(cliente, "sim_a"); _recargar(cliente, "sim_b")
    assert _iniciar(cliente, "sim_a", P1).status_code == 201
    g = cliente.get(f"{PREF}/guia", params=q).json()
    assert g["puesto_id"] == P2 and g["distancia_m"] > 0  # P1 está lleno

    assert _iniciar(cliente, "sim_b", P2).status_code == 201
    _error(cliente.get(f"{PREF}/guia", params=q), 404, "SIN_PUESTOS_LIBRES")


def test_guia_valida_parametros(cliente):
    _error(cliente.get(f"{PREF}/guia", params={"lat": 200, "lon": 0, "destino_lat": 0, "destino_lon": 0}),
           422, "VALIDACION")
    _error(cliente.get(f"{PREF}/guia"), 422, "VALIDACION")


def test_puestos_formato(cliente):
    puestos = [e.Puesto.model_validate(p) for p in cliente.get(f"{PREF}/puestos").json()]
    assert [(p.puesto_id, p.calle, p.capacidad, p.ocupados) for p in puestos] == [(P1, "A", 1, 0), (P2, "B", 1, 0)]


def test_tarifa_y_salud(cliente):
    t = cliente.get(f"{PREF}/tarifa").json()
    assert e.Tarifa.model_validate(t).bloque_minimo_min == 30
    for ruta in ("/salud", f"{PREF}/salud"):
        salud = cliente.get(ruta).json()
        assert e.Salud.model_validate(salud).ts is not None  # v1.2: hora del servidor (la app mide su desfase)
        assert {k: salud[k] for k in ("ok", "contrato", "t_sim")} == {"ok": True, "contrato": 1, "t_sim": None}


# ---------------------------------------------------------------- eventos


def test_eventos_202_y_ultimo_estado(cliente):
    ub = ej.cargar("ubicacion")
    r = cliente.post(f"{PREF}/eventos/ubicacion", json=ub)
    assert r.status_code == 202 and r.json() == {"aceptado": True}
    viejo = {**ub, "ts": "2000-01-01T00:00:00Z", "lat": 0.0}
    assert cliente.post(f"{PREF}/eventos/ubicacion", json=viejo).status_code == 202
    modo = ej.cargar("modo")
    assert cliente.post(f"{PREF}/eventos/modo", json=modo).status_code == 202

    mundo = cliente.app.state.servicios.mundo
    u = mundo.ultimo(ub["usuario_id"])
    assert u.ubicacion.lat == ub["lat"]  # el evento más viejo no pisa al más nuevo
    assert mundo.ultimo(modo["usuario_id"]).modo.modo.value == modo["modo"]


def test_eventos_validan_contrato(cliente):
    ub = ej.cargar("ubicacion")
    _error(cliente.post(f"{PREF}/eventos/ubicacion", json={**ub, "ts": "2026-10-20T14:03:05"}), 422, "VALIDACION")
    _error(cliente.post(f"{PREF}/eventos/ubicacion", json={**ub, "extra": 1}), 422, "VALIDACION")
    _error(cliente.post(f"{PREF}/eventos/modo", json={**ej.cargar("modo"), "confianza": 2}), 422, "VALIDACION")


# ---------------------------------------------------------------- errores


def test_saldo_insuficiente_402(cliente):
    cuerpo = _error(_iniciar(cliente), 402, "SALDO_INSUFICIENTE")
    assert cuerpo["error"]["detalle"] == {"disponible": 0.0, "retencion": 0.25}


def test_puesto_lleno_409_y_sesion_activa_409(cliente):
    _recargar(cliente, "sim_a"); _recargar(cliente, "sim_b")
    assert _iniciar(cliente, "sim_a").status_code == 201
    _error(_iniciar(cliente, "sim_b"), 409, "PUESTO_LLENO")
    _error(_iniciar(cliente, "sim_a", P2), 409, "SESION_ACTIVA")


def test_sesiones_bloqueadas_403(cliente):
    _recargar(cliente)
    sid = _iniciar(cliente).json()["sesion_id"]
    # 20 h → $10 de débito con $5 de saldo: queda negativo y bloqueada.
    r = cliente.post(f"{PREF}/sesiones/{sid}/cerrar", json={"ts": "2026-10-21T10:00:00Z", "motivo": "manual"})
    assert r.json()["saldo"] < 0
    assert cliente.get(f"{PREF}/billetera/sim_veh42").json()["bloqueada"] is True
    _error(_iniciar(cliente), 403, "SESIONES_BLOQUEADAS")


def test_sesion_no_existe_404(cliente):
    sid = "ses_00000000-0000-4000-8000-000000000000"
    _error(cliente.get(f"{PREF}/sesiones/{sid}"), 404, "SESION_NO_EXISTE")
    _error(cliente.post(f"{PREF}/sesiones/{sid}/cerrar", json={"ts": "2026-10-20T14:00:00Z", "motivo": "manual"}),
           404, "SESION_NO_EXISTE")
    _error(cliente.post(f"{PREF}/sesiones/{sid}/transicion", headers=TOKEN,
                        json={"estado": "A_PIE", "ts": "2026-10-20T14:00:00Z"}), 404, "SESION_NO_EXISTE")
    _error(cliente.get(f"{PREF}/sesiones/no-es-un-id"), 422, "VALIDACION")


def test_puesto_no_existe_404(cliente):
    _recargar(cliente)
    _error(_iniciar(cliente, puesto="pa_inventado_0"), 404, "PUESTO_NO_EXISTE")


def test_transiciones_invalidas_y_sesion_cerrada(cliente):
    _recargar(cliente)
    sid = _iniciar(cliente).json()["sesion_id"]
    cuerpo = {"estado": "REGRESANDO", "ts": "2026-10-20T14:05:00Z"}
    _error(cliente.post(f"{PREF}/sesiones/{sid}/transicion", headers=TOKEN, json=cuerpo), 409, "TRANSICION_INVALIDA")
    _error(cliente.post(f"{PREF}/sesiones/{sid}/cerrar", json={"ts": "2026-10-20T14:05:00Z", "motivo": "deteccion"}),
           409, "TRANSICION_INVALIDA")
    cliente.post(f"{PREF}/sesiones/{sid}/cerrar", json={"ts": "2026-10-20T14:05:00Z", "motivo": "manual"})
    _error(cliente.post(f"{PREF}/sesiones/{sid}/cerrar", json={"ts": "2026-10-20T14:06:00Z", "motivo": "manual"}),
           409, "SESION_YA_CERRADA")
    _error(cliente.post(f"{PREF}/sesiones/{sid}/transicion", headers=TOKEN,
                        json={"estado": "A_PIE", "ts": "2026-10-20T14:06:00Z"}), 409, "SESION_YA_CERRADA")


def test_transicion_exige_token(cliente):
    _recargar(cliente)
    sid = _iniciar(cliente).json()["sesion_id"]
    cuerpo = {"estado": "A_PIE", "ts": "2026-10-20T14:05:00Z"}
    _error(cliente.post(f"{PREF}/sesiones/{sid}/transicion", json=cuerpo), 401, "TOKEN_SIM_INVALIDO")
    _error(cliente.post(f"{PREF}/sesiones/{sid}/transicion", json=cuerpo, headers={"X-Sim-Token": "x"}),
           401, "TOKEN_SIM_INVALIDO")
    r = cliente.post(f"{PREF}/sesiones/{sid}/transicion", json=cuerpo, headers={"Authorization": "Bearer secreto"})
    assert r.status_code == 200


def test_recarga_minima_y_validacion(cliente):
    _error(_recargar(cliente, monto=3), 422, "RECARGA_MINIMA")
    _error(_recargar(cliente, monto=0), 422, "VALIDACION")
    _error(cliente.post(f"{PREF}/billetera/pepito/recarga", json={"monto": 5}), 422, "VALIDACION")
    _error(cliente.post(f"{PREF}/sesiones", content=b"{no es json", headers={"Content-Type": "application/json"}),
           422, "VALIDACION")


def test_contrato_incompatible_400(cliente):
    _error(cliente.get(f"{PREF}/puestos", headers={"X-Contrato-Version": "2"}), 400, "CONTRATO_INCOMPATIBLE")
    assert cliente.get(f"{PREF}/puestos", headers={"X-Contrato-Version": "1"}).status_code == 200


def test_ruta_o_metodo_inexistente_con_formato(cliente):
    for r, estado in ((cliente.get(f"{PREF}/no-existe"), 404), (cliente.delete(f"{PREF}/puestos"), 405)):
        assert r.status_code == estado and r.headers["X-Contrato-Version"] == "1"
        assert e.CuerpoError.model_validate(r.json()).error.codigo is e.CodigoError.VALIDACION


def test_error_interno_500_con_formato(tmp_path):
    app = crear_app(Config(db_url="sqlite:///:memory:", visor_dir=None))

    @app.get("/explota")
    def explota():
        raise RuntimeError("bum")

    with TestClient(app, raise_server_exceptions=False) as c:
        _error(c.get("/explota"), 500, "ERROR_INTERNO")


def test_sin_token_configurado_las_rutas_sim_quedan_abiertas(tmp_path):
    app = crear_app(Config(db_url="sqlite:///:memory:", visor_dir=None))
    with TestClient(app) as c:
        assert c.post(f"{PREF}/sim/paso", json=ej.cargar("sim_paso")).status_code == 202


# ---------------------------------------------------------------- transversal


def test_header_contrato_en_todas_las_respuestas(cliente):
    sid = "ses_00000000-0000-4000-8000-000000000000"
    respuestas = [
        cliente.get("/salud"), cliente.get(f"{PREF}/salud"), cliente.get(f"{PREF}/tarifa"),
        cliente.get(f"{PREF}/puestos"), cliente.get(f"{PREF}/guia"),
        cliente.post(f"{PREF}/eventos/modo", json=ej.cargar("modo")),
        cliente.get(f"{PREF}/sesiones/{sid}"), cliente.get(f"{PREF}/billetera/sim_x"),
        cliente.get(f"{PREF}/espejo/candidatos"), cliente.get("/no-existe"), cliente.get("/docs"),
        cliente.get("/openapi.json"),
    ]
    assert all(r.headers.get("X-Contrato-Version") == "1" for r in respuestas)


def test_cors_abierto_por_defecto(cliente):
    r = cliente.options(f"{PREF}/puestos", headers={"Origin": "http://localhost:8081",
                                                   "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] in ("*", "http://localhost:8081")


def test_config_por_entorno(monkeypatch):
    monkeypatch.setenv("ESERT_DB_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ESERT_TOKEN_SIM", "t0k3n")
    monkeypatch.setenv("ESERT_CORS_ORIGENES", "https://demo.e-sert.tesisucuenca.com, http://localhost:8081")
    cfg = Config()
    assert cfg.db_url == "sqlite:///:memory:" and cfg.token_sim == "t0k3n"
    assert cfg.origenes() == ["https://demo.e-sert.tesisucuenca.com", "http://localhost:8081"]
    monkeypatch.delenv("ESERT_DB_URL")
    monkeypatch.setenv("E_SERT_DB_URL", "sqlite:///otra.db")
    assert Config().db_url == "sqlite:///otra.db"


def test_visor_estatico(tmp_path):
    (tmp_path / "index.html").write_text("<h1>visor</h1>", encoding="utf-8")
    app = crear_app(Config(db_url="sqlite:///:memory:", visor_dir=str(tmp_path)))
    with TestClient(app) as c:
        assert "visor" in c.get("/visor/").text


def test_pagos_se_monta_si_existe(monkeypatch):
    import sys
    import types

    from fastapi import APIRouter

    router = APIRouter(prefix="/pagos")
    router.get("/retorno")(lambda: {"ok": True})
    mod = types.ModuleType("backend.pagos.rutas")
    mod.router = router
    monkeypatch.setitem(sys.modules, "backend.pagos", types.ModuleType("backend.pagos"))
    monkeypatch.setitem(sys.modules, "backend.pagos.rutas", mod)
    app = crear_app(Config(db_url="sqlite:///:memory:", visor_dir=None))
    assert app.state.pagos_montado
    with TestClient(app) as c:
        assert c.get(f"{PREF}/pagos/retorno").json() == {"ok": True}


def test_app_perezosa_y_atributo_desconocido(monkeypatch, tmp_path):
    import backend.api.main as m

    monkeypatch.setenv("ESERT_DB_URL", "sqlite:///:memory:")
    monkeypatch.setattr(m, "_app", None)
    assert m.app is m.app
    with pytest.raises(AttributeError):
        m.no_existe  # noqa: B018


# ---------------------------------------------------------------- OpenAPI


RUTAS_CONTRATO = {
    ("get", "/api/v1/salud"), ("get", "/api/v1/tarifa"), ("get", "/api/v1/puestos"), ("get", "/api/v1/guia"),
    ("post", "/api/v1/sim/paso"), ("post", "/api/v1/eventos/ubicacion"), ("post", "/api/v1/eventos/modo"),
    ("post", "/api/v1/sesiones"), ("post", "/api/v1/sesiones/{sesion_id}/transicion"),
    ("post", "/api/v1/sesiones/{sesion_id}/cerrar"), ("get", "/api/v1/sesiones/{sesion_id}"),
    ("get", "/api/v1/billetera/{usuario_id}"), ("post", "/api/v1/billetera/{usuario_id}/recarga"),
    ("get", "/api/v1/espejo/candidatos"),
}


def test_openapi_tiene_todas_las_rutas_con_ejemplos():
    esquema = json.loads(openapi_json())
    assert esquema["info"]["title"] == "e-sert API" and esquema["info"]["version"] == "1"
    presentes = {(m, p) for p, ops in esquema["paths"].items() for m in ops}
    assert RUTAS_CONTRATO <= presentes
    for metodo, ruta in presentes:
        op = esquema["paths"][ruta][metodo]
        assert op.get("tags"), ruta
        exito = next(v for k, v in op["responses"].items() if k.startswith("2"))
        contenido = exito["content"]["application/json"]
        assert "example" in contenido or "examples" in contenido, f"{metodo} {ruta} sin ejemplo"
        if "requestBody" in op:
            assert op["requestBody"]["content"]["application/json"].get("examples"), f"{ruta} sin ejemplo de cuerpo"


def test_exportar_openapi(tmp_path):
    from backend.api.exportar_openapi import main

    salida = main([str(tmp_path / "openapi.json")])
    assert json.loads(salida.read_text(encoding="utf-8"))["info"]["title"] == "e-sert API"
