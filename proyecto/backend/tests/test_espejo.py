"""Modo espejo (S3-3, contrato §7, v1.2): candidatos, `/ws/espejo/{veh_id}`, `espejos` y recibo.

Los snapshots son sintéticos (el cuerpo de `POST /interno/snapshot` con el bloque interno
`espejo`), así que no hace falta SUMO. Cada lectura del WS termina en un mensaje esperado
(`espejo_fin` o un número fijo de mensajes): nada queda colgado.
"""

from __future__ import annotations

import json
import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.api.main import Config, crear_app
from backend.espejo.ws_espejo import CIERRE_NO_EXISTE
from comun import esquemas as e

TOKEN = "secreto"
CAB = {"X-Sim-Token": TOKEN}
SNAP = "/api/v1/interno/snapshot"
SES = f"ses_{uuid.UUID(int=42)}"


def vehiculo(veh: str, estado="GUIADO") -> dict:
    return {"id": veh, "lat": -2.8973, "lon": -79.0045, "estado": estado, "con_app": True}


def detalle(t: float, estado="GUIADO", recibo=None, distancia=180.0) -> dict:
    return {
        "t_sim": t, "estado": estado, "lat": -2.8973, "lon": -79.0045, "modo": "vehiculo", "confianza": 0.9,
        "destino": {"nombre": "Parque Calderón", "lat": -2.897308, "lon": -79.004488},
        "puesto": {"puesto_id": "pa_-106945247#0_0", "lat": -2.8898, "lon": -78.9956, "distancia_m": distancia},
        "ruta": [[-2.8973, -79.0045], [-2.8975, -79.005]],
        "sesion": None, "billetera": {"saldo": 4.85, "disponible": 4.60}, "avisos": ["saldo_bajo"],
        "recibo": recibo,
    }


RECIBO = {"sesion_id": SES, "minutos_reales": 42.3, "minutos_cobrados": 45, "cobrado_usd": 0.38,
          "tarjeta_sert_usd": 0.5, "ahorro_usd": 0.12}


def cuerpo(t: float, vehs=("sim_veh42", "sim_veh7", "sim_veh9"), detalles=None, fin=False) -> dict:
    """Snapshot con el bloque interno `espejo`: todos los autos son candidatos."""
    return {
        "t_sim": t, "ts": "2026-11-05T15:04:05.120Z",
        "vehiculos": [vehiculo(v) for v in vehs], "peatones": [],
        "verdad": {"puestos": [], "estacionados": [], "falsas_liberaciones": []},
        "espejo": {"candidatos": [{"id": v, "destino_nombre": "Parque Calderón", "estado": "GUIADO", "t_sim": t}
                                  for v in vehs],
                   "detalle": detalles or {}, "fin": fin},
    }


def esperar(cond, timeout: float = 3.0) -> None:
    fin = time.monotonic() + timeout
    while not cond():
        assert time.monotonic() < fin, "tiempo agotado esperando la condición"
        time.sleep(0.01)


def leer(ws) -> e.Modelo:
    return e.leer_mensaje_ws(ws.receive_text())


@pytest.fixture
def app():
    return crear_app(Config(db_url="sqlite:///:memory:", token_sim=TOKEN))


@pytest.fixture
def c(app):
    with TestClient(app) as cliente:
        yield cliente


def registro(app):
    return app.state.servicios.espejo


# ---------------------------------------------------------------------------- candidatos


def test_candidatos_del_bloque_espejo(c):
    assert c.get("/api/v1/espejo/candidatos").json() == []  # sin simulación
    assert c.post(SNAP, json=cuerpo(10.0), headers=CAB).status_code == 202
    r = c.get("/api/v1/espejo/candidatos")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    lista = [e.CandidatoEspejo.model_validate(x) for x in r.json()]
    assert [x.id for x in lista] == ["sim_veh42", "sim_veh7", "sim_veh9"]
    assert all(x.destino_nombre == "Parque Calderón" and x.t_sim == 10.0 for x in lista)


