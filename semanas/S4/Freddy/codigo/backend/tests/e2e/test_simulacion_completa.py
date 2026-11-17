"""Controlador TraCI sin GUI (SUMO en `van3twin`) contra el backend vivo de esta computadora.

1 800 s simulados (el prompt dice 300; ver `HASTA_S`), penetración 50 %, semilla 2 (`traci.correr_kpis --id p50_rf_s2 --libsumo`; S4-3, antes p20_rf_s1). Mientras
corre, un cliente toma vehículos de `GET /espejo/candidatos`, los sigue por `/ws/espejo/{veh}` y
mira el `snapshot` público. Al final se comprueba:

- ninguna sesión cerrada en falso: `isStoppedParking(veh) == False` al cerrarse (marca `falsa`
  que pone `KPIsSistema._al_cerrar` en el mismo paso del cierre);
- `saldo = Σ recargas − Σ débitos` para cada usuario y ningún saldo bajo `−saldo_negativo_max_usd`;
- precisión del mapa (solo autos con app) ≥ valor de S3 − 5 puntos;
- modo espejo: el seguido aparece en `espejos` del snapshot y recibe el `recibo` una sola vez;
- el log del controlador no tiene excepciones.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

import httpx
import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from comun import esquemas as e
from comun.tarifa import cargar_tarifa

from .conftest import CODIGO, CONTENEDOR, CONTRATO, docker, host_desde_contenedor, ruta_en_contenedor

pytestmark = pytest.mark.e2e

# S4-3: con rf_final (0 falsas liberaciones) al 20 % solo se cierra 1 sesión real en 1 800 s. Se usa el
# escenario de la demo (50 %, semilla 2, primer cierre en t = 1 014 s), cambiable con ESERT_E2E_ID.
ID_CORRIDA = os.environ.get("ESERT_E2E_ID", "p50_rf_s2")
# El prompt pide 300 s, pero con las estadías de la demanda (10-120 min) en 300 s no se abre
# ninguna sesión y todas las comprobaciones quedarían vacías. 1 800 s (~90 s reales) sí abre y
# cierra sesiones. Se puede cambiar con ESERT_E2E_HASTA.
HASTA_S = int(os.environ.get("ESERT_E2E_HASTA", "1800"))
# S3-1 (semanas/S3/Freddy/RESUMEN.md, p50_rf_s1, 900 s): precisión del mapa solo app = 1,00. Se
# compara la métrica "solo app" porque la total depende de la penetración (con 20 % el mapa no
# ve al 80 % de los autos, por diseño) y no sería comparable con la corrida de S3 al 50 %.
PRECISION_S3_APP = 1.00
MARGEN = 0.05
MAX_SEGUIDOS = 6
# S4-3: además de los candidatos (BUSCANDO/GUIADO), se siguen autos cuyo conductor ya vuelve: son los
# que llegan a CERRADA dentro de la corrida. Con el umbral las sesiones se cerraban (en falso) enseguida.
MAX_POR_CERRAR = 4
ESTADOS_POR_CERRAR = {e.EstadoSesion.REGRESANDO, e.EstadoSesion.SALIENDO}
TIMEOUT_CORRIDA_S = 240


class Seguidor(threading.Thread):
    """Sigue un vehículo por `/ws/espejo/{veh}` hasta `espejo_fin` o el cierre del socket."""

    def __init__(self, url_ws: str, veh: str):
        super().__init__(daemon=True, name=f"espejo-{veh}")
        self.url, self.veh = f"{url_ws}/ws/espejo/{veh}", veh
        self.mensajes, self.errores, self.desde, self.hasta = [], [], None, None

    def run(self):
        try:
            with connect(self.url, open_timeout=5) as ws:
                self.desde = time.monotonic()
                while True:
                    m = e.leer_mensaje_ws(ws.recv(timeout=TIMEOUT_CORRIDA_S))
                    self.mensajes.append(m)
                    if isinstance(m, e.MensajeEspejoFin):
                        break
        except ConnectionClosed:
            pass
        except Exception as err:  # noqa: BLE001 — se reporta en la aserción
            self.errores.append(repr(err))
        finally:
            self.hasta = time.monotonic()

    @property
    def espejos(self):
        return [m for m in self.mensajes if isinstance(m, e.MensajeEspejo)]

    @property
    def cerrada(self) -> bool:
        return any(m.estado == e.EstadoSesion.CERRADA for m in self.espejos)

    @property
    def recibos(self) -> int:
        return sum(1 for m in self.espejos if m.recibo is not None)


class Snapshots(threading.Thread):
    """Lee `/ws/estado?rol=publico` y guarda (hora, snapshot)."""

    def __init__(self, url_ws: str):
        super().__init__(daemon=True, name="snapshots")
        self.url = f"{url_ws}/ws/estado?rol=publico"
        self.recibidos, self.alto, self.errores = [], threading.Event(), []

    def run(self):
        try:
            with connect(self.url, open_timeout=5) as ws:
                while not self.alto.is_set():
                    try:
                        m = e.leer_mensaje_ws(ws.recv(timeout=0.5))
                    except TimeoutError:
                        continue
                    self.recibidos.append((time.monotonic(), m))
        except ConnectionClosed:
            pass
        except Exception as err:  # noqa: BLE001
            self.errores.append(repr(err))


def comprobar_entorno_contenedor(url_desde_contenedor: str) -> None:
    """Dependencias de Python del contenedor y alcance del backend; si falla, el motivo exacto."""
    r = docker("exec", CONTENEDOR, "python3", "-c", "import httpx, pandas, pydantic, sqlalchemy, pyproj")
    if r.returncode != 0:
        pytest.fail("faltan dependencias en el contenedor; instala con "
                    "`docker exec van3twin pip3 install --user -r <codigo>/traci/requirements.txt "
                    f"-r <codigo>/backend/requirements-servidor.txt`:\n{r.stderr[-400:]}")
    sonda = (f"import urllib.request as u; print(u.urlopen('{url_desde_contenedor}/salud', timeout=5).status)")
    r = docker("exec", CONTENEDOR, "python3", "-c", sonda)
    if r.returncode != 0 or r.stdout.strip() != "200":
        pytest.fail(f"el contenedor no llega al backend en {url_desde_contenedor} "
                    f"(¿firewall de WSL/Windows?): {r.stderr.strip()[-300:]}")


def test_simulacion_completa_contra_backend_vivo(requiere_sumo, arrancar_servidor, tmp_path):
    servidor = arrancar_servidor(host="0.0.0.0")
    url_cont = f"http://{host_desde_contenedor()}:{servidor.port}"
    comprobar_entorno_contenedor(url_cont)

    codigo_cont = ruta_en_contenedor(CODIGO)
    volcado_rel = f"traci/salidas/e2e_{uuid.uuid4().hex[:8]}.json"
    sufijo = "_e2e"
    log = tmp_path / "controlador.log"
    cmd = (f"python3 -m traci.correr_kpis --id {ID_CORRIDA} --hasta {HASTA_S} --publicar {url_cont} "
           f"--sufijo {sufijo} --volcar {volcado_rel} --libsumo")  # S4-3: sin socket TraCI, ~35 % menos
    snaps = Snapshots(servidor.ws)
    snaps.start()
    seguidores: dict = {}
    with log.open("w", encoding="utf-8") as salida:
        proc = subprocess.Popen(["docker", "exec", "-w", codigo_cont, "-e", f"ESERT_TOKEN_SIM={servidor.token}",
                                 CONTENEDOR, "bash", "-lc", cmd], stdout=salida, stderr=subprocess.STDOUT)
        fin = time.monotonic() + TIMEOUT_CORRIDA_S
        with httpx.Client(base_url=f"{servidor.url}/api/v1", headers=CONTRATO, timeout=5) as c:
            while proc.poll() is None and time.monotonic() < fin:
                if len(seguidores) < MAX_SEGUIDOS:
                    for cand in c.get("/espejo/candidatos").json():
                        if cand["id"] not in seguidores and len(seguidores) < MAX_SEGUIDOS:
                            seguidores[cand["id"]] = Seguidor(servidor.ws, cand["id"])
                            seguidores[cand["id"]].start()
                if len(seguidores) < MAX_SEGUIDOS + MAX_POR_CERRAR:
                    ultimo = next((m for _, m in reversed(snaps.recibidos) if isinstance(m, e.MensajeSnapshot)), None)
                    for v in (ultimo.vehiculos if ultimo else []):
                        if (v.con_app and v.estado in ESTADOS_POR_CERRAR and v.id not in seguidores
                                and len(seguidores) < MAX_SEGUIDOS + MAX_POR_CERRAR):
                            seguidores[v.id] = Seguidor(servidor.ws, v.id)
                            seguidores[v.id].start()
                time.sleep(0.2)
        if proc.poll() is None:
            proc.kill()
            pytest.fail(f"el controlador no terminó en {TIMEOUT_CORRIDA_S} s; log en {log}")
    for s in seguidores.values():
        s.join(timeout=10)
    snaps.alto.set()
    snaps.join(timeout=5)

    texto_log = log.read_text(encoding="utf-8", errors="replace")
    volcado_host = CODIGO / volcado_rel
    try:
        # --- el controlador terminó bien y sin excepciones
        assert proc.returncode == 0, texto_log[-3000:]
        for marca in ("Traceback", "Exception", "Error:"):
            assert marca not in texto_log, f"{marca} en el log del controlador:\n{texto_log[-3000:]}"
        datos = json.loads(volcado_host.read_text(encoding="utf-8"))
    finally:
        volcado_host.unlink(missing_ok=True)
        (CODIGO / "traci" / "salidas_kpi" / f"ejemplo_{ID_CORRIDA}{sufijo}.json").unlink(missing_ok=True)

    fallos: list = []  # se juntan todas las comprobaciones: un fallo no esconde los demás

    def comprobar(cond: bool, mensaje: str) -> None:
        if not cond:
            fallos.append(mensaje)

    # --- cada sesión cerrada: el auto ya no estaba estacionado en SUMO al cerrarse
    sesiones = datos["sesiones_kpi"]
    comprobar(len(datos["cerradas"]) == len(sesiones) > 0,
              f"la corrida no cerró sesiones ({len(datos['cerradas'])} en el núcleo, {len(sesiones)} en KPIs)")
    falsas = [s for s in sesiones if s["falsa"]]
    comprobar(not falsas, f"falsas liberaciones: {len(falsas)}/{len(sesiones)} sesiones cerradas con el auto "
                          f"aún estacionado (isStoppedParking) — p. ej. {[s['veh'] for s in falsas[:5]]}")

    # --- libro: saldo = Σ recargas − Σ débitos, sin pasar del saldo negativo permitido
    tarifa = cargar_tarifa()
    debitos: dict = {}
    for s in datos["cerradas"]:
        debitos[s["usuario_id"]] = debitos.get(s["usuario_id"], 0) + round(s["debitado"] * 100)
    comprobar(bool(datos["recargas_usd"]), "ningún usuario recargó")
    for u, recarga_usd in datos["recargas_usd"].items():
        libro, estado = datos["libro"][u], datos["estado_billetera_centavos"][u]
        comprobar(libro["recarga_centavos"] == round(recarga_usd * 100), f"recarga de {u}: {libro}")
        comprobar(libro["debito_centavos"] == debitos.get(u, 0), f"débitos de {u}: {libro}")
        comprobar(estado["saldo"] == libro["recarga_centavos"] - libro["debito_centavos"], f"saldo de {u}: {estado}")
        comprobar(estado["saldo"] >= -round(tarifa.saldo_negativo_max_usd * 100), f"saldo bajo el mínimo {u}: {estado}")

    # --- mapa de ocupación
    kpis = datos["kpis"]
    comprobar(kpis["precision_mapa_app"] >= PRECISION_S3_APP - MARGEN,
              f"precision_mapa_app {kpis['precision_mapa_app']} < {PRECISION_S3_APP - MARGEN}")

    # --- modo espejo
    comprobar(bool(seguidores), "nunca hubo candidatos en GET /espejo/candidatos")
    for s in seguidores.values():
        comprobar(not s.errores, f"espejo {s.veh}: {s.errores}")
        comprobar(s.recibos <= 1, f"{s.veh} recibió {s.recibos} recibos")
        if s.cerrada:
            comprobar(s.recibos == 1, f"{s.veh} llegó a CERRADA sin recibo")
        en_snapshot = [m for t, m in snaps.recibidos if isinstance(m, e.MensajeSnapshot)
                       and s.desde and s.desde <= t <= (s.hasta or t) and s.veh in m.espejos]
        comprobar(bool(s.espejos and en_snapshot), f"{s.veh} no apareció en `espejos` mientras se lo seguía")
    comprobar(any(s.cerrada for s in seguidores.values()),
              f"ningún vehículo seguido llegó a CERRADA en {HASTA_S} s: "
              + str({v: [m.estado for m in s.espejos][-3:] for v, s in seguidores.items()}))
    comprobar(not snaps.errores, f"snapshots: {snaps.errores}")

    resumen = (f"{len(sesiones)} cerradas, {len(falsas)} falsas, {len(datos['recargas_usd'])} billeteras, "
               f"precision_mapa_app={kpis['precision_mapa_app']}, seguidos={len(seguidores)} "
               f"(cerrados {sum(s.cerrada for s in seguidores.values())}), "
               f"recibos={sum(s.recibos for s in seguidores.values())}")
    print("RESUMEN e2e SUMO:", resumen)
    assert not fallos, resumen + "\n- " + "\n- ".join(fallos)
