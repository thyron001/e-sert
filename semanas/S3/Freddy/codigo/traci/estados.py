"""Máquina de estados de la sesión de parqueo (contrato §3) y su control como hook del Controlador.

- `MaquinaSesion` es pura (sin TraCI): recibe cada ventana de 5 s el modo clasificado y la
  distancia al puesto, y devuelve las transiciones. Así se prueba sin SUMO.
- `ControlSesiones` es el hook de TraCI: abre una sesión por cada auto de búsqueda que
  estaciona, lleva el teléfono `sim_<veh>` con el `EmuladorGPS` (la posición del auto si está
  dentro, la del peatón si camina), clasifica con `clasificacion.py`, registra los CSV y cuenta
  las **falsas liberaciones**: cerrar la sesión mientras el auto sigue estacionado.

S3-2 (robustez):
- **Datos pobres:** si la ventana trae menos del 50 % de las muestras esperadas, o la inferencia
  cayó al *fallback* (fuente distinta de `rf`) con confianza < 0,5, no hay transición: se
  mantiene el estado y no avanza la cuenta de ventanas en vehículo.
- **Teléfono apagado:** en una fracción de las sesiones (`frac_apagado`) el teléfono deja de
  emitir al pasar a `A_PIE`. El silencio nunca cierra la sesión; tras `t_sin_senal_s` (120 s) sin
  datos se marca `sin_senal`. Una sesión `sin_senal` se cierra al llegar a `tiempo_maximo_min`
  con el motivo `timeout_sin_senal` (propuesto en `comun/CONTRATO.propuesto.md`).
- La inferencia se hace **en lote**: una llamada a `clasificar_lote` por paso para todos los
  usuarios a los que les toca ventana.
"""

from __future__ import annotations

import csv
import math
import random
from collections import Counter, namedtuple
from pathlib import Path
from typing import Dict, List, Optional

from comun.esquemas import MotivoCierre

from .controlador import parametro
from .clasificacion import ClasificadorUsuario, haversine_m
from .gps import EmuladorGPS, modo_real_persona, modo_real_vehiculo

ESTADOS = ("BUSCANDO", "GUIADO", "ESTACIONADO", "A_PIE", "REGRESANDO", "SALIENDO", "CERRADA")
Transicion = namedtuple("Transicion", "t_sim usuario_id desde hacia modo distancia_m")
EN_AUTO = "en_auto"  # descripción de la etapa de espera del peatón que se queda dentro del auto
COBERTURA_MIN = 0.5
CONFIANZA_MIN_FALLBACK = 0.5
T_SIN_SENAL_S = 120.0
TIEMPO_MAXIMO_S = 120 * 60.0  # tarifa.json: tiempo_maximo_min


def datos_pobres(cobertura: float, fuente: str, confianza: float,
                 cobertura_min: float = COBERTURA_MIN, confianza_min: float = CONFIANZA_MIN_FALLBACK) -> bool:
    """True si la ventana no alcanza para decidir: pocas muestras o *fallback* poco confiable."""
    return cobertura < cobertura_min or (fuente != "rf" and confianza < confianza_min)