def test_candidato_que_salio_no_se_ofrece(c):
    c.post(SNAP, json=cuerpo(10.0), headers=CAB)
    sin_9 = cuerpo(11.0, vehs=("sim_veh42", "sim_veh7"))
    sin_9["espejo"]["candidatos"].append({"id": "sim_veh9", "destino_nombre": "x", "estado": "GUIADO", "t_sim": 11.0})
    c.post(SNAP, json=sin_9, headers=CAB)
    assert [x["id"] for x in c.get("/api/v1/espejo/candidatos").json()] == ["sim_veh42", "sim_veh7"]


# ---------------------------------------------------------------------------- token y bloque interno


def test_snapshot_sin_token_401(c, app):
    r = c.post(SNAP, json=cuerpo(10.0))
    assert r.status_code == 401 and r.json()["error"]["codigo"] == "TOKEN_SIM_INVALIDO"
    assert registro(app).snapshots == 0  # el bloque rechazado no se registra
    assert c.get("/api/v1/espejo/candidatos").json() == []


def test_ws_estado_nunca_lleva_el_bloque_interno(c):
    with c.websocket_connect("/ws/estado?rol=visor") as visor:
        c.post(SNAP, json=cuerpo(10.0, detalles={"sim_veh42": detalle(10.0, recibo=RECIBO)}), headers=CAB)
        textos = [visor.receive_text(), visor.receive_text()]  # snapshot y verdad
    for texto in textos:
        datos = json.loads(texto)
        assert datos["tipo"] in ("snapshot", "verdad")
        assert "espejo" not in datos and "detalle" not in texto and "candidatos" not in texto
        assert "recibo" not in texto and SES not in texto
    snap = e.leer_mensaje_ws(textos[0])
    assert set(json.loads(textos[0])) == set(e.MensajeSnapshot.model_fields)


# ---------------------------------------------------------------------------- WS por vehículo


def test_no_existe_cierra_4404(c):
    with c.websocket_connect("/ws/espejo/sim_fantasma") as ws:
        fin = leer(ws)
        assert isinstance(fin, e.MensajeEspejoFin) and fin.motivo is e.MotivoFinEspejo.no_existe
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
    assert exc.value.code == CIERRE_NO_EXISTE


def test_solo_su_vehiculo_a_1hz_con_10_snapshots_por_segundo(c, app):
    c.post(SNAP, json=cuerpo(0.0), headers=CAB)
    mensajes, horas = [], []
    detener = threading.Event()

    def controlador():
        """10 snapshots por segundo real, con detalle de los tres autos (como si los siguieran a todos)."""
        t = 1.0
        while not detener.is_set():
            det = {v: detalle(t, distancia=500 - t) for v in ("sim_veh42", "sim_veh7", "sim_veh9")}
            c.post(SNAP, json=cuerpo(t, detalles=det), headers=CAB)
            t += 1.0
            time.sleep(0.1)
        # el auto seguido sale de la simulación
        c.post(SNAP, json=cuerpo(t, vehs=("sim_veh7", "sim_veh9")), headers=CAB)

    with c.websocket_connect("/ws/espejo/sim_veh42") as ws:
        hilo = threading.Thread(target=controlador)
        hilo.start()
        inicio = time.monotonic()
        while True:
            m = leer(ws)
            horas.append(time.monotonic())
            mensajes.append(m)
            if isinstance(m, e.MensajeEspejoFin):
                break
            if time.monotonic() - inicio > 4.0:
                detener.set()
        hilo.join()
    espejos = [m for m in mensajes if isinstance(m, e.MensajeEspejo)]
    assert {m.veh_id for m in mensajes} == {"sim_veh42"}
    assert mensajes[-1].motivo is e.MotivoFinEspejo.salio_simulacion
    assert len(espejos) >= 4
    # ≤ 1 Hz: entre dos mensajes espejo pasa al menos ~1 s (con 10 snapshots por segundo)
    pausas = [b - a for a, b in zip(horas, horas[1:len(espejos)])]
    # Las horas son de recepción en el cliente: si el sistema está cargado, un mensaje que llega tarde
    # alarga una pausa y acorta la siguiente aunque el servidor respete 1 Hz (falló así 1 de ~20 veces
    # en S4-3). Se exige el ritmo con tolerancia a ese corrimiento: cada pausa ≥ 0,5 s y cada par de
    # pausas seguidas ≥ 1,9 s (dos mensajes por segundo no pasarían).
    assert min(pausas) >= 0.5, pausas
    assert all(a + b >= 1.9 for a, b in zip(pausas, pausas[1:])), pausas
    assert len(espejos) <= (horas[len(espejos) - 1] - horas[0]) + 1.5
    # y cada mensaje trae el dato más nuevo, no uno viejo encolado
    assert all(b.t_sim - a.t_sim >= 5 for a, b in zip(espejos[1:], espejos[2:]))


