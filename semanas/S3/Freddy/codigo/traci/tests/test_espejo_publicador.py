"""Modo espejo (S3-3): bloque interno `espejo`, ruta en lat/lon y publicación de snapshots.

Los casos unitarios usan un `traci` falso (como `test_robustez.py`) con el núcleo real
(`PuenteNucleo`); el marcado `sumo` carga la red real de Tyrone y necesita el contenedor `van3twin`.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from comun.esquemas import BloqueEspejo, DetalleEspejo, MotivoCierre, PasoSimulacion, ReciboEspejo
from traci.correr_guiado import PublicadorSnapshots, Ritmo, _ahora_iso
from traci.espejo_publicador import EspejoPublicador, estado_vehiculo, recibo_de
from traci.gps import conversor_plano
from traci.puente_nucleo import Publicador, PuenteNucleo
from traci.ruta_geo import RutaGeo, douglas_peucker, simplificar

EN_CONTENEDOR = Path("/home/vanet/results").is_dir() and bool(os.environ.get("SUMO_HOME"))
VAR_POSITION = 0x42
PUESTO = "pa_x_0"
CONVERSOR = conversor_plano()
RED = Path(__file__).resolve().parents[1] / "escenario" / "tyrone" / "sumo" / "red" / "centro.net.xml"
INVALID_DOUBLE = -1073741824.0  # lo que devuelve getDrivingDistance si no hay camino


# ---------------------------------------------------------------------------- Douglas-Peucker (puro)


def test_linea_recta_queda_en_dos_puntos():
    recta = [(float(i), 2.0 * i) for i in range(1000)]
    salida = simplificar(recta)
    assert salida == [recta[0], recta[-1]]
    assert douglas_peucker(recta, 0.5) == [recta[0], recta[-1]]


def test_zigzag_respeta_max_puntos_y_extremos():
    # onda triangular de 5000 puntos (201 vértices): obliga a subir la tolerancia. Un zigzag que
    # alterna punto a punto es el peor caso de Douglas-Peucker (O(n²) por pasada, ~36 s aquí).
    zigzag = [(float(i), float(abs((i % 50) - 25))) for i in range(5000)]
    salida = simplificar(zigzag, max_puntos=200)
    assert 2 <= len(salida) <= 200
    assert salida[0] == zigzag[0] and salida[-1] == zigzag[-1]


def test_simplificar_quita_repetidos():
    puntos = [(0.0, 0.0), (0.0, 0.0), (5.0, 5.0), (5.0, 5.0), (5.0, 5.0), (10.0, 0.0)]
    assert simplificar(puntos, tolerancia=0.1) == [(0.0, 0.0), (5.0, 5.0), (10.0, 0.0)]
    assert douglas_peucker([(1.0, 1.0)], 1.0) == [(1.0, 1.0)]


# ---------------------------------------------------------------------------- RutaGeo con red falsa


class RedFalsa:
    """Imita lo que `RutaGeo` usa de `sumolib.net.Net`: hasEdge, getEdge().getShape() y convertXY2LonLat."""

    def __init__(self, formas: dict):
        self.formas = formas

    def hasEdge(self, e):
        return e in self.formas

    def getEdge(self, e):
        return SimpleNamespace(getShape=lambda: list(self.formas[e]))

    def convertXY2LonLat(self, x, y):
        lat, lon = CONVERSOR(x, y)
        return lon, lat


def _red_en_l() -> RedFalsa:
    """Tres aristas: a (0,0)→(100,0), b (100,0)→(100,100), c (100,100)→(200,100) y una interna."""
    return RedFalsa({
        "a": [(0.0, 0.0), (100.0, 0.0)],
        "b": [(100.0, 0.0), (100.0, 100.0)],
        "c": [(100.0, 100.0), (200.0, 100.0)],
        ":j_0": [(500.0, 500.0), (600.0, 600.0)],  # nunca debe aparecer
    })


def _latlon(x, y):
    lat, lon = CONVERSOR(x, y)
    return [round(lat, 7), round(lon, 7)]


def test_ruta_geo_salta_internas_corta_y_formato_lat_lon():
    rg = RutaGeo(_red_en_l())
    ruta = rg.desde_aristas(["a", ":j_0", "b", "c"])
    assert ruta == [_latlon(0, 0), _latlon(100, 0), _latlon(100, 100), _latlon(200, 100)]
    assert all(-3 < lat < -2.8 and -79.1 < lon < -78.9 for lat, lon in ruta)  # [lat, lon], no [lon, lat]
    # cortada en la arista del puesto: el camino al puesto, no la salida posterior
    assert rg.desde_aristas(["a", ":j_0", "b", "c"], hasta_edge="b") == \
        [_latlon(0, 0), _latlon(100, 0), _latlon(100, 100)]
    # desde el índice actual de la ruta
    assert rg.desde_aristas(["a", ":j_0", "b", "c"], indice=2) == \
        [_latlon(100, 0), _latlon(100, 100), _latlon(200, 100)]
    # aristas desconocidas se ignoran
    assert rg.desde_aristas(["zz"]) == []


def test_ruta_geo_cache():
    rg = RutaGeo(_red_en_l())
    primera = rg.desde_aristas(["a", "b"], 0, "b")
    assert (rg.calculadas, rg.aciertos) == (1, 0)
    segunda = rg.desde_aristas(["a", "b"], 0, "b")
    assert (rg.calculadas, rg.aciertos) == (1, 1)
    assert segunda == primera
    rg.desde_aristas(["a", "b"], 1, "b")  # otro índice: se recalcula
    assert (rg.calculadas, rg.aciertos) == (2, 1)


def test_ruta_geo_cache_acotada():
    rg = RutaGeo(_red_en_l(), tam_cache=2)
    for i in range(3):
        rg.desde_aristas(["a", "b", "c"], i)
    rg.desde_aristas(["a", "b", "c"], 0)  # se expulsó la más vieja
    assert (rg.calculadas, rg.aciertos) == (4, 0)


# ---------------------------------------------------------------------------- EspejoPublicador con traci falso


class MundoEspejo:
    """Cinco autos con el núcleo real y un `traci` falso:

    - v1 BUSCANDO (A_CIEGAS en la guía), v42 GUIADO al puesto, v3 BUSCANDO: con app;
    - v4 ESTACIONADO (máquina de sesión), con app;
    - v5 BUSCANDO pero sin app.
    """

    def __init__(self, tmp_path: Path):
        csv = tmp_path / "puestos.csv"
        lat_p, lon_p = CONVERSOR(300.0, 0.0)
        csv.write_text("puesto_id,edge,lane,calle,capacidad,lat,lon,x,y\n"
                       f"{PUESTO},x,x_0,Calle X,5,{lat_p},{lon_p},300,0\n", encoding="utf-8")
        self.puente = PuenteNucleo(csv, semilla=1, recarga_usd=(20.0, 20.0))
        self.distancia = 123.4
        self.posiciones = {v: (10.0 * k, 0.0) for k, v in enumerate(["v1", "v42", "v3", "v4", "v5"])}
        self.destinos_param = {"v1": "Catedral", "v42": "Parque CalderÃ³n", "v3": "Mercado",
                               "v4": "Catedral", "v5": "Mercado"}  # v42 como lo manda TraCI (latin-1)
        tr = SimpleNamespace(
            constants=SimpleNamespace(VAR_POSITION=VAR_POSITION),
            vehicle=SimpleNamespace(
                getParameter=lambda veh, k: {"destino": self.destinos_param[veh]}.get(k, ""),  # SUMO da "" si falta
                getDrivingDistance=lambda veh, edge, pos: self.distancia,
                getRoute=lambda veh: ["a", ":j_0", "b", "x", "c"],
                getRouteIndex=lambda veh: 0),
            person=SimpleNamespace(getStage=lambda ped: SimpleNamespace(description="caminando")),
            parkingarea=SimpleNamespace(getLaneID=lambda pid: "x_0", getStartPos=lambda pid: 5.0),
            lane=SimpleNamespace(getEdgeID=lambda lane: lane.rsplit("_", 1)[0]),
        )
        self.ctrl = SimpleNamespace(traci=tr, personas={},
                                    vehiculos={v: {VAR_POSITION: p} for v, p in self.posiciones.items()})
        self.guia = SimpleNamespace(estado={"v1": "A_CIEGAS", "v42": "GUIADO", "v3": "BUSCANDO", "v5": "BUSCANDO"},
                                    puesto={"v42": PUESTO})
        self.sesiones = SimpleNamespace(maquinas={"v4": SimpleNamespace(estado="ESTACIONADO")}, puesto_de={},
                                        sesion_de={}, t_inicio={}, puesto_ll={}, ultimo_modo={})
        self.registro = SimpleNamespace(con_app={"v1": True, "v42": True, "v3": True, "v4": True, "v5": False})
        destinos = {"Parque Calderón": (-2.8970, -79.0040, 1.0), "Catedral": (-2.8975, -79.0050, 1.0)}
        self.red = RedFalsa({"a": [(0.0, 0.0), (100.0, 0.0)], "b": [(100.0, 0.0), (100.0, 100.0)],
                             "x": [(100.0, 100.0), (300.0, 0.0)], "c": [(300.0, 0.0), (400.0, 0.0)]})
        self.espejo = EspejoPublicador(self.sesiones, self.guia, self.puente, self.registro, destinos,
                                       CONVERSOR, ruta_geo=RutaGeo(self.red))


def test_candidatos_solo_con_app_y_buscando_o_guiado(tmp_path):
    m = MundoEspejo(tmp_path)
    bloque = m.espejo.bloque(m.ctrl, 12.34)
    BloqueEspejo.model_validate(bloque)
    por_id = {c["id"]: c for c in bloque["candidatos"]}
    assert set(por_id) == {"sim_v1", "sim_v42", "sim_v3"}
    assert por_id["sim_v1"]["estado"] == "BUSCANDO"  # A_CIEGAS se muestra como BUSCANDO
    assert por_id["sim_v42"] == {"id": "sim_v42", "destino_nombre": "Parque Calderón",
                                 "estado": "GUIADO", "t_sim": 12.3}
    assert por_id["sim_v3"]["destino_nombre"] == "Mercado"
    assert bloque["detalle"] == {}


def test_detalle_solo_de_los_seguidos_y_en_la_red(tmp_path):
    m = MundoEspejo(tmp_path)
    bloque = m.espejo.bloque(m.ctrl, 10.0, {"sim_v42", "sim_v99"})
    assert set(bloque["detalle"]) == {"sim_v42"}
    del m.ctrl.vehiculos["v42"]
    assert m.espejo.bloque(m.ctrl, 11.0, {"sim_v42"})["detalle"] == {}
    assert m.espejo.detalles_armados == 1


def test_detalle_guiado_valida_y_distancia_por_la_red(tmp_path):
    m = MundoEspejo(tmp_path)
    bloque = m.espejo.bloque(m.ctrl, 10.0, ["sim_v42"])
    BloqueEspejo.model_validate(bloque)
    det = bloque["detalle"]["sim_v42"]
    DetalleEspejo.model_validate(det)
    assert det["estado"] == "GUIADO"
    assert [det["lat"], det["lon"]] == _latlon(*m.posiciones["v42"])
    assert det["destino"]["nombre"] == "Parque Calderón"
    assert det["puesto"]["puesto_id"] == PUESTO and det["puesto"]["distancia_m"] == 123.4
    # la ruta llega hasta la arista del puesto ("x"), sin la interna ni la salida "c"
    assert det["ruta"][0] == _latlon(0, 0) and det["ruta"][-1] == _latlon(300, 0)
    assert _latlon(400, 0) not in det["ruta"]
    assert det["sesion"] is None and det["recibo"] is None and det["modo"] is None


def test_distancia_invalida_cae_a_linea_recta(tmp_path):
    m = MundoEspejo(tmp_path)
    m.distancia = INVALID_DOUBLE
    det = m.espejo.bloque(m.ctrl, 10.0, ["sim_v42"])["detalle"]["sim_v42"]
    DetalleEspejo.model_validate(det)
    d = det["puesto"]["distancia_m"]
    assert math.isfinite(d) and d >= 0
    assert d == pytest.approx(290.0, abs=2.0)  # del auto en x=10 al puesto en x=300


def test_telefono_va_con_el_peaton(tmp_path):
    m = MundoEspejo(tmp_path)
    m.ctrl.personas = {"ped_v42": {VAR_POSITION: (50.0, 50.0)}}
    det = m.espejo.bloque(m.ctrl, 10.0, ["sim_v42"])["detalle"]["sim_v42"]
    assert [det["lat"], det["lon"]] == _latlon(50.0, 50.0)


def test_sesion_en_curso_y_recibo_al_cerrar(tmp_path):
    m = MundoEspejo(tmp_path)
    usuario = "sim_v42"
    m.puente.registrar(usuario)
    sid = m.puente.iniciar(usuario, PUESTO, 100.0)
    assert sid is not None
    m.sesiones.maquinas["v42"] = SimpleNamespace(estado="ESTACIONADO")
    m.sesiones.sesion_de["v42"] = sid
    m.sesiones.t_inicio["v42"] = 100.0
    m.sesiones.ultimo_modo[usuario] = {"modo": "quieto", "confianza": 0.91234}

    t = 100.0 + 20 * 60  # 20 minutos después
    det = m.espejo.bloque(m.ctrl, t, ["sim_v42"])["detalle"]["sim_v42"]
    DetalleEspejo.model_validate(det)
    assert det["estado"] == "ESTACIONADO" and det["modo"] == "quieto" and det["confianza"] == 0.912
    assert det["ruta"] == []  # estacionado: sin ruta
    assert det["sesion"]["sesion_id"] == sid and det["sesion"]["minutos"] == 20.0
    assert det["sesion"]["costo_usd"] > 0
    assert det["sesion"]["costo_usd"] == pytest.approx(20 / 60 * 0.50, abs=0.005)
    assert det["sesion"]["retenido_usd"] == 0.25  # bloque mínimo de 30 min a 0,50 USD/h
    assert det["billetera"] == {"saldo": 20.0, "disponible": 19.75}

    fila = m.puente.cerrar(sid, t, MotivoCierre.manual)  # dispara `al_cerrar` → recibo
    recibo = m.espejo.recibos["v42"]
    assert recibo == recibo_de(fila)
    del m.sesiones.maquinas["v42"]
    del m.sesiones.sesion_de["v42"]
    del m.sesiones.t_inicio["v42"]
    assert estado_vehiculo("v42", m.sesiones, m.guia, m.espejo.recibos) == "CERRADA"
    assert m.espejo.estado("v42") == "CERRADA"

    bloque = m.espejo.bloque(m.ctrl, t + 5, ["sim_v42"])
    BloqueEspejo.model_validate(bloque)
    assert "sim_v42" not in {c["id"] for c in bloque["candidatos"]}
    det = bloque["detalle"]["sim_v42"]
    assert det["estado"] == "CERRADA" and det["sesion"] is None
    rec = det["recibo"]
    ReciboEspejo.model_validate(rec)
    assert rec["sesion_id"] == sid
    assert rec["minutos_cobrados"] == 20
    assert rec["cobrado_usd"] == pytest.approx(0.17, abs=0.01)
    assert rec["tarjeta_sert_usd"] == 0.25
    assert rec["ahorro_usd"] == round(rec["tarjeta_sert_usd"] - rec["cobrado_usd"], 2)
    assert det["billetera"]["disponible"] == det["billetera"]["saldo"]  # retención liberada


def test_recibo_solo_de_usuarios_simulados(tmp_path):
    m = MundoEspejo(tmp_path)
    m.espejo._al_cerrar({"usuario_id": "app_0", "sesion_id": "x", "minutos_reales": 1,
                         "minutos_cobrados": 10, "debitado": 0.1})
    assert m.espejo.recibos == {}


# ---------------------------------------------------------------------------- PublicadorSnapshots


class PublicadorFalso:
    def __init__(self):
        self.cuerpos = []
        self.al_responder = None

    def publicar(self, cuerpo):
        self.cuerpos.append(cuerpo)


def _snapshots(m: MundoEspejo, pub: PublicadorFalso) -> PublicadorSnapshots:
    return PublicadorSnapshots(pub, m.sesiones, m.guia, m.registro, SimpleNamespace(activos={}), m.red,
                               espejo=m.espejo)


def test_publicador_snapshots_con_espejo(tmp_path):
    m = MundoEspejo(tmp_path)
    pub = PublicadorFalso()
    snap = _snapshots(m, pub)
    assert pub.al_responder == snap._al_responder

    for t in (5.0, 5.2, 5.9):  # como mucho una publicación por segundo simulado
        snap.on_paso(m.ctrl, t)
    assert len(pub.cuerpos) == 1
    cuerpo = pub.cuerpos[0]
    PasoSimulacion.model_validate(cuerpo)
    assert re.search(r"T\d{2}:\d{2}:\d{2}\.\d{3}Z$", cuerpo["ts"])
    assert {c["id"] for c in cuerpo["espejo"]["candidatos"]} == {"sim_v1", "sim_v42", "sim_v3"}
    assert cuerpo["espejo"]["detalle"] == {}
    assert {v["id"] for v in cuerpo["vehiculos"]} == {"sim_v1", "sim_v42", "sim_v3", "sim_v4"}

    pub.al_responder({"aceptado": True, "espejos": ["sim_v42"]})  # lo que respondió el backend
    snap.on_paso(m.ctrl, 6.0)
    assert len(pub.cuerpos) == 2
    cuerpo = pub.cuerpos[1]
    PasoSimulacion.model_validate(cuerpo)
    assert set(cuerpo["espejo"]["detalle"]) == {"sim_v42"}

    snap.fin_corrida()
    fin = pub.cuerpos[-1]
    PasoSimulacion.model_validate(fin)
    assert fin["espejo"]["fin"] is True and fin["t_sim"] == 6.0
    assert len(pub.cuerpos) == 3


def test_publicador_snapshots_sin_espejo(tmp_path):
    m = MundoEspejo(tmp_path)
    pub = PublicadorFalso()
    snap = PublicadorSnapshots(pub, m.sesiones, m.guia, m.registro, SimpleNamespace(activos={}), m.red)
    assert pub.al_responder is None
    snap.on_paso(m.ctrl, 1.0)
    assert "espejo" not in pub.cuerpos[0]
    PasoSimulacion.model_validate(pub.cuerpos[0])
    snap.fin_corrida()  # sin espejo no hay último snapshot
    assert len(pub.cuerpos) == 1


def test_ahora_iso_con_milisegundos():
    ts = _ahora_iso()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", ts)


def test_ritmo_frena_la_simulacion():
    ritmo = Ritmo(factor=100.0)
    t0 = time.perf_counter()
    ritmo.on_paso(None, 0.0)
    ritmo.on_paso(None, 10.0)  # 10 s simulados a 100x = 0,1 s reales
    assert time.perf_counter() - t0 >= 0.09


# ---------------------------------------------------------------------------- Publicador HTTP real


class _Manejador(BaseHTTPRequestHandler):
    recibidos: list = []

    def do_POST(self):  # noqa: N802 (nombre de http.server)
        largo = int(self.headers.get("Content-Length", 0))
        _Manejador.recibidos.append((self.path, json.loads(self.rfile.read(largo))))
        cuerpo = json.dumps({"aceptado": True, "espejos": ["sim_v1"]}).encode()
        self.send_response(202 if self.path == "/api/v1/interno/snapshot" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *args):
        pass


def test_publicador_entrega_la_respuesta_al_callback():
    _Manejador.recibidos = []
    servidor = HTTPServer(("127.0.0.1", 0), _Manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    respuestas = []
    pub = Publicador(f"http://127.0.0.1:{servidor.server_address[1]}", al_responder=respuestas.append)
    try:
        pub.publicar({"t_sim": 1.0})
        limite = time.monotonic() + 3.0
        while not respuestas and time.monotonic() < limite:
            time.sleep(0.05)
        assert respuestas == [{"aceptado": True, "espejos": ["sim_v1"]}]
        assert _Manejador.recibidos == [("/api/v1/interno/snapshot", {"t_sim": 1.0})]
        assert pub.enviados == 1 and pub.fallidos == 0
    finally:
        pub.cerrar()
        servidor.shutdown()
        servidor.server_close()


# ---------------------------------------------------------------------------- red real (SUMO)


@pytest.mark.sumo
@pytest.mark.skipif(not EN_CONTENEDOR, reason="requiere el contenedor van3twin")
def test_ruta_geo_en_la_red_del_centro():
    if not RED.exists():
        pytest.skip(f"no existe {RED}")
    from traci.sumo import cargar_sumolib

    net = cargar_sumolib().net.readNet(str(RED))
    (xmin, ymin), (xmax, ymax) = net.getBBoxXY()
    esquinas = [net.convertXY2LonLat(x, y) for x in (xmin, xmax) for y in (ymin, ymax)]
    margen = 0.002
    lon_min, lon_max = min(e[0] for e in esquinas) - margen, max(e[0] for e in esquinas) + margen
    lat_min, lat_max = min(e[1] for e in esquinas) - margen, max(e[1] for e in esquinas) + margen
    # la caja de la red cae dentro del Centro Histórico (con holgura)
    assert -2.92 <= lat_min and lat_max <= -2.87 and -79.03 <= lon_min and lon_max <= -78.98

    aristas = [e for e in net.getEdges() if e.getFunction() != "internal" and e.allows("passenger")]
    aristas.sort(key=lambda e: e.getShape()[0][0] + e.getShape()[0][1])
    camino = None
    for a in aristas[:20]:  # una esquina contra la opuesta, hasta encontrar un camino
        for b in reversed(aristas[-20:]):
            edges, _costo = net.getShortestPath(a, b)
            if edges and len(edges) > 5:
                camino = edges
                break
        if camino:
            break
    assert camino, "no se encontró un camino entre esquinas opuestas de la red"

    rg = RutaGeo(net)
    ruta = rg.desde_aristas([e.getID() for e in camino])
    assert 2 <= len(ruta) <= 200
    for lat, lon in ruta:
        assert lat_min <= lat <= lat_max and lon_min <= lon <= lon_max
    assert rg.desde_aristas([e.getID() for e in camino]) is ruta and rg.aciertos == 1


# ---------------------------------------------------------------------------- hallazgos de la prueba en vivo (S3-3)


def _ctrl_con_parametros(params: dict) -> SimpleNamespace:
    return SimpleNamespace(traci=SimpleNamespace(vehicle=SimpleNamespace(
        getParameter=lambda veh, k: params.get(k, ""))))


def test_destino_de_acepta_los_tres_formatos():
    """Escenarios de Tyrone (S2): `destino="lat,lon"` + `destino_nombre`; demanda de S1: el nombre en `destino`."""
    from traci.guiado import destino_de

    destinos = {"Plaza de las Flores": (-2.8977, -79.0058, 1.0)}
    tyrone = _ctrl_con_parametros({"destino": "-2.897699,-79.005837", "destino_nombre": "Plaza de las Flores"})
    assert destino_de(tyrone, "v", destinos) == ("Plaza de las Flores", -2.8977, -79.0058)
    s1 = _ctrl_con_parametros({"destino": "Plaza de las Flores"})
    assert destino_de(s1, "v", destinos)[0] == "Plaza de las Flores"
    solo_coords = _ctrl_con_parametros({"destino": "-2.9,-79.0"})
    assert destino_de(solo_coords, "v", destinos) == ("-2.9,-79.0", -2.9, -79.0)
    assert destino_de(_ctrl_con_parametros({}), "v", destinos) is None


def test_posicion_no_finita_no_tumba_la_corrida(tmp_path):
    """SUMO a veces da una posición inválida con el auto recién estacionado: se salta ese detalle."""
    m = MundoEspejo(tmp_path)
    m.ctrl.vehiculos["v42"][VAR_POSITION] = (float("nan"), float("nan"))
    bloque = m.espejo.bloque(m.ctrl, 10.0, ["sim_v42"])
    assert bloque["detalle"] == {} and m.espejo.errores == {"posicion_no_finita": 1}
    m.ctrl.vehiculos["v42"][VAR_POSITION] = (10.0, 0.0)
    assert set(m.espejo.bloque(m.ctrl, 11.0, ["sim_v42"])["detalle"]) == {"sim_v42"}


def test_error_inesperado_en_un_detalle_se_cuenta_y_sigue(tmp_path):
    m = MundoEspejo(tmp_path)

    def falla(*a):
        raise ValueError("math domain error")

    m.ctrl.traci.vehicle.getDrivingDistance = falla
    bloque = m.espejo.bloque(m.ctrl, 10.0, ["sim_v42", "sim_v1"])
    assert "sim_v42" not in bloque["detalle"] and m.espejo.errores["ValueError"] == 1


def test_posicion_invalida_de_sumo_no_invalida_el_snapshot(tmp_path):
    """S3-3: un auto estacionado con posición -2^30 volvía `inf` su lat/lon y el backend rechazaba
    todos los snapshots (JSON inválido). Ahora se usa su última posición válida."""
    m = MundoEspejo(tmp_path)
    pub = PublicadorFalso()
    snap = _snapshots(m, pub)
    snap.on_paso(m.ctrl, 1.0)
    previa = next(v for v in pub.cuerpos[0]["vehiculos"] if v["id"] == "sim_v42")
    m.ctrl.vehiculos["v42"][VAR_POSITION] = (-1073741824.0, -1073741824.0)
    m.ctrl.vehiculos["v3"][VAR_POSITION] = (float("inf"), 0.0)
    snap.on_paso(m.ctrl, 2.0)
    cuerpo = pub.cuerpos[-1]
    json.dumps(cuerpo, allow_nan=False)  # JSON válido: sin inf ni NaN
    PasoSimulacion.model_validate(cuerpo)
    v42 = next(v for v in cuerpo["vehiculos"] if v["id"] == "sim_v42")
    assert (v42["lat"], v42["lon"]) == (previa["lat"], previa["lon"])  # sigue en la simulación
    assert snap.posiciones_invalidas == 2


def test_sin_puesto_tras_cerrar_y_recibo_viejo_no_viaja_con_sesion_nueva(tmp_path):
    m = MundoEspejo(tmp_path)
    m.espejo.recibos["v42"] = {"sesion_id": "ses_00000000-0000-4000-8000-000000000000", "minutos_reales": 1.0,
                               "minutos_cobrados": 10, "cobrado_usd": 0.08, "tarjeta_sert_usd": 0.25,
                               "ahorro_usd": 0.17}
    m.guia.estado["v42"] = "ESTACIONADO"
    d = m.espejo.detalle(m.ctrl, "v42", 10.0)
    assert d["estado"] == "CERRADA" and d["puesto"] is None and d["recibo"] is not None
    m.sesiones.sesion_de["v42"] = "ses_11111111-1111-4111-8111-111111111111"  # abrió otra sesión
    assert m.espejo.detalle(m.ctrl, "v42", 11.0)["recibo"] is None
