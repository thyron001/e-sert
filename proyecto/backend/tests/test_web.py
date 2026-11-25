"""App web (`/api/v1/web/*`): ciclo completo con pasos simulados del controlador."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import Config, crear_app
from backend.web.servicio import codigos_de

LAT, LON = -2.8975, -79.0045


class Sim:
    """Hace de controlador: manda pasos a `/sim/paso` con el detalle del espejo y los eventos web."""

    def __init__(self, c: TestClient):
        self.c = c
        self.t = 100.0
        self.respuesta = {}

    def paso(self, t=None, detalle=None, web=None, ocupados=None):
        self.t = self.t + 1 if t is None else t
        cuerpo = {"t_sim": self.t, "ts": "2026-11-18T03:00:00Z", "vehiculos": [], "peatones": [],
                  "verdad": {"puestos": [{"puesto_id": p, "ocupados": n, "capacidad": 50}
                                         for p, n in (ocupados or {}).items()],
                             "estacionados": [], "falsas_liberaciones": []},
                  "espejo": {"candidatos": [], "detalle": {
                      v: {"t_sim": self.t, "estado": est, "lat": LAT, "lon": LON, "ruta": [[LAT, LON]]}
                      for v, est in (detalle or {}).items()}}}
        if web:
            cuerpo["web"] = web
        r = self.c.post("/api/v1/sim/paso", json=cuerpo)
        assert r.status_code == 202, r.text
        self.respuesta = r.json()
        self.respuesta["ordenes"] = [{k: v for k, v in o.items() if v is not None} for o in self.respuesta["ordenes"]]
        return self.respuesta


@pytest.fixture
def entorno():
    app = crear_app(Config(db_url="sqlite:///:memory:"))
    with TestClient(app) as c:
        uid = c.post("/api/v1/web/usuarios").json()["usuario_id"]
        yield c, Sim(c), uid


def estado(c, uid):
    return c.get(f"/api/v1/web/usuarios/{uid}").json()


def test_usuario_nuevo_con_5_dolares(entorno):
    c, _, uid = entorno
    d = estado(c, uid)
    assert uid.startswith("app_") and d["saldo"] == 5.0 and d["sesion"] is None


def test_sin_simulacion_no_se_puede_buscar(entorno):
    c, _, uid = entorno
    r = c.post(f"/api/v1/web/usuarios/{uid}/buscar", json={"lat": LAT, "lon": LON})
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "DEMO_NO_DISPONIBLE"


def test_ciclo_completo_buscar_pagar_renovar_maximo_y_salir(entorno):
    c, sim, uid = entorno
    sim.paso()
    r = c.post(f"/api/v1/web/usuarios/{uid}/buscar", json={"lat": LAT, "lon": LON})
    assert r.status_code == 202 and r.json()["sesion"]["estado"] == "pendiente"
    veh = r.json()["sesion"]["veh_id"]
    # el backend ordena crear el auto y lo sigue
    resp = sim.paso()
    assert resp["ordenes"] == [{"tipo": "buscar", "veh_id": veh, "lat": LAT, "lon": LON}]
    assert veh in resp["espejos"]
    assert c.post(f"/api/v1/web/usuarios/{uid}/buscar", json={"lat": LAT, "lon": LON}).status_code == 409
    # el controlador asigna el puesto
    pid = sorted(c.app.state.servicios.web.puestos)[0]
    sim.paso(web=[{"tipo": "asignado", "veh_id": veh, "puesto_id": pid}], detalle={veh: "GUIADO"})
    d = estado(c, uid)["sesion"]
    assert d["estado"] == "yendo" and d["puesto"]["codigo"] == "001" and d["auto"]["ruta"]
    # la IA detecta que estacionó y se bajó
    sim.paso(t=200, detalle={veh: "A_PIE"})
    assert estado(c, uid)["sesion"]["estado"] == "llego"
    # elige una hora: se debita de inmediato
    d = c.post(f"/api/v1/web/usuarios/{uid}/tiempo", json={"minutos": 60}).json()
    assert d["saldo"] == 4.5 and d["sesion"]["estado"] == "activa" and d["sesion"]["restante_s"] == 3600
    # a 5 min del final: alerta
    sim.paso(t=200 + 3600 - 299, detalle={veh: "A_PIE"})
    assert "0,25" in estado(c, uid)["sesion"]["alerta"]
    # al llegar a 0 se renueva sola
    sim.paso(t=200 + 3600, detalle={veh: "A_PIE"})
    d = estado(c, uid)
    assert d["saldo"] == 4.25 and d["sesion"]["pagado_min"] == 90 and d["sesion"]["estado"] == "activa"
    # extender a mano hasta el máximo
    d = c.post(f"/api/v1/web/usuarios/{uid}/extender", json={"minutos": 30}).json()
    assert d["saldo"] == 4.0 and d["sesion"]["pagado_min"] == 120 and d["sesion"]["puede_extender"] is False
    assert c.post(f"/api/v1/web/usuarios/{uid}/extender", json={"minutos": 30}).status_code == 422
    # en el máximo, al llegar a 0 el conductor vuelve
    fin = estado(c, uid)["sesion"]["pagado_hasta"]
    sim.paso(t=fin - 100, detalle={veh: "A_PIE"})
    assert "máximo" in estado(c, uid)["sesion"]["alerta"]
    resp = sim.paso(t=fin, detalle={veh: "A_PIE"})
    assert estado(c, uid)["sesion"]["estado"] == "volviendo"
    assert {"tipo": "volver", "veh_id": veh} in sim.paso(detalle={veh: "REGRESANDO"})["ordenes"] + resp["ordenes"]
    assert estado(c, uid)["sesion"]["estado"] == "volviendo"  # regresando no basta
    # la IA detecta que volvió a manejar: se cierra
    sim.paso(detalle={veh: "SALIENDO"})
    d = estado(c, uid)
    assert d["sesion"]["estado"] == "cerrada" and d["sesion"]["debitado"] == 1.0 and d["saldo"] == 4.0
    assert veh not in sim.paso()["espejos"]


def test_ya_estacione_con_codigo_y_me_voy(entorno):
    c, sim, uid = entorno
    sim.paso()
    w = c.app.state.servicios.web
    pid = sorted(w.puestos)[4]
    r = c.post(f"/api/v1/web/usuarios/{uid}/estacionado", json={"codigo": "5"})
    assert r.status_code == 202
    veh = r.json()["sesion"]["veh_id"]
    assert sim.paso()["ordenes"] == [{"tipo": "estacionado", "veh_id": veh, "puesto_id": pid}]
    sim.paso(web=[{"tipo": "asignado", "veh_id": veh, "puesto_id": pid}], detalle={veh: "ESTACIONADO"})
    d = estado(c, uid)["sesion"]
    assert d["estado"] == "llego" and d["puesto"]["codigo"] == "005"
    c.post(f"/api/v1/web/usuarios/{uid}/tiempo", json={"minutos": 30})
    assert estado(c, uid)["saldo"] == 4.75
    assert c.post(f"/api/v1/web/usuarios/{uid}/me-voy").json()["sesion"]["estado"] == "volviendo"
    assert {"tipo": "volver", "veh_id": veh} in sim.paso(detalle={veh: "A_PIE"})["ordenes"]
    sim.paso(detalle={veh: "SALIENDO"})
    assert estado(c, uid)["sesion"]["estado"] == "cerrada"


def test_codigo_inexistente_y_puesto_lleno(entorno):
    c, sim, uid = entorno
    w = c.app.state.servicios.web
    pid = sorted(w.puestos)[0]
    sim.paso(ocupados={pid: 50})
    assert c.post(f"/api/v1/web/usuarios/{uid}/estacionado", json={"codigo": "999"}).json()["error"]["codigo"] == "PUESTO_NO_EXISTE"
    w.puestos[pid] = w.puestos[pid]._replace(capacidad=50) if hasattr(w.puestos[pid], "_replace") else w.puestos[pid]
    r = c.post(f"/api/v1/web/usuarios/{uid}/estacionado", json={"codigo": "001"})
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "PUESTO_LLENO"


def test_sin_elegir_tiempo_se_cobran_30_min(entorno):
    c, sim, uid = entorno
    sim.paso()
    veh = c.post(f"/api/v1/web/usuarios/{uid}/buscar", json={"lat": LAT, "lon": LON}).json()["sesion"]["veh_id"]
    pid = sorted(c.app.state.servicios.web.puestos)[0]
    sim.paso(web=[{"tipo": "asignado", "veh_id": veh, "puesto_id": pid}])
    sim.paso(t=500, detalle={veh: "ESTACIONADO"})
    assert estado(c, uid)["sesion"]["eleccion_restante_s"] == 300
    sim.paso(t=800, detalle={veh: "A_PIE"})
    d = estado(c, uid)
    assert d["sesion"]["estado"] == "activa" and d["sesion"]["pagado_min"] == 30 and d["saldo"] == 4.75


def test_sin_puesto_libre_cierra_con_mensaje(entorno):
    c, sim, uid = entorno
    sim.paso()
    veh = c.post(f"/api/v1/web/usuarios/{uid}/buscar", json={"lat": LAT, "lon": LON}).json()["sesion"]["veh_id"]
    sim.paso(web=[{"tipo": "sin_puesto", "veh_id": veh}])
    d = estado(c, uid)["sesion"]
    assert d["estado"] == "cerrada" and "libres" in d["mensaje"]
    assert estado(c, uid)["saldo"] == 5.0


def test_validaciones(entorno):
    c, sim, uid = entorno
    sim.paso()
    assert c.post(f"/api/v1/web/usuarios/{uid}/buscar", json={"lat": 10, "lon": LON}).status_code == 422
    assert c.get("/api/v1/web/usuarios/sim_x").status_code == 422
    assert c.post(f"/api/v1/web/usuarios/{uid}/tiempo", json={"minutos": 45}).status_code in (409, 422)
    assert c.post(f"/api/v1/web/usuarios/{uid}/me-voy").status_code == 404


def test_puestos_con_codigo():
    assert codigos_de(["pa_b_0", "pa_a_0", "pa_c_0"]) == {"pa_a_0": "001", "pa_b_0": "002", "pa_c_0": "003"}
    app = crear_app(Config(db_url="sqlite:///:memory:"))
    with TestClient(app) as c:
        lista = c.get("/api/v1/web/puestos").json()
    assert lista and lista[0]["codigo"] == "001" and {"lat", "lon", "capacidad", "ocupados"} <= set(lista[0])


def test_un_regresando_pasajero_no_cierra_la_sesion(entorno):
    """La máquina de estados marca a veces REGRESANDO un momento y vuelve a A_PIE (falsa alarma)."""
    c, sim, uid = entorno
    sim.paso()
    veh = c.post(f"/api/v1/web/usuarios/{uid}/buscar", json={"lat": LAT, "lon": LON}).json()["sesion"]["veh_id"]
    pid = sorted(c.app.state.servicios.web.puestos)[0]
    sim.paso(web=[{"tipo": "asignado", "veh_id": veh, "puesto_id": pid}])
    sim.paso(t=300, detalle={veh: "A_PIE"})
    c.post(f"/api/v1/web/usuarios/{uid}/tiempo", json={"minutos": 60})
    sim.paso(t=305, detalle={veh: "REGRESANDO"})
    sim.paso(t=360, detalle={veh: "A_PIE"})
    assert estado(c, uid)["sesion"]["estado"] == "activa"


# --------------------------------------------------------------------------- perfiles, historial, IA

def test_perfiles_fijos_con_saldo_inicial_una_sola_vez():
    from backend.web.servicio import PERFILES, id_perfil
    app = crear_app(Config(db_url="sqlite:///:memory:"))
    with TestClient(app) as c:
        p = c.get("/api/v1/web/perfiles").json()
        assert [x["nombre"] for x in p] == list(PERFILES) and len(p) == 9
        assert [x["saldo"] for x in p] == [10.0] * 4 + [5.0] * 5   # equipo $10, cinco invitados $5
        assert len({x["usuario_id"] for x in p}) == 9
        assert c.get("/api/v1/web/perfiles").json()[0]["saldo"] == 10.0   # no se recarga otra vez
        uid = id_perfil("Tyrone Novillo")
        assert p[0]["usuario_id"] == uid and c.get(f"/api/v1/web/usuarios/{uid}").json()["nombre"] == "Tyrone Novillo"


def test_historial_y_activos(entorno):
    c, sim, uid = entorno
    sim.paso()
    veh = c.post(f"/api/v1/web/usuarios/{uid}/buscar", json={"lat": LAT, "lon": LON}).json()["sesion"]["veh_id"]
    assert c.get("/api/v1/web/activos").json()[0]["veh_id"] == veh
    sim.paso(web=[{"tipo": "sin_puesto", "veh_id": veh}])
    assert c.get("/api/v1/web/activos").json() == []
    h = c.get(f"/api/v1/web/usuarios/{uid}/historial").json()
    assert len(h) == 1 and h[0]["motivo"] == "sin_puesto"


def test_probar_ia_clasifica_con_el_rf():
    app = crear_app(Config(db_url="sqlite:///:memory:"))
    # 30 s caminando hacia el norte a ~1,3 m/s, y 30 s en auto a ~10 m/s
    a_pie = [{"t": i, "lat": -2.9 + i * 1.3 / 111320, "lon": -79.0, "precision_m": 5} for i in range(30)]
    auto = [{"t": i, "lat": -2.9 + i * 10 / 111320, "lon": -79.0, "precision_m": 5} for i in range(30)]
    with TestClient(app) as c:
        r1 = c.post("/api/v1/web/ia/clasificar", json={"muestras": a_pie}).json()
        r2 = c.post("/api/v1/web/ia/clasificar", json={"muestras": auto}).json()
        assert c.post("/api/v1/web/ia/clasificar", json={"muestras": []}).status_code == 422
    assert r1["modo"] == "a_pie" and r1["fuente"] == "rf" and r1["muestras"] == 30
    assert r2["modo"] == "vehiculo"
