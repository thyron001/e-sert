"""Corre un escenario con guiado, sesiones y cobro en la simulación (S2-3).

Se ejecuta **dentro del contenedor** `van3twin`, desde `semanas/S3/Freddy/codigo`:

    python3 -m traci.correr_guiado --escenario app50_s1          # 75 min simulados, en segundo plano
    python3 -m traci.correr_guiado --escenario base_s1           # línea base sin app, para comparar
    python3 -m traci.correr_guiado --escenario app50_s1 --fuente verdad   # oráculo de comparación
    python3 -m traci.correr_guiado --escenario app50_s1 --publicar http://localhost:8000
    python3 -m traci.correr_guiado --escenario app50_s1 --publicar https://demo.e-sert.tesisucuenca.com --ritmo 1

Con `--publicar`, cada snapshot lleva además el bloque interno `espejo` (S3-3): candidatos y el
detalle de los autos que algún teléfono sigue (los que devuelve el backend en `espejos`).
`--ritmo F` frena la simulación a F veces el tiempo real (1 = la demo en vivo).

Escribe en `traci/salidas/` (ignorada por git): `sesiones_<esc>.csv`, `libro_<esc>.json`,
`busqueda_<esc>.csv` y `resumen_guiado_<esc>.json`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from .controlador import ConfigControlador, Controlador
from .espejo_publicador import EspejoPublicador, estado_vehiculo
from .estados import ControlSesiones
from .gps import EmuladorGPS
from .guiado import Guia, RegistroBusqueda
from .peatones import GestorPeatones, leer_destinos
from .ruta_geo import RutaGeo
from .puente_nucleo import MotivoCierre, Publicador, PuenteNucleo
from .sumo import cargar_sumolib

AQUI = Path(__file__).resolve().parent
SUMO = AQUI / "escenario" / "tyrone" / "sumo"
SALIDAS = AQUI / "salidas"


def liquidar_al_final(puente: PuenteNucleo, t: float) -> int:
    """Cierra con motivo `manual` las sesiones que siguen abiertas al terminar la corrida (S4).

    Es lo que hace el operador al terminar la demo: el contrato §3 acepta `manual` desde cualquier
    estado abierto. Se debita el tiempo hasta `t` y se libera la retención, así el libro queda
    saldado (retención final 0, criterio de S2-3). Se informa aparte (`liquidadas_fin_corrida`) y
    `--sin-liquidar` lo desactiva.
    """
    abiertas = list(puente.abiertas)
    for sesion_id in abiertas:
        puente.cerrar(sesion_id, t, motivo=MotivoCierre.manual)
    return len(abiertas)


def libro_cuadra(puente: PuenteNucleo) -> bool:
    """Por usuario: recargas = las que se dieron, débitos = Σ cobrado en sus sesiones cerradas y
    saldo = recargas − débitos (comparación independiente del cálculo del libro)."""
    debitos: dict = {}
    for fila in puente.cerradas:
        debitos[fila["usuario_id"]] = debitos.get(fila["usuario_id"], 0) + round(fila["debitado"] * 100)
    for usuario, f in puente.libro().items():
        if f["recarga_centavos"] != round(puente.recargas[usuario] * 100) or f["debito_centavos"] != debitos.get(usuario, 0):
            return False
        if puente.billetera.estado_centavos(usuario)["saldo"] != f["recarga_centavos"] - f["debito_centavos"]:
            return False
    return True


class PublicadorSnapshots:
    """Hook: cada segundo simulado empuja el estado del mundo (contrato §4.4) al backend."""

    def __init__(self, publicador: Publicador, sesiones: ControlSesiones, guia: Optional[Guia],
                 registro: RegistroBusqueda, peatones: GestorPeatones, net, kpis=None,
                 espejo: Optional[EspejoPublicador] = None):
        self.publicador = publicador
        # S3-3: con `espejo`, el cuerpo suma el bloque interno `espejo`; la respuesta del backend
        # dice qué autos sigue algún teléfono (`espejos`) y solo de esos se arma el detalle.
        self.espejo = espejo
        self.espejos: frozenset = frozenset()
        self.web = None  # AutosWeb (app web): eventos en el cuerpo, órdenes en la respuesta
        self.ritmo = None  # Ritmo: el backend puede pedir otro factor en la respuesta (`ritmo`)
        self._ultimo_cuerpo: Optional[dict] = None
        self._ultima_pos: dict = {}
        self.posiciones_invalidas = 0
        publicador.al_responder = self._al_responder
        # S3-1: con `kpis` (KPIsSistema), el campo `verdad` lleva la ocupación real de SUMO, los
        # autos con app estacionados y las falsas liberaciones del paso (contrato §4.4 y §6).
        self.kpis = kpis
        self.net = net  # sumolib: convierte (x, y) a lon/lat sin llamadas TraCI
        self.sesiones = sesiones
        self.guia = guia
        self.registro = registro
        self.peatones = peatones
        self._ultimo_s = -1
        self.omitidos_backend_caido = 0

    def on_paso(self, ctrl, t: float) -> None:
        if int(t) == self._ultimo_s:
            return
        self._ultimo_s = int(t)
        listo = getattr(self.publicador, "listo", None)
        if listo is not None and not listo():
            self.omitidos_backend_caido += 1  # backend caído: no se arma el cuerpo (cortacircuitos)
            return
        tc = ctrl.traci.constants
        vehiculos = []
        for veh, es_app in self.registro.con_app.items():
            if not es_app or veh not in ctrl.vehiculos:
                continue
            pos = self._posicion(f"sim_{veh}", ctrl.vehiculos[veh][tc.VAR_POSITION])
            if pos is None:
                continue
            vehiculos.append({"id": f"sim_{veh}", "lat": pos[0], "lon": pos[1],
                              "estado": self._estado(veh), "con_app": True})
        peatones = []
        for ped in self.peatones.activos.values():
            if ped.ped in ctrl.personas:
                pos = self._posicion(ped.ped, ctrl.personas[ped.ped][tc.VAR_POSITION])
                if pos is not None:
                    peatones.append({"id": ped.ped, "lat": pos[0], "lon": pos[1]})
        cuerpo = {
            "t_sim": round(t, 1),
            "ts": _ahora_iso(),
            "vehiculos": vehiculos,
            "peatones": peatones,
            "verdad": self._verdad(ctrl),
        }
        # v1.4: el mapa estimado vive en el núcleo del controlador (PuenteNucleo); sin esto el backend
        # solo ve sus propias sesiones HTTP y el visor queda en 0/610.
        puente = getattr(self.sesiones, "puente", None)
        if puente is not None:
            cuerpo["puestos"] = [{"puesto_id": o.puesto_id, "ocupados": o.ocupados, "capacidad": o.capacidad}
                                 for o in puente.mapa.ocupacion() if o.ocupados > 0]
        if self.espejo is not None:
            cuerpo["espejo"] = self.espejo.bloque(ctrl, t, self.espejos)
        if self.web is not None:
            eventos = self.web.eventos()
            if eventos:
                cuerpo["web"] = eventos
        self._ultimo_cuerpo = cuerpo
        self.publicador.publicar(cuerpo)

    def _al_responder(self, respuesta: dict) -> None:
        """Hilo del publicador: guarda la lista `espejos` y encola las órdenes de la app web."""
        self.espejos = frozenset(respuesta.get("espejos") or ())
        if self.web is not None:
            self.web.recibir(respuesta.get("ordenes"))
        pedido = respuesta.get("ritmo")
        if self.ritmo is not None and isinstance(pedido, (int, float)) and pedido > 0:
            self.ritmo.fijar(float(pedido))

    def fin_corrida(self) -> None:
        """Último snapshot con `espejo.fin`: los teléfonos reciben `espejo_fin` (`fin_simulacion`)."""
        if self.espejo is None or self._ultimo_cuerpo is None:
            return
        cuerpo = dict(self._ultimo_cuerpo, ts=_ahora_iso(), espejo={"candidatos": [], "detalle": {}, "fin": True})
        self.publicador.publicar(cuerpo)

    def _verdad(self, ctrl) -> dict:
        if self.kpis is None:
            return {"puestos": [], "estacionados": [], "falsas_liberaciones": []}
        cap = self.kpis.capacidad
        real = self.kpis.verdad.ocupacion(ctrl, cap)
        return {
            "puestos": [{"puesto_id": pid, "ocupados": min(r[0], cap[pid]), "capacidad": cap[pid]}
                        for pid, r in real.items()],
            "estacionados": [f"sim_{veh}" for veh in self.kpis.verdad.estacionados_app()],
            "falsas_liberaciones": self.kpis.tomar_falsas(),
        }

    def _posicion(self, agente: str, xy) -> Optional[tuple]:
        """(lat, lon) finita del agente. S3-3: SUMO a veces da a un auto estacionado la posición
        inválida -2^30, que sale como `inf` y vuelve inválido el JSON de **todo** el snapshot (el
        backend lo rechaza y el visor se congela). Se usa la última posición válida del agente; si
        nunca tuvo una, se omite en este snapshot."""
        x, y = xy
        if math.isfinite(x) and math.isfinite(y) and x > -1e9 and y > -1e9:
            lat, lon = self._latlon(x, y)
            if math.isfinite(lat) and math.isfinite(lon):
                self._ultima_pos[agente] = (lat, lon)
                return lat, lon
        self.posiciones_invalidas += 1
        return self._ultima_pos.get(agente)

    def _latlon(self, x: float, y: float) -> tuple:
        lon, lat = self.net.convertXY2LonLat(x, y)
        return round(lat, 7), round(lon, 7)

    def _estado(self, veh: str) -> Optional[str]:
        cerrados = self.espejo.recibos if self.espejo is not None else ()
        return estado_vehiculo(veh, self.sesiones, self.guia, cerrados)


def _ahora_iso() -> str:
    """Hora UTC con milisegundos (para medir la latencia hasta la pantalla del espejo)."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Ritmo:
    """Hook: frena la simulación a `factor` veces el tiempo real (1 = demo en vivo).

    2026-11-18: `fijar()` cambia el factor en plena corrida (el visor lo pide; llega en la
    respuesta de `/sim/paso`). Al cambiar, y si la simulación se atrasa más de `MAX_ATRASO_S`
    (no da abasto, p. ej. a 10× con sumo-gui), se toma el instante actual como nueva referencia:
    así no "recupera" el atraso corriendo a toda velocidad cuando luego se baja el ritmo.
    """

    MAX_ATRASO_S = 2.0

    def __init__(self, factor: float):
        self.factor = factor
        self._inicio: Optional[tuple] = None

    def fijar(self, factor: float) -> None:
        """Nuevo factor desde el próximo paso (se puede llamar desde otro hilo)."""
        if factor > 0 and factor != self.factor:
            self.factor = factor
            self._inicio = None

    def on_paso(self, ctrl, t: float) -> None:
        inicio = self._inicio
        if inicio is None:
            self._inicio = (time.perf_counter(), t)
            return
        t0_real, t0_sim = inicio
        espera = (t - t0_sim) / self.factor - (time.perf_counter() - t0_real)
        if espera > 0:
            time.sleep(espera)
        elif espera < -self.MAX_ATRASO_S:
            self._inicio = (time.perf_counter(), t)