def test_espejos_en_el_snapshot_mientras_hay_suscriptor(c, app):
    c.post(SNAP, json=cuerpo(10.0), headers=CAB)
    with c.websocket_connect("/ws/estado?rol=publico") as visor:
        with c.websocket_connect("/ws/espejo/sim_veh42") as ws:
            primero = leer(ws)  # al conectar llega el último estado conocido (del snapshot)
            assert isinstance(primero, e.MensajeEspejo) and primero.veh_id == "sim_veh42"
            r = c.post(SNAP, json=cuerpo(11.0), headers=CAB)
            assert r.json() == {"aceptado": True, "espejos": ["sim_veh42"], "ordenes": []}  # el controlador sabe a quién detallar
            snap = leer(visor)
            assert isinstance(snap, e.MensajeSnapshot) and snap.espejos == ["sim_veh42"]
        esperar(lambda: registro(app).espejos() == [])
        c.post(SNAP, json=cuerpo(12.0), headers=CAB)
        snap = leer(visor)
        assert snap.espejos == []


def test_varias_pantallas_mismo_vehiculo(c, app):
    c.post(SNAP, json=cuerpo(10.0), headers=CAB)
    with c.websocket_connect("/ws/espejo/sim_veh42") as a:
        leer(a)
        with c.websocket_connect("/ws/espejo/sim_veh42") as b:
            leer(b)
            assert registro(app).suscriptores["sim_veh42"] == 2
        esperar(lambda: registro(app).suscriptores["sim_veh42"] == 1)
    esperar(lambda: "sim_veh42" not in registro(app).suscriptores)


def test_mensaje_con_los_campos_exactos_de_6b(c):
    c.post(SNAP, json=cuerpo(10.0, detalles={"sim_veh42": detalle(10.0)}), headers=CAB)
    with c.websocket_connect("/ws/espejo/sim_veh42") as ws:
        texto = ws.receive_text()
    datos = json.loads(texto)
    assert set(datos) == {"tipo", "veh_id", "t_sim", "ts", "estado", "lat", "lon", "modo", "destino",
                          "puesto", "ruta", "sesion", "billetera", "avisos", "recibo"}
    assert datos["ts"].endswith("Z") and "confianza" not in datos  # la confianza es interna
    m = e.MensajeEspejo.model_validate(datos)
    assert m.puesto.distancia_m == 180.0 and m.avisos == [e.Aviso.saldo_bajo]


# ---------------------------------------------------------------------------- recibo y fin