class MaquinaSesion:
    """Estados de una sesión (un usuario `sim_<veh>`), con los umbrales del contrato como parámetros.

    La sesión existe desde `ESTACIONADO` (contrato §3). `SALIENDO` se cierra en el mismo paso
    (`SALIENDO → CERRADA`, motivo `deteccion`): el controlador es quien cierra.
    """

    def __init__(self, usuario_id: str, dist_a_pie_m: float = 15, dist_regreso_m: float = 30,
                 dist_salida_m: float = 20, ventanas_vehiculo: int = 2, politica_datos_pobres: bool = True):
        self.usuario_id = usuario_id
        self.dist_a_pie_m = dist_a_pie_m
        self.dist_regreso_m = dist_regreso_m
        self.dist_salida_m = dist_salida_m
        self.ventanas_vehiculo = ventanas_vehiculo
        self.politica_datos_pobres = politica_datos_pobres
        self.estado = "ESTACIONADO"
        self.retenidas = 0  # ventanas ignoradas por datos pobres
        self._vehiculo_seguido = 0

    def actualizar(self, modo: str, distancia_m: float, t_sim: float, cobertura: float = 1.0,
                   fuente: str = "rf", confianza: float = 1.0) -> List[Transicion]:
        """Procesa una ventana. Devuelve las transiciones ocurridas (0, 1 o 2)."""
        if self.estado == "CERRADA":
            return []
        if self.politica_datos_pobres and datos_pobres(cobertura, fuente, confianza):
            self.retenidas += 1
            return []
        if modo == "vehiculo" and distancia_m > self.dist_salida_m:
            self._vehiculo_seguido += 1
        else:
            self._vehiculo_seguido = 0

        desde = self.estado
        nuevo = self._siguiente(modo, distancia_m)
        if nuevo is None:
            return []
        transiciones = [Transicion(t_sim, self.usuario_id, desde, nuevo, modo, round(distancia_m, 1))]
        self.estado = nuevo
        if nuevo == "SALIENDO":
            transiciones.append(Transicion(t_sim, self.usuario_id, "SALIENDO", "CERRADA", modo,
                                           round(distancia_m, 1)))
            self.estado = "CERRADA"
        return transiciones

    def _siguiente(self, modo: str, distancia_m: float) -> Optional[str]:
        """Regla de transición del contrato §3 (la primera que aplique)."""
        if self.estado in ("ESTACIONADO", "REGRESANDO") and self._vehiculo_seguido >= self.ventanas_vehiculo:
            return "SALIENDO"
        if self.estado == "ESTACIONADO" and modo == "a_pie" and distancia_m > self.dist_a_pie_m:
            return "A_PIE"
        if self.estado == "A_PIE" and modo in ("a_pie", "quieto") and distancia_m < self.dist_regreso_m:
            return "REGRESANDO"
        if self.estado == "REGRESANDO" and modo == "a_pie" and distancia_m > self.dist_regreso_m:
            return "A_PIE"  # se volvió a alejar
        return None


def _finitas(*valores: float) -> bool:
    return all(math.isfinite(v) for v in valores)