def _progreso(ctrl, t: float) -> None:
    """Línea cada 300 s simulados: si SUMO cae, el log dice en qué segundo fue."""
    if int(t) % 300 == 0 and int(t) != _progreso.ultimo:
        _progreso.ultimo = int(t)
        print(f"progreso t={int(t)} s, autos en red={len(ctrl.vehiculos)}", flush=True)


_progreso.ultimo = -1


def main(argv: Optional[Sequence[str]] = None) -> dict:
    ap = argparse.ArgumentParser(description="Guiado, sesiones y cobro sobre un escenario de S2-3")
    ap.add_argument("--escenario", choices=["app50_s1", "base_s1"], default="app50_s1")
    ap.add_argument("--hasta", type=float, default=4500, help="Segundo de simulación final (75 min)")
    ap.add_argument("--fuente", choices=["mapa", "verdad"], default="mapa")
    ap.add_argument("--max-reasignaciones", type=int, default=3)
    ap.add_argument("--periodo-revision", type=float, default=10.0)
    ap.add_argument("--sin-guia", action="store_true", help="Solo sesiones, sin guiado (línea base con app)")
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--gps-semilla", type=int, default=1)
    ap.add_argument("--publicar", default=None, help="URL del backend (sin ruta), p. ej. http://localhost:8000")
    ap.add_argument("--gui", action="store_true")
    ap.add_argument("--ritmo", type=float, default=None,
                    help="Veces el tiempo real (1 = en vivo para la demo del espejo); sin esto, lo más rápido posible")
    ap.add_argument("--sin-espejo", action="store_true", help="No mandar el bloque interno espejo")
    ap.add_argument("--sin-liquidar", action="store_true",
                    help="No cerrar al final las sesiones abiertas (por defecto se liquidan con motivo manual)")
    args, extra = ap.parse_known_args(argv)

    cfg = SUMO / f"{args.escenario}.sumocfg"
    if not cfg.exists():  # S3: los escenarios unificados de Tyrone (`escenarios/app50_s1.sumocfg`)
        cfg = SUMO / "escenarios" / f"{args.escenario}.sumocfg"
    # las salidas llevan la fuente de ocupación si no es la del sistema, para no mezclar corridas
    esc = args.escenario if (args.fuente == "mapa" or args.sin_guia) else f"{args.escenario}_{args.fuente}"
    puente = PuenteNucleo(SUMO / "parqueos" / "puestos.csv", semilla=args.semilla)
    guia = None if args.sin_guia else Guia(puente, SUMO / "demanda" / "destinos.csv", args.fuente,
                                           args.max_reasignaciones, args.periodo_revision)
    gps = EmuladorGPS(semilla=args.gps_semilla)
    peatones = GestorPeatones(SUMO / "demanda" / "destinos.csv", semilla=args.semilla,
                              registrar_trayectorias=False)
    sesiones = ControlSesiones(gps, SALIDAS, esc, puente=puente, solo_con_app=True)
    registro = RegistroBusqueda()
    publicador = None
    net = None
    espejo = None
    if args.publicar:
        publicador = Publicador(args.publicar, token=os.environ.get("ESERT_TOKEN_SIM"))
        net = cargar_sumolib().net.readNet(str(SUMO / "red" / "centro.net.xml"))
        if not args.sin_espejo:
            destinos = guia.destinos if guia is not None else leer_destinos(SUMO / "demanda" / "destinos.csv")

            def a_geo(x: float, y: float) -> tuple:
                lon, lat = net.convertXY2LonLat(x, y)
                return lat, lon

            espejo = EspejoPublicador(sesiones, guia, puente, registro, destinos, a_geo, RutaGeo(net))
    snapshots = None

    # Cada corrida escribe sus salidas de SUMO en su propia carpeta (no comparten el .sumocfg)
    carpeta_sumo = SUMO / "salidas" / esc
    carpeta_sumo.mkdir(parents=True, exist_ok=True)
    salidas_sumo = ["--stop-output", str(carpeta_sumo / "stops.xml"),
                    "--tripinfo-output", str(carpeta_sumo / "tripinfo.xml"),
                    "--statistic-output", str(carpeta_sumo / "estadisticas.xml")]
    config = ConfigControlador(cfg=cfg, gui=args.gui, semilla=args.semilla, args_extra=extra + salidas_sumo,
                               etiqueta=f"s3_{esc}")
    inicio = time.perf_counter()
    try:
        with Controlador(config) as ctrl:
            ctrl.agregar_hook(peatones.on_paso)
            if guia is not None:
                ctrl.agregar_hook(guia.on_paso)
            ctrl.agregar_hook(sesiones.on_paso)
            ctrl.agregar_hook(registro.on_paso)
            if publicador is not None:
                snapshots = PublicadorSnapshots(publicador, sesiones, guia, registro, peatones, net,
                                                espejo=espejo)
                ctrl.agregar_hook(snapshots.on_paso)
            if args.ritmo:
                ctrl.agregar_hook(Ritmo(args.ritmo).on_paso)
            ctrl.agregar_hook(_progreso)
            ctrl.correr(args.hasta)
            t_final = ctrl.t
            abiertas_al_terminar = len(puente.abiertas)
            liquidadas = 0 if args.sin_liquidar else liquidar_al_final(puente, t_final)
    finally:
        sesiones.cerrar()
        if publicador is not None:
            if snapshots is not None:
                snapshots.fin_corrida()
            publicador.cerrar()
    tiempo_real = time.perf_counter() - inicio

    SALIDAS.mkdir(parents=True, exist_ok=True)
    puente.guardar_sesiones(SALIDAS / f"sesiones_{esc}.csv")
    puente.guardar_libro(SALIDAS / f"libro_{esc}.json")
    registro.guardar(SALIDAS / f"busqueda_{esc}.csv", guia)
    resumen = {
        "escenario": esc,
        "t_sim_final": t_final,
        "tiempo_real_s": round(tiempo_real, 1),
        "velocidad_sim_x_real": round(t_final / tiempo_real, 3) if tiempo_real else None,
        "guia": guia.resumen() if guia else None,
        "sesiones_maquina": sesiones.resumen(),
        "nucleo": puente.resumen(),
        "abiertas_al_terminar_la_simulacion": abiertas_al_terminar,
        "liquidadas_fin_corrida": liquidadas,
        "retencion_final_centavos": sum(f["retencion_neta_centavos"] for f in puente.libro().values()),
        "libro_cuadra": libro_cuadra(puente),
        "snapshots_omitidos_backend_caido": None if snapshots is None else snapshots.omitidos_backend_caido,
        "publicador": publicador.resumen() if publicador else None,
        "espejo": None if espejo is None else {
            "detalles_armados": espejo.detalles_armados, "recibos": len(espejo.recibos),
            "rutas_calculadas": espejo.ruta_geo.calculadas, "rutas_en_cache": espejo.ruta_geo.aciertos,
            "errores": espejo.errores},
        "peatones": peatones.resumen(),
    }
    (SALIDAS / f"resumen_guiado_{esc}.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    return resumen


if __name__ == "__main__":
    main()
