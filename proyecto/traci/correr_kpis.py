"""Corre una configuración `p{pen:02d}_{clf}_s{sem}` con guiado, sesiones y `KPIsSistema` (S3-1).

Usa los escenarios unificados de Tyrone (`proyecto/sumo/escenarios/generar_escenarios.py`, con
`--porc-app`), copiados a `traci/escenario/tyrone/sumo/` (ignorada por git). Reemplaza el MOCK de
`escenario_app.py` de S2-3.

Se ejecuta **dentro del contenedor** `van3twin`, desde `semanas/S3/Freddy/codigo`:

    python3 -m traci.correr_kpis --id p50_rf_s1 --hasta 900            # ejemplo para Tyrone
    python3 -m traci.correr_kpis --id p50_umbral_s1 --hasta 900
    python3 -m traci.correr_kpis --id p50_rf_s1 --hasta 900 --medir-costo 2   # con y sin KPIs
    python3 -m traci.correr_kpis --id p50_rf_s1 --publicar http://<host>:8000
    python3 -m traci.correr_kpis --id p50_umbral_s1 --hasta 4500 --publicar http://localhost:8000 --ritmo 10

Con `--publicar`, el snapshot lleva el bloque interno `espejo` (S3-3; `--sin-espejo` lo quita) y
`--ritmo F` frena la simulación a F veces el tiempo real (1 = demo en vivo).

Escribe `traci/salidas_kpi/ejemplo_<id>.json` (resumen; se sube al repo) y, en `traci/salidas/`
(ignorada), `kpis_sesiones_<id>.csv` y `kpis_mapa_<id>.csv`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Sequence

from .clasificacion import ClasificadorUsuario, buscar_proyecto
from .controlador import ConfigControlador, Controlador
from .estados import ControlSesiones
from .gps import EmuladorGPS
from .guiado import Guia, RegistroBusqueda
from .kpis_sistema import KPIsSistema
from .peatones import GestorPeatones
from .puente_nucleo import Publicador, PuenteNucleo

AQUI = Path(__file__).resolve().parent
SUMO = AQUI / "escenario" / "tyrone" / "sumo"
SALIDAS = AQUI / "salidas"
SALIDAS_KPI = AQUI / "salidas_kpi"
NOMBRES = {0: "base", 20: "app20", 50: "app50", 80: "app80"}  # los de generar_escenarios.py
PATRON_ID = re.compile(r"^p(\d{2})_(umbral|rf)_s(\d+)$")


def interpretar_id(id_corrida: str) -> tuple:
    """`p50_rf_s1` → `(50, "rf", 1)`."""
    m = PATRON_ID.match(id_corrida)
    if not m:
        raise ValueError(f"ID de corrida inválido: {id_corrida} (se espera p50_rf_s1)")
    return int(m.group(1)), m.group(2), int(m.group(3))


def preparar_escenario(pen: int, semilla: int, sumo: Path = SUMO) -> Path:
    """Copia `proyecto/sumo` (si falta) y genera la demanda del escenario. Devuelve el `.sumocfg`."""
    if not (sumo / "escenarios" / "generar_escenarios.py").exists():
        origen = buscar_proyecto() / "sumo"
        shutil.copytree(origen, sumo, dirs_exist_ok=True, ignore=shutil.ignore_patterns("salidas"))
    nombre = f"{NOMBRES.get(pen, f'app{pen}')}_s{semilla}"
    cfg = sumo / "escenarios" / f"{nombre}.sumocfg"
    if not (sumo / "escenarios" / f"{nombre}.rou.xml").exists() or not cfg.exists():
        subprocess.run([sys.executable, "generar_escenarios.py", "--semillas", str(semilla),
                        "--porcentajes", str(pen)], cwd=sumo / "escenarios", check=True)
    return cfg


def _progreso(ctrl, t: float) -> None:
    if int(t) % 300 == 0 and int(t) != _progreso.ultimo:
        _progreso.ultimo = int(t)
        print(f"progreso t={int(t)} s, autos en red={len(ctrl.vehiculos)}", flush=True)


_progreso.ultimo = -1


class _Captura:
    """Hook: `traci.gui.screenshot` de la vista principal en el segundo simulado T (`ruta.png@T`)."""

    def __init__(self, especificacion: str):
        ruta, _, t = especificacion.rpartition("@")
        self.ruta, self.t = (ruta, float(t)) if ruta else (especificacion, 60.0)
        self.hecha = False

    def on_paso(self, ctrl, t: float) -> None:
        if not self.hecha and t >= self.t:
            Path(self.ruta).parent.mkdir(parents=True, exist_ok=True)
            ctrl.traci.gui.screenshot("View #0", str(self.ruta))
            self.hecha = True
            print(f"captura sumo-gui en t={int(t)} s → {self.ruta}", flush=True)


class PublicadorNulo:
    """Publicador sin red para medir el costo de armar el snapshot (serializa y descarta)."""

    def __init__(self):
        self.enviados = 0

    def publicar(self, cuerpo: dict) -> None:
        json.dumps(cuerpo)
        self.enviados += 1

    def cerrar(self) -> None:
        pass

    def resumen(self) -> dict:
        return {"enviados": self.enviados}


def correr(id_corrida: str, hasta: float = 900, con_kpis: bool = True, publicar: Optional[str] = None,
           gps_semilla: int = 1, sufijo: str = "", *, sigma_m: float = 5.0, p_perdida: float = 0.02,
           rafaga_s: Optional[float] = None, frac_rafaga: float = 0.3, frac_apagado: float = 0.0,
           libsumo: bool = False, en_lote: bool = True, solo_busca: bool = True, cache_parametros: bool = True,
           contar_eventos: bool = True, args_sumo: Sequence[str] = (), geo_local: bool = True,
           politica_datos_pobres: bool = True, ws_nulo: bool = False, guardar_csv: bool = True,
           instrumentar: Optional[Callable[[dict], None]] = None, espejo: bool = True,
           peatones_solo_web: bool = False,
           ritmo: Optional[float] = None, volcar: Optional[Path] = None, gui: bool = False,
           captura: Optional[str] = None) -> dict:
    """Una corrida. Devuelve el resumen (con `kpis` si `con_kpis`) y el tiempo por paso.

    S3-2: parámetros del GPS (`sigma_m`, `p_perdida`, ráfagas `rafaga_s`/`frac_rafaga`), teléfonos
    apagados (`frac_apagado`), `libsumo`, inferencia en lote, suscripción solo a autos que buscan
    (`solo_busca`), `ws_nulo` (arma el snapshot sin red, para el perfil) e `instrumentar(partes)`,
    que recibe los componentes ya enchufados antes de correr (lo usa `perfil.py`).

    S4-1: `volcar` escribe un JSON con el libro de cada billetera y cada sesión cerrada (con la
    marca `falsa`: el auto seguía `isStoppedParking` al cerrarse); lo leen las pruebas e2e.
    S4-3: `gui` abre `sumo-gui` (pantalla :99 del contenedor) y `captura="ruta.png@T"` guarda una
    captura de la vista en el segundo simulado T (`traci.gui.screenshot`).
    """
    pen, clf, semilla = interpretar_id(id_corrida)
    os.environ["ESERT_CLASIFICADOR"] = clf  # lo lee la inferencia de Pablo al cargar el modelo
    cfg = preparar_escenario(pen, semilla)
    puente = PuenteNucleo(SUMO / "parqueos" / "puestos.csv", semilla=semilla)
    guia = Guia(puente, SUMO / "demanda" / "destinos.csv", "mapa")
    peatones = GestorPeatones(SUMO / "demanda" / "destinos.csv", semilla=semilla, registrar_trayectorias=False,
                              solo_web=peatones_solo_web)
    clasificador = ClasificadorUsuario()
    gps = EmuladorGPS(semilla=gps_semilla, sigma_m=sigma_m, p_perdida=p_perdida, rafaga_s=rafaga_s,
                      frac_rafaga=frac_rafaga)
    sesiones = ControlSesiones(gps, SALIDAS, id_corrida + sufijo, clasificador=clasificador, puente=puente,
                               solo_con_app=True, politica_datos_pobres=politica_datos_pobres,
                               frac_apagado=frac_apagado, semilla_apagado=semilla, en_lote=en_lote)
    registro = RegistroBusqueda()
    pub_kpi = Publicador(publicar, token=os.environ.get("ESERT_TOKEN_SIM"), ruta="/api/v1/sim/kpi") if publicar else None
    pub_paso = Publicador(publicar, token=os.environ.get("ESERT_TOKEN_SIM")) if publicar else None
    if pub_paso is None and ws_nulo:
        pub_paso = PublicadorNulo()

    config = ConfigControlador(cfg=cfg, semilla=semilla, etiqueta=f"kpis_{id_corrida}{sufijo}_{int(con_kpis)}",
                               libsumo=libsumo, cache_parametros=cache_parametros, args_extra=list(args_sumo),
                               gui=gui)
    kpis = None
    snapshots = None
    pub_espejo = None
    reloj = {"s": 0.0}
    inicio = time.perf_counter()
    try:
        with Controlador(config) as ctrl:
            if geo_local:
                # (x, y) → (lat, lon) con pyproj local en vez de `convertGeo` por TraCI en cada
                # muestra GPS (mismo resultado, < 1e-9°; lo comprueba test_integracion_sumo de S1).
                from .generar_trazas import conversor_red

                ctrl.a_geo = conversor_red(SUMO / "red" / "centro.net.xml")
            if solo_busca:
                # Solo los autos que buscan parqueo se leen por vehículo; el tráfico de fondo
                # (~5 000 autos) no lo usa ningún hook y suscribirlo cuesta en cada paso.
                ctrl.config.filtro_vehiculos = lambda v: ctrl.parametro(v, "clase") == "busca"
            ctrl.agregar_hook(peatones.on_paso)
            ctrl.agregar_hook(guia.on_paso)
            ctrl.agregar_hook(sesiones.on_paso)
            ctrl.agregar_hook(registro.on_paso)
            if con_kpis:
                kpis = KPIsSistema(ctrl, puente, intervalo_mapa_s=60, publicador_kpi=pub_kpi,
                                   contar_eventos=contar_eventos)
                # Sobrecosto medido en la misma corrida: se cronometran los hooks de KPIs
                # (verdad + KPIs; los dos últimos registrados) y el oyente de cierres.
                ctrl.hooks[-2:] = [_cronometrar(h, reloj) for h in ctrl.hooks[-2:]]
                puente.al_cerrar[:] = [_cronometrar(h, reloj) for h in puente.al_cerrar]
            if pub_paso is not None:
                from .correr_guiado import PublicadorSnapshots
                from .espejo_publicador import EspejoPublicador
                from .ruta_geo import RutaGeo
                from .sumo import cargar_sumolib

                net = cargar_sumolib().net.readNet(str(SUMO / "red" / "centro.net.xml"))
                if espejo and publicar:
                    pub_espejo = EspejoPublicador(sesiones, guia, puente, registro, guia.destinos, ctrl.a_geo,
                                                  RutaGeo(net))
                snapshots = PublicadorSnapshots(pub_paso, sesiones, guia, registro, peatones, net, kpis=kpis,
                                                espejo=pub_espejo)
                ctrl.agregar_hook(snapshots.on_paso)
                if publicar:
                    # App web (2026-11-18): el backend ordena crear y mover autos propios en SUMO.
                    from .autos_web import AutosWeb

                    snapshots.web = AutosWeb(guia, peatones)
                    ctrl.agregar_hook(snapshots.web.on_paso)
            if ritmo:
                from .correr_guiado import Ritmo

                reloj_ritmo = Ritmo(ritmo)
                ctrl.agregar_hook(reloj_ritmo.on_paso)
                if snapshots is not None:
                    snapshots.ritmo = reloj_ritmo  # el visor puede cambiarlo en vivo
            if captura:
                ctrl.agregar_hook(_Captura(captura).on_paso)
            ctrl.agregar_hook(_detener_entre_pasos)
            ctrl.agregar_hook(_progreso)
            if instrumentar is not None:
                instrumentar({"ctrl": ctrl, "peatones": peatones, "guia": guia, "sesiones": sesiones,
                              "registro": registro, "puente": puente, "kpis": kpis,
                              "clasificador": clasificador, "progreso": _progreso})
            ctrl.correr(hasta)
            t_final, pasos = ctrl.t, ctrl.pasos
    finally:
        sesiones.cerrar()
        if snapshots is not None:
            snapshots.fin_corrida()
        for pub in (pub_kpi, pub_paso):
            if pub is not None:
                pub.cerrar()
    tiempo_real = time.perf_counter() - inicio
    fuentes = dict(sesiones.fuentes)
    salida = {
        "id": id_corrida,
        "porc_app": pen,
        "clasificador_pedido": clf,
        "clasificador_usado": "rf" if fuentes.get("rf") else "umbral",
        "ventanas_por_fuente": fuentes,
        "t_sim_final": t_final,
        "pasos": pasos,
        "tiempo_real_s": round(tiempo_real, 2),
        "ms_por_paso": round(1000 * tiempo_real / max(1, pasos), 3),
        "sesiones_maquina": sesiones.resumen(),
        "espejo": None if pub_espejo is None else {
            "detalles_armados": pub_espejo.detalles_armados, "recibos": len(pub_espejo.recibos),
            "rutas_calculadas": pub_espejo.ruta_geo.calculadas, "rutas_en_cache": pub_espejo.ruta_geo.aciertos,
            "errores": pub_espejo.errores},
        "publicador": None if publicar is None or not hasattr(pub_paso, "resumen") else pub_paso.resumen(),
        "opciones": {"sigma_m": sigma_m, "p_perdida": p_perdida, "rafaga_s": rafaga_s, "frac_rafaga": frac_rafaga,
                     "frac_apagado": frac_apagado, "libsumo": libsumo, "en_lote": en_lote, "solo_busca": solo_busca,
                     "cache_parametros": cache_parametros, "contar_eventos": contar_eventos,
                     "args_sumo": list(args_sumo), "geo_local": geo_local,
                     "politica_datos_pobres": politica_datos_pobres},
    }
    if kpis is not None:
        resto = tiempo_real - reloj["s"]
        salida["costo_kpis"] = {"s_en_kpis": round(reloj["s"], 3), "s_resto": round(resto, 3),
                                "sobrecosto_pct": round(100 * reloj["s"] / resto, 2)}
        salida["kpis"] = kpis.resumen()
        if frac_apagado > 0:
            salida["apagados"] = proyeccion_apagados(sesiones, kpis)
        if guardar_csv:
            SALIDAS.mkdir(parents=True, exist_ok=True)
            nombre = id_corrida + sufijo
            kpis.detalle_sesiones().to_csv(SALIDAS / f"kpis_sesiones_{nombre}.csv", index=False)
            kpis.serie_mapa().to_csv(SALIDAS / f"kpis_mapa_{nombre}.csv", index=False)
    if volcar is not None:
        volcar = Path(volcar)
        volcar.parent.mkdir(parents=True, exist_ok=True)
        volcar.write_text(_json(volcado(puente, kpis, salida)), encoding="utf-8")
    return salida


def volcado(puente: PuenteNucleo, kpis: Optional[KPIsSistema], salida: dict) -> dict:
    """Libro de billeteras y sesiones de la corrida, para comprobar invariantes desde fuera (S4-1)."""
    return {
        "recargas_usd": dict(puente.recargas),
        "libro": puente.libro(),
        "estado_billetera_centavos": {u: puente.billetera.estado_centavos(u) for u in puente.recargas},
        "cerradas": list(puente.cerradas),
        "abiertas": len(puente.abiertas),
        "sesiones_kpi": [] if kpis is None else [
            {k: s[k] for k in ("sesion_id", "usuario_id", "veh", "t_fin", "motivo", "debitado", "falsa")}
            for s in kpis.sesiones],
        "kpis": salida.get("kpis"),
        "espejo": salida.get("espejo"),
        "publicador": salida.get("publicador"),
    }


def proyeccion_apagados(sesiones: ControlSesiones, kpis: KPIsSistema) -> dict:
    """Teléfonos apagados: cuántas sesiones terminan en `timeout_sin_senal` y su error de cobro.

    Una corrida de 30 min no llega al tope de 120 min, así que para las sesiones apagadas cuyo
    auto ya salió se **proyecta** el cobro al tope: `costo(tiempo_maximo) − costo(estadía real)`.
    """
    from .puente_nucleo import tar

    tope_min = sesiones.tiempo_maximo_s / 60
    errores = []
    for veh in sesiones.apagados:
        llegada, salida = kpis.verdad.estadia(veh)
        if llegada is not None and salida is not None:
            errores.append(round(tar.costo(tope_min) - tar.costo((salida - llegada) / 60), 2))
    cerradas = [s for s in kpis.sesiones if s["motivo"] == "timeout_sin_senal"]
    return {
        "telefonos_apagados": len(sesiones.apagados),
        "apagados_efectivos": sesiones.apagados_efectivos,
        "marcadas_sin_senal": sesiones.marcadas_sin_senal,
        "cierres_timeout_en_corrida": len(cerradas),
        "esperando_tope_al_final": len(sesiones.esperando_tope),
        "auto_ya_salio": len(errores),
        "error_proyectado_medio_usd": round(sum(errores) / len(errores), 3) if errores else None,
        "error_proyectado_max_usd": max(errores) if errores else None,
        "falsas_entre_apagados": sum(1 for s in kpis.sesiones if s["veh"] in sesiones.apagados and s["falsa"]),
    }


def _cronometrar(funcion, reloj: dict):
    """Envuelve un hook u oyente y suma su tiempo de pared en `reloj["s"]`."""
    def envuelta(*args):
        t0 = time.perf_counter()
        try:
            return funcion(*args)
        finally:
            reloj["s"] += time.perf_counter() - t0
    envuelta.__wrapped__ = funcion
    return envuelta


def _json(obj) -> str:
    """JSON sin `NaN` (no es JSON válido): los NaN se escriben como `null`."""
    def limpiar(x):
        if isinstance(x, float) and math.isnan(x):
            return None
        if isinstance(x, dict):
            return {k: limpiar(v) for k, v in x.items()}
        return x
    return json.dumps(limpiar(obj), indent=2, ensure_ascii=False)


DETENER = threading.Event()


class CorridaDetenida(Exception):
    """La corrida se detuvo a pedido (Ctrl+C o stdin cerrado), entre dos pasos de SUMO."""


def _detener_entre_pasos(ctrl, t: float) -> None:
    """Hook: si se pidió detener, corta la corrida **entre** pasos, con el protocolo TraCI en un estado
    limpio; así `traci.close()` funciona y SUMO termina bien (S4-3)."""
    if DETENER.is_set():
        raise CorridaDetenida(f"detenida en t={int(t)} s")


def pedir_detencion(signum=None, frame=None) -> None:
    """Primer Ctrl+C: pide detener entre pasos. Segundo Ctrl+C: interrumpe ya (por si algo se cuelga)."""
    if DETENER.is_set():
        raise KeyboardInterrupt
    DETENER.set()
    print("deteniendo la corrida al terminar el paso actual (otro Ctrl+C la corta ya)", flush=True)


def vigilar_stdin() -> threading.Thread:
    """S4-3: pide detener la corrida cuando se cierra la entrada estándar.

    `docker exec` sin TTY no reenvía Ctrl+C al proceso del contenedor: si el lanzador muere, el
    controlador y `sumo` quedan vivos. Lanzado con `docker exec -i … --vigilar-stdin`, al morir el
    cliente se cierra stdin y la corrida se detiene entre dos pasos, como con un Ctrl+C.
    """

    def bucle():
        while sys.stdin.buffer.read(4096):
            pass
        print("stdin cerrado: deteniendo la corrida", flush=True)
        DETENER.set()

    hilo = threading.Thread(target=bucle, name="vigilar-stdin", daemon=True)
    hilo.start()
    return hilo


def main(argv: Optional[Sequence[str]] = None) -> dict:
    ap = argparse.ArgumentParser(description="Corrida con KPIs de sistema (S3-1)")
    ap.add_argument("--id", default="p50_rf_s1", help="p{pen:02d}_{umbral|rf}_s{semilla}")
    ap.add_argument("--hasta", type=float, default=900, help="Segundo de simulación final")
    ap.add_argument("--publicar", default=None, help="URL del backend (sin ruta)")
    ap.add_argument("--sufijo", default="", help="Sufijo de los archivos de salida (p. ej. _3600)")
    ap.add_argument("--ritmo", type=float, default=None, help="Veces el tiempo real (1 = demo en vivo)")
    ap.add_argument("--sin-espejo", action="store_true", help="No mandar el bloque interno espejo")
    ap.add_argument("--vigilar-stdin", action="store_true",
                    help="termina al cerrarse stdin (lanzar con `docker exec -i`; Ctrl+C del lanzador)")
    ap.add_argument("--gui", action="store_true", help="abre sumo-gui (pantalla :99, VNC 5901)")
    ap.add_argument("--captura", default=None, help="ruta.png@T: captura de sumo-gui en el segundo simulado T")
    ap.add_argument("--libsumo", action="store_true",
                    help="SUMO en el mismo proceso, sin socket TraCI (sin GUI; S4-3: e2e más rápido)")
    ap.add_argument("--volcar", type=Path, default=None,
                    help="JSON con libro de billeteras y sesiones (pruebas e2e, S4-1)")
    ap.add_argument("--medir-costo", type=int, default=0, metavar="N",
                    help="Corre N pares (sin KPIs, con KPIs) y escribe costo_<id>.json")
    args = ap.parse_args(argv)
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, pedir_detencion)
    if args.vigilar_stdin:
        vigilar_stdin()
    SALIDAS_KPI.mkdir(parents=True, exist_ok=True)

    if args.medir_costo:
        sin, con = [], []
        for _ in range(args.medir_costo):
            sin.append(correr(args.id, args.hasta, con_kpis=False)["ms_por_paso"])
            con.append(correr(args.id, args.hasta, con_kpis=True)["ms_por_paso"])
        costo = {"id": args.id, "hasta": args.hasta, "ms_por_paso_sin_kpis": sin, "ms_por_paso_con_kpis": con,
                 "sobrecosto_pct": round(100 * (min(con) / min(sin) - 1), 2)}
        (SALIDAS_KPI / f"costo_{args.id}.json").write_text(_json(costo), encoding="utf-8")
        print(_json(costo))
        return costo

    salida = correr(args.id, args.hasta, publicar=args.publicar, sufijo=args.sufijo, espejo=not args.sin_espejo,
                    ritmo=args.ritmo, volcar=args.volcar, gui=args.gui, captura=args.captura,
                    libsumo=args.libsumo)
    (SALIDAS_KPI / f"ejemplo_{args.id}{args.sufijo}.json").write_text(_json(salida), encoding="utf-8")
    print(_json(salida))
    return salida


if __name__ == "__main__":
    try:
        main()
    except CorridaDetenida as motivo:
        print(f"corrida {motivo}; TraCI y SUMO cerrados", flush=True)
        sys.exit(130)
    except KeyboardInterrupt:
        print("corrida interrumpida (segundo Ctrl+C)", flush=True)
        sys.exit(130)
