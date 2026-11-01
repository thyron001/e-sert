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


def test_ws_envia_kpi_cada_30_snapshots(cliente):
    # 30 snapshots + 1 kpi: con la muestra corta el servidor la repite en bucle.
    mensajes = [leer_mensaje_ws(t) for t in recibir(cliente, 31)]
    kpis = [m for m in mensajes if isinstance(m, MensajeKpi)]
    assert kpis, "no llegó ningún mensaje kpi en 31 mensajes"
    valores = kpis[0].valores
    assert "busqueda_media_s" in valores
    assert isinstance(valores["busqueda_media_s"], float)
    # El kpi llega justo después del snapshot 30.
    assert isinstance(mensajes[30], MensajeKpi)
    assert all(isinstance(m, MensajeSnapshot) for m in mensajes[:30])


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
