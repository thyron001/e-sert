"""Tests 2 y 3: el WebSocket `/ws/estado` y `GET /api/v1/puestos` del servidor de prueba."""
from comun.esquemas import MensajeKpi, MensajeSnapshot, Puesto, leer_mensaje_ws

N_PUESTOS = 610


def recibir(cliente, n):
    """Abre `/ws/estado` y devuelve los primeros `n` mensajes como texto."""
    with cliente.websocket_connect("/ws/estado") as ws:
        return [ws.receive_text() for _ in range(n)]


def test_ws_mensajes_cumplen_contrato(cliente):
    textos = recibir(cliente, 5)
    assert len(textos) == 5
    for texto in textos:
        msj = leer_mensaje_ws(texto)
        assert isinstance(msj, (MensajeSnapshot, MensajeKpi)), type(msj)


def test_ws_envia_kpi_entre_snapshots(cliente):
    """El reproductor intercala mensajes `kpi` (cada 5 s reales en vivo; aquí cada 10 ms)."""
    mensajes = [leer_mensaje_ws(t) for t in recibir(cliente, 60)]
    kpis = [m for m in mensajes if isinstance(m, MensajeKpi)]
    assert kpis, "no llegó ningún mensaje kpi en 60 mensajes"
    assert isinstance(kpis[0].valores["busqueda_media_s"], float)
    assert any(isinstance(m, MensajeSnapshot) for m in mensajes)


def test_api_puestos(cliente):
    r = cliente.get("/api/v1/puestos")
    assert r.status_code == 200
    datos = r.json()
    assert len(datos) == N_PUESTOS
    ids = set()
    for d in datos:
        p = Puesto.model_validate(d)
        assert p.ocupados <= p.capacidad, p.puesto_id
        ids.add(p.puesto_id)
    assert len(ids) == N_PUESTOS, "hay puesto_id repetidos"


def test_espejos_mock_y_candidatos(cliente):
    """El servidor rellena `espejos` (MOCK) y los candidatos son autos con app que buscan."""
    with cliente.websocket_connect("/ws/estado") as ws:
        snaps = [m for m in (leer_mensaje_ws(ws.receive_text()) for _ in range(6)) if isinstance(m, MensajeSnapshot)]
    assert snaps and all(1 <= len(s.espejos) <= 2 for s in snaps)
    con_app = {v.id for v in snaps[-1].vehiculos if v.con_app}
    assert set(snaps[-1].espejos) <= con_app
    cand = cliente.get("/api/v1/espejo/candidatos").json()
    assert all({"id", "destino_nombre", "estado", "t_sim"} <= set(c) for c in cand)


def test_ws_espejo_campos_6b(cliente):
    """`/ws/espejo/{veh}` manda `espejo` con los campos del contrato §7 (MOCK) y `no_existe` si no está."""
    with cliente.websocket_connect("/ws/estado") as ws:
        snap = leer_mensaje_ws(ws.receive_text())
    veh = snap.espejos[0]
    with cliente.websocket_connect(f"/ws/espejo/{veh}") as ws:
        m = ws.receive_json()
    assert m["tipo"] == "espejo" and m["veh_id"] == veh
    for campo in ("t_sim", "ts", "estado", "lat", "lon", "modo", "destino", "puesto", "ruta", "sesion",
                  "billetera", "avisos", "recibo"):
        assert campo in m
    assert {"puesto_id", "lat", "lon", "distancia_m"} <= set(m["puesto"])
    with cliente.websocket_connect("/ws/espejo/sim_no_existe") as ws:
        fin = ws.receive_json()
    assert fin["tipo"] == "espejo_fin" and fin["motivo"] == "no_existe"


def test_kpi_cada_5s_trae_valores(cliente):
    from visor.servidor_prueba import KPI_CADA_S

    assert KPI_CADA_S == 5.0
    with cliente.websocket_connect("/ws/estado") as ws:
        msgs = [leer_mensaje_ws(ws.receive_text()) for _ in range(60)]
    kpis = [m for m in msgs if isinstance(m, MensajeKpi)]
    assert kpis and "busqueda_media_s" in kpis[0].valores