def test_recibo_una_vez_aunque_se_repita_el_snapshot(c, app):
    c.post(SNAP, json=cuerpo(10.0, detalles={"sim_veh42": detalle(10.0, estado="SALIENDO")}), headers=CAB)
    with c.websocket_connect("/ws/espejo/sim_veh42") as ws:
        assert leer(ws).recibo is None
        for k in range(4):  # el mismo recibo en 4 snapshots seguidos
            t = 11.0 + k
            c.post(SNAP, json=cuerpo(t, detalles={"sim_veh42": detalle(t, estado="CERRADA", recibo=RECIBO)}),
                   headers=CAB)
        recibidos = [leer(ws) for _ in range(3)]
        # reconexión dentro de los 60 s: la pantalla nueva vuelve a recibirlo, una vez
        with c.websocket_connect("/ws/espejo/sim_veh42") as otra:
            assert leer(otra).recibo == e.Recibo(**{k: v for k, v in RECIBO.items() if k != "sesion_id"})
        c.post(SNAP, json=cuerpo(20.0, vehs=("sim_veh7",)), headers=CAB)  # el auto sale de SUMO
        resto = []
        while not resto or not isinstance(resto[-1], e.MensajeEspejoFin):
            resto.append(leer(ws))
    con_recibo = [m for m in recibidos + resto if isinstance(m, e.MensajeEspejo) and m.recibo is not None]
    assert len(con_recibo) == 1
    assert con_recibo[0].estado is e.EstadoSesion.CERRADA and con_recibo[0].recibo.ahorro_usd == 0.12
    assert resto[-1].motivo is e.MotivoFinEspejo.salio_simulacion
    assert registro(app).recibos_recibidos == 1


def test_fin_de_la_corrida(c):
    c.post(SNAP, json=cuerpo(10.0), headers=CAB)
    with c.websocket_connect("/ws/espejo/sim_veh42") as ws:
        leer(ws)
        c.post(SNAP, json=cuerpo(10.5, fin=True), headers=CAB)
        m = leer(ws)
        while isinstance(m, e.MensajeEspejo):
            m = leer(ws)
        assert m.motivo is e.MotivoFinEspejo.fin_simulacion
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
    assert exc.value.code == 1000
    assert c.get("/api/v1/espejo/candidatos").json() == []  # terminada la corrida, no hay a quién seguir


def test_latido_sin_snapshots_nuevos(c):
    """Sin datos nuevos el WS reenvía el último estado (la app reconecta tras 5 s de silencio)."""
    c.post(SNAP, json=cuerpo(10.0), headers=CAB)
    with c.websocket_connect("/ws/espejo/sim_veh42") as ws:
        t0 = time.monotonic()
        leer(ws)
        m = leer(ws)
        assert isinstance(m, e.MensajeEspejo) and m.t_sim == 10.0
        assert 1.5 <= time.monotonic() - t0 <= 3.5


# ---------------------------------------------------------------------------- RegistroEspejo (reloj falso, S3-3 vuelta 2)


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _paso(t: float, **kw) -> e.PasoSimulacion:
    return e.PasoSimulacion.model_validate(cuerpo(t, **kw))


def test_recibo_no_se_vuelve_a_registrar_despues_de_60_s():
    from backend.espejo.registro import RegistroEspejo

    reloj = Reloj()
    reg = RegistroEspejo(reloj=reloj)
    for k in range(5):  # el controlador repite el recibo mientras el auto sigue en la red
        reloj.t = 40.0 * k
        reg.aplicar(_paso(10.0 + k, detalles={"sim_veh42": detalle(10.0 + k, estado="CERRADA", recibo=RECIBO)}))
    assert reg.recibos_recibidos == 1
    assert reg.recibo_pendiente("sim_veh42", set()) is None  # pasaron 160 s: ya no se reenvía


def test_controlador_caido_sin_fin_termina_por_inactividad():
    from backend.espejo.registro import RegistroEspejo

    reloj = Reloj()
    reg = RegistroEspejo(reloj=reloj, inactividad_s=30)
    reg.aplicar(_paso(10.0))
    reloj.t = 20.0
    assert reg.fin("sim_veh42") is None
    reloj.t = 31.0
    assert reg.fin("sim_veh42") is e.MotivoFinEspejo.fin_simulacion


def test_sumo_relanzado_termina_las_pantallas_de_la_corrida_anterior():
    from backend.espejo.registro import RegistroEspejo

    reg = RegistroEspejo(reloj=Reloj())
    reg.aplicar(_paso(500.0))
    corrida = reg.corrida
    assert reg.fin("sim_veh42", corrida) is None
    reg.aplicar(_paso(1.0))  # t_sim vuelve atrás: corrida nueva con los mismos IDs
    assert reg.fin("sim_veh42", corrida) is e.MotivoFinEspejo.fin_simulacion
    assert reg.fin("sim_veh42", reg.corrida) is None