class ControlSesiones:
    """Hook `on_paso` de `Controlador`: sesiones de parqueo con GPS emulado y clasificación."""

    def __init__(self, gps: EmuladorGPS, salidas: Path, escenario: str,
                 clasificador: Optional[ClasificadorUsuario] = None, puente=None,
                 solo_con_app: bool = False, politica_datos_pobres: bool = True,
                 frac_apagado: float = 0.0, semilla_apagado: int = 1,
                 t_sin_senal_s: float = T_SIN_SENAL_S, tiempo_maximo_s: float = TIEMPO_MAXIMO_S,
                 en_lote: bool = True):
        self.gps = gps
        self.clasificador = clasificador or ClasificadorUsuario()
        # Con `puente` (S2-3), cada sesión se abre y se cierra en el núcleo del backend.
        self.puente = puente
        self.solo_con_app = solo_con_app
        self.politica_datos_pobres = politica_datos_pobres
        self.frac_apagado = frac_apagado
        self._rng_apagado = random.Random(semilla_apagado)
        self.t_sin_senal_s = t_sin_senal_s
        self.tiempo_maximo_s = tiempo_maximo_s
        self.en_lote = en_lote
        self.sesion_de: Dict[str, str] = {}
        self.maquinas: Dict[str, MaquinaSesion] = {}
        # Puesto = punto donde el auto se estacionó (lat, lon); un parkingArea mide ~100 m y su
        # centro quedaría a más de 30 m de cualquier auto.
        self.puesto_ll: Dict[str, tuple] = {}
        self.puesto_de: Dict[str, str] = {}
        self.t_inicio: Dict[str, float] = {}
        self._ultima_fila: Dict[str, dict] = {}
        self._ultima_muestra: Dict[str, float] = {}
        self.apagados: set = set()          # sesiones cuyo teléfono se apagará en A_PIE
        self.apagado_desde: Dict[str, float] = {}
        self.apagados_efectivos = 0  # teléfonos que de verdad se apagaron (llegaron a A_PIE)
        self.sin_senal: Dict[str, float] = {}  # veh → t en que se marcó sin_senal
        self.marcadas_sin_senal = 0
        self.esperando_tope: Dict[str, float] = {}  # veh que salió de la red sin señal → t límite
        self.llegadas = 0
        self.coords_invalidas = 0  # muestras o puestos con coordenadas no finitas (descartados)
        self.cerradas = 0
        self.cierres_timeout = 0
        self.falsas_liberaciones = 0
        self.falsas_con_datos_pobres = 0
        self.ventanas_retenidas = 0
        self.fuentes: Counter = Counter()
        self.ultimo_modo: Dict[str, dict] = {}  # usuario → último ResultadoModo (lo ve el espejo, S3-3)

        salidas.mkdir(parents=True, exist_ok=True)
        self._archivos = {
            "transiciones": (salidas / f"transiciones_{escenario}.csv").open("w", newline="", encoding="utf-8"),
            "ventanas": (salidas / f"ventanas_{escenario}.csv").open("w", newline="", encoding="utf-8"),
            "falsas": (salidas / f"falsas_liberaciones_{escenario}.csv").open("w", newline="", encoding="utf-8"),
        }
        cabeceras = {
            "transiciones": ["t_sim", "usuario_id", "desde", "hacia", "modo", "distancia_m"],
            "ventanas": ["t_sim", "usuario_id", "estado", "modo_clasificado", "confianza", "fuente",
                         "distancia_m", "modo_real", "cobertura", "retenida"],
            "falsas": ["t_sim", "usuario_id", "puesto_id", "distancia_m"],
        }
        self._escritores = {}
        for clave, archivo in self._archivos.items():
            self._escritores[clave] = csv.writer(archivo)
            self._escritores[clave].writerow(cabeceras[clave])

    # ------------------------------------------------------------------ hook

    def on_paso(self, ctrl, t: float) -> None:
        """Llamado tras cada paso del `Controlador`."""
        self._abrir_llegadas(ctrl, t)
        self._cerrar_por_tope(t)

        activos = []
        for veh in list(self.maquinas):
            if veh not in ctrl.vehiculos:  # el auto salió de la red sin detección
                self._auto_fuera(veh, t)
                continue
            self._muestrear(ctrl, veh, t)
            self._revisar_senal(veh, t)
            activos.append(veh)

        usuarios = [f"sim_{veh}" for veh in activos]
        if self.en_lote:
            resultados = self.clasificador.evaluar_lote(usuarios, t)
        else:
            resultados = {}
            for u in usuarios:
                r = self.clasificador.evaluar(u, t)
                if r is not None:
                    resultados[u] = r
        for veh in activos:
            resultado = resultados.get(f"sim_{veh}")
            if resultado is not None and f"sim_{veh}" in self._ultima_fila:
                self._procesar_ventana(ctrl, veh, t, resultado)

    def _abrir_llegadas(self, ctrl, t: float) -> None:
        tr = ctrl.traci
        for veh in tr.simulation.getParkingStartingVehiclesIDList():
            if parametro(ctrl, veh, "clase") != "busca" or veh in self.maquinas or veh in self.t_inicio:
                continue
            if self.solo_con_app and parametro(ctrl, veh, "con_app") != "1":
                continue
            self.maquinas[veh] = MaquinaSesion(f"sim_{veh}", politica_datos_pobres=self.politica_datos_pobres)
            self.puesto_de[veh] = tr.vehicle.getStops(veh)[0].stoppingPlaceID
            self.t_inicio[veh] = t
            if self.frac_apagado > 0 and self._rng_apagado.random() < self.frac_apagado:
                self.apagados.add(veh)
            x, y = tr.vehicle.getPosition(veh)
            lat, lon = ctrl.a_geo(x, y)
            if not _finitas(lat, lon) and self.puente is not None:
                # SUMO a veces da una posición no válida con el auto recién parado: se usa el puesto
                lat, lon = self.puente.mapa.puestos[self.puesto_de[veh]].lat, self.puente.mapa.puestos[self.puesto_de[veh]].lon
                self.coords_invalidas += 1
            self.puesto_ll[veh] = (lat, lon)
            self._ultima_muestra[veh] = t
            self.llegadas += 1
            if self.puente is not None:
                sesion_id = self.puente.iniciar(f"sim_{veh}", self.puesto_de[veh], t)
                if sesion_id is not None:
                    self.sesion_de[veh] = sesion_id

    def _auto_fuera(self, veh: str, t: float) -> None:
        """El auto salió de la red sin que la app detectara la salida."""
        if veh in self.sin_senal or veh in self.apagado_desde:
            # Sin teléfono el sistema no sabe que se fue: la sesión espera al tope de tiempo.
            self.esperando_tope[veh] = self.t_inicio[veh] + self.tiempo_maximo_s
        elif self.puente is not None and veh in self.sesion_de:
            self.puente.cerrar(self.sesion_de.pop(veh), t, motivo=MotivoCierre.manual)
        self._olvidar(veh)

    def _cerrar_por_tope(self, t: float) -> None:
        """Cierra con `timeout_sin_senal` las sesiones sin señal que llegaron a `tiempo_maximo_min`."""
        for veh in list(self.maquinas) + list(self.esperando_tope):
            limite = self.esperando_tope.get(veh, self.t_inicio.get(veh, t) + self.tiempo_maximo_s)
            if veh not in self.sin_senal and veh not in self.esperando_tope:
                continue
            if t < limite:
                continue
            self.cierres_timeout += 1
            if self.puente is not None and veh in self.sesion_de:
                self.puente.cerrar(self.sesion_de.pop(veh), limite, motivo=MotivoCierre.timeout_sin_senal)
            self.esperando_tope.pop(veh, None)
            if veh in self.maquinas:
                self._olvidar(veh)

    def _revisar_senal(self, veh: str, t: float) -> None:
        """Marca `sin_senal` tras `t_sin_senal_s` sin muestras; la desmarca si vuelven."""
        sin_datos = t - self._ultima_muestra.get(veh, t)
        if sin_datos >= self.t_sin_senal_s and veh not in self.sin_senal:
            self.sin_senal[veh] = t
            self.marcadas_sin_senal += 1
        elif sin_datos < self.t_sin_senal_s and veh in self.sin_senal:
            del self.sin_senal[veh]

    def _olvidar(self, veh: str) -> None:
        self.maquinas.pop(veh, None)
        self.puesto_ll.pop(veh, None)
        self.sin_senal.pop(veh, None)
        self.apagado_desde.pop(veh, None)
        self.clasificador.olvidar(f"sim_{veh}")

    def _muestrear(self, ctrl, veh: str, t: float) -> None:
        """Una muestra del teléfono: el peatón si camina, el auto si está dentro."""
        usuario = f"sim_{veh}"
        if veh in self.apagado_desde:
            return
        if veh in self.apagados and self.maquinas[veh].estado == "A_PIE":
            self.apagado_desde[veh] = t  # teléfono apagado: deja de emitir para siempre
            self.apagados_efectivos += 1
            return
        if not self.gps.toca_muestra(usuario, t):
            return
        datos = ctrl.vehiculos[veh]
        ped = f"ped_{veh}"
        tc = ctrl.traci.constants
        if ped in ctrl.personas and ctrl.traci.person.getStage(ped).description != EN_AUTO:
            x, y = ctrl.personas[ped][tc.VAR_POSITION]
            modo = modo_real_persona(ctrl.traci.person.getStage(ped).type)
        else:
            x, y = datos[tc.VAR_POSITION]
            modo = modo_real_vehiculo(ctrl.estacionado(datos))
        fila = self.gps.observar(usuario, t, x, y, modo, ctrl.a_geo)
        if fila is not None and not _finitas(fila["lat"], fila["lon"]):
            self.coords_invalidas += 1
            return
        if fila is not None:
            self._ultima_fila[usuario] = fila
            self._ultima_muestra[veh] = t
            self.clasificador.observar(usuario, fila)

    def _procesar_ventana(self, ctrl, veh: str, t: float, resultado: dict) -> None:
        usuario = f"sim_{veh}"
        maquina = self.maquinas[veh]
        fila = self._ultima_fila[usuario]
        puesto = self.puesto_ll[veh]
        distancia = haversine_m(fila["lat"], fila["lon"], puesto[0], puesto[1])
        self.fuentes[resultado["fuente"]] += 1
        self.ultimo_modo[usuario] = resultado
        retenidas_antes = maquina.retenidas
        transiciones = maquina.actualizar(resultado["modo"], distancia, t, resultado.get("cobertura", 1.0),
                                          resultado["fuente"], resultado["confianza"])
        retenida = maquina.retenidas > retenidas_antes
        self.ventanas_retenidas += retenida
        self._escritores["ventanas"].writerow([
            round(t, 1), usuario, maquina.estado, resultado["modo"], round(resultado["confianza"], 3),
            resultado["fuente"], round(distancia, 1), fila["modo_real"],
            round(resultado.get("cobertura", 1.0), 2), int(retenida),
        ])
        for trans in transiciones:
            self._escritores["transiciones"].writerow(list(trans))
            if trans.hacia == "CERRADA":
                self._cerrar(ctrl, veh, trans, distancia, resultado)
            elif self.puente is not None and veh in self.sesion_de:
                self.puente.transicion(self.sesion_de[veh], trans.hacia, trans.t_sim)
        if maquina.estado == "CERRADA":
            self._olvidar(veh)

    def _cerrar(self, ctrl, veh: str, trans: Transicion, distancia: float, resultado: dict) -> None:
        """Al cerrar, comprueba en SUMO si el auto sigue estacionado: eso es una falsa liberación."""
        self.cerradas += 1
        if ctrl.traci.vehicle.isStoppedParking(veh):
            self.falsas_liberaciones += 1
            if datos_pobres(resultado.get("cobertura", 1.0), resultado["fuente"], resultado["confianza"]):
                self.falsas_con_datos_pobres += 1  # con la política activa debe quedar en 0
            self._escritores["falsas"].writerow([trans.t_sim, trans.usuario_id, self.puesto_de[veh],
                                                 round(distancia, 1)])
        if self.puente is not None and veh in self.sesion_de:
            self.puente.cerrar(self.sesion_de.pop(veh), trans.t_sim)

    # ------------------------------------------------------------------ cierre y resumen

    def cerrar(self) -> None:
        """Cierra los CSV (idempotente)."""
        for archivo in self._archivos.values():
            if not archivo.closed:
                archivo.close()

    def resumen(self) -> dict:
        """Cifras de la corrida: sesiones, falsas liberaciones y el clasificador usado."""
        por_100 = round(100 * self.falsas_liberaciones / self.llegadas, 2) if self.llegadas else None
        return {
            "coords_invalidas": self.coords_invalidas,
            "sesiones": self.llegadas,
            "cerradas": self.cerradas,
            "abiertas_al_final": len(self.maquinas) + len(self.esperando_tope),
            "falsas_liberaciones": self.falsas_liberaciones,
            "falsas_por_100_sesiones": por_100,
            "falsas_con_datos_pobres": self.falsas_con_datos_pobres,
            "ventanas_retenidas": self.ventanas_retenidas,
            "telefonos_apagados": len(self.apagados),
            "apagados_efectivos": self.apagados_efectivos,
            "marcadas_sin_senal": self.marcadas_sin_senal,
            "esperando_tope_al_final": len(self.esperando_tope),
            "cierres_timeout_sin_senal": self.cierres_timeout,
            "clasificador": self.clasificador.origen,
            "ventanas_por_fuente": dict(self.fuentes),
        }
