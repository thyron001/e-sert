"""App web (`/app/`, 2026-11-18): usuarios, sesiones prepago y órdenes al controlador.

Cada persona que abre la app es un usuario `app_<uuid>` con $5 de prueba y, cuando busca o
estaciona, un auto propio en SUMO (`sim_web_<id>`). Flujo de una sesión (`SesionWeb.estado`):

    buscar ──► pendiente ──(asignado)──► yendo ──(la IA detecta que estacionó)──► llego
    estacionado (código) ─────────────────────────────────────────────────────► llego
    llego ──(elige 30/60/90/120 min: se debita ya)──► activa ──(«Me voy» o máximo)──► volviendo
    volviendo ──(la IA detecta que volvió a manejar)──► cerrada

- **Tarifa:** $0,25 por bloque de 30 min (`comun/tarifa.json`), prepago, sin devolución.
- **Temporizador en tiempo simulado.** A 10 min del final (`aviso_tiempo_min`) se avisa (`alerta`); al llegar a 0 se
  renueva sola (+30 min, +$0,25) mientras no pase de 120 min. En el máximo, o si el saldo no
  alcanza, se ordena al conductor volver.
- Si el usuario no elige el tiempo en 5 min simulados desde que llegó, se cobran 30 min.
- **La IA:** el estado del auto (`DetalleEspejo.estado`) sale de la máquina de estados del
  controlador, que usa el clasificador de movimiento (RF) sobre el GPS emulado del conductor:
  `ESTACIONADO`/`A_PIE` → llegó; `SALIENDO`/`CERRADA` → se fue (un `REGRESANDO` pasajero no cierra).
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select

from comun import esquemas as e

from ..nucleo import tarifa as tar
from ..nucleo.billetera import Billetera
from ..nucleo.db import BaseDatos, PuestoTabla, SesionWeb
from ..nucleo.errores import ErrorNucleo

C = e.CodigoError
SALDO_INICIAL_USD = 5.0          # usuario anónimo (crear_usuario)
SALDO_PERFIL_USD = 10.0          # cada perfil fijo empieza con $10
# Perfiles de la app (pestaña «Usuario»): el equipo y tres invitados. El id es fijo (uuid5 del
# nombre), así cada perfil conserva su billetera y su historial entre teléfonos y visitas.
PERFILES = ("Tyrone Novillo", "Pablo Calle", "Miguel Bermeo", "Freddy Lopez",
            "Invitado 1", "Invitado 2", "Invitado 3")


def id_perfil(nombre: str) -> str:
    return f"app_{uuid.uuid5(uuid.NAMESPACE_URL, 'e-sert:perfil:' + nombre)}"


NOMBRES = {id_perfil(n): n for n in PERFILES}
OPCIONES_MIN = (30, 60, 90, 120)
ESPERA_ELECCION_S = 300.0       # sin elegir tiempo en 5 min simulados → 30 min
SIM_VIVA_S = 10.0               # sin pasos en 10 s reales, la simulación está detenida
ABIERTAS = ("pendiente", "yendo", "llego", "activa", "volviendo")
LLEGADA = {"ESTACIONADO", "A_PIE"}
# Solo cuando el auto ya arrancó. `REGRESANDO` no basta: la máquina de estados lo marca a veces un
# momento (el conductor quieto cerca del auto) y vuelve a `A_PIE` cuando el RF ve que sigue a pie.
SALIDA = {"SALIENDO", "CERRADA"}
ESPERA_SIN_AUTO_S = 30.0        # el auto ya no aparece en la simulación: se cierra la sesión
ESPERA_ASIGNACION_S = 30.0      # sin respuesta del controlador a una orden: error


def codigos_de(ids: List[str]) -> Dict[str, str]:
    """Código corto de cada puesto ("001"…): el número pintado en la calle. Orden por id."""
    return {pid: f"{i + 1:03d}" for i, pid in enumerate(sorted(ids))}


@dataclass
class Auto:
    """Lo último que el controlador informó del auto de un usuario."""

    t_sim: float
    lat: float
    lon: float
    estado: Optional[str]
    modo: Optional[str]
    ruta: List[Tuple[float, float]]
    visto_wall: float


class ServicioWeb:
    def __init__(self, bd: BaseDatos, billetera: Billetera, reloj=time.monotonic):
        self.bd = bd
        self.billetera = billetera
        self.reloj = reloj
        self._candado = threading.RLock()
        with bd.transaccion() as s:
            filas = s.execute(select(PuestoTabla.id, PuestoTabla.lat, PuestoTabla.lon, PuestoTabla.calle,
                                     PuestoTabla.capacidad)).all()
        self.puestos = {f.id: f for f in filas}
        self.codigos = codigos_de(list(self.puestos))
        self.por_codigo = {c: pid for pid, c in self.codigos.items()}
        self.ocupacion_real: Dict[str, int] = {}
        self.autos: Dict[str, Auto] = {}
        self._ordenes: List[dict] = []
        self.t_sim: Optional[float] = None
        self._ultimo_paso_wall: Optional[float] = None
        self._creadas_wall: Dict[str, float] = {}

    # ------------------------------------------------------------------ simulación

    def sim_activa(self) -> bool:
        return self._ultimo_paso_wall is not None and self.reloj() - self._ultimo_paso_wall < SIM_VIVA_S

    def seguidos(self) -> List[str]:
        """Autos web con sesión abierta: el controlador manda su detalle de espejo."""
        with self.bd.transaccion() as s:
            return sorted(s.scalars(select(SesionWeb.veh_id).where(SesionWeb.estado.in_(ABIERTAS))).all())

    def tomar_ordenes(self) -> List[dict]:
        with self._candado:
            salida, self._ordenes = self._ordenes, []
        return salida

    def _ordenar(self, **orden) -> None:
        with self._candado:
            self._ordenes.append({k: v for k, v in orden.items() if v is not None})

    def on_paso(self, paso: e.PasoSimulacion) -> None:
        """Cada paso del controlador: eventos, posición de los autos web, IA y temporizadores."""
        ahora = self.reloj()
        with self._candado:
            reinicio = self.t_sim is not None and paso.t_sim < self.t_sim - 1
            self.t_sim = paso.t_sim
            self._ultimo_paso_wall = ahora
            self.ocupacion_real = {p.puesto_id: p.ocupados for p in paso.verdad.puestos}
            detalle = paso.espejo.detalle if paso.espejo is not None else {}
            for veh, det in detalle.items():
                if veh.startswith("sim_web_"):
                    self.autos[veh] = Auto(det.t_sim, det.lat, det.lon, det.estado.value if det.estado else None,
                                           det.modo.value if det.modo else None,
                                           [(float(c[0]), float(c[1])) for c in det.ruta], ahora)
        if reinicio:
            self._cerrar_todas("simulacion_reiniciada", "La simulación se reinició.")
        eventos = {ev.veh_id: ev for ev in (paso.web or [])}
        with self.bd.transaccion() as s:
            for ses in s.scalars(select(SesionWeb).where(SesionWeb.estado.in_(ABIERTAS))).all():
                self._avanzar(s, ses, paso.t_sim, eventos.get(ses.veh_id), ahora)

    def _avanzar(self, s, ses: SesionWeb, t: float, ev: Optional[e.EventoWeb], ahora: float) -> None:
        auto = self.autos.get(ses.veh_id)
        if ev is not None:
            if ev.tipo == "asignado":
                ses.puesto_id = ev.puesto_id
                if ses.estado == "pendiente":
                    ses.estado = "llego" if ses.modo == "estacionado" else "yendo"
                    if ses.estado == "llego":
                        ses.t_llegada = t
            else:
                textos = {"sin_puesto": "No hay puestos libres cerca en este momento.",
                          "puesto_lleno": "Ese puesto ya no tiene plazas libres."}
                self._cerrar(ses, t, ev.tipo, textos.get(ev.tipo, ev.detalle or "No se pudo crear el auto."))
                return
        if ses.estado == "pendiente" and ahora - self._creadas_wall.get(ses.id, ahora) > ESPERA_ASIGNACION_S:
            self._cerrar(ses, t, "sin_respuesta", "La simulación no respondió. Prueba otra vez.")
            return
        estado_auto = auto.estado if auto else None
        if ses.estado == "yendo" and estado_auto in LLEGADA:
            ses.estado, ses.t_llegada = "llego", t
        if ses.estado == "llego" and ses.t_llegada is not None and t - ses.t_llegada >= ESPERA_ELECCION_S:
            try:
                self._pagar(s, ses, 30, t)
                ses.mensaje = "No elegiste el tiempo: se cobraron 30 min."
            except ErrorNucleo:
                self._volver(ses, t, "saldo", "No tienes saldo para pagar el puesto.")
        if ses.estado == "activa" and ses.pagado_hasta is not None:
            if t >= ses.pagado_hasta:
                if ses.pagado_min >= tar.tarifa_vigente().tiempo_maximo_min:
                    self._volver(ses, t, "tiempo_maximo", "Llegaste al tiempo máximo de 120 min: retira el vehículo.")
                else:
                    try:
                        self._pagar(s, ses, 30, t, renovacion=True)
                        ses.mensaje = "Se renovó tu tiempo: +30 min (−$0,25)."
                    except ErrorNucleo:
                        self._volver(ses, t, "saldo", "Tu saldo no alcanza para otra media hora.")
        if ses.estado in ("activa", "volviendo", "llego") and estado_auto in SALIDA:
            self._cerrar(ses, t, ses.motivo or "salida", "Saliste del puesto. ¡Buen viaje!")
            return
        if ses.estado != "pendiente" and auto is not None and ahora - auto.visto_wall > ESPERA_SIN_AUTO_S:
            self._cerrar(ses, t, ses.motivo or "salida", "Tu auto ya no está en la simulación.")

    # ------------------------------------------------------------------ usuarios

    def crear_usuario(self) -> Tuple[str, float]:
        usuario = f"app_{uuid.uuid4()}"
        self.billetera.recargar(usuario, SALDO_INICIAL_USD, referencia_payphone="prueba_web")
        return usuario, SALDO_INICIAL_USD

    def perfiles(self) -> List[dict]:
        """Los perfiles fijos con su saldo; la primera vez reciben sus $10 iniciales."""
        salida = []
        for nombre in PERFILES:
            usuario = id_perfil(nombre)
            if not self.billetera.movimientos(usuario):
                self.billetera.recargar(usuario, SALDO_PERFIL_USD, referencia_payphone="saldo_inicial")
            salida.append({"usuario_id": usuario, "nombre": nombre,
                           "saldo": self.billetera.estado(usuario)["saldo"]})
        return salida

    def historial(self, usuario: str) -> List[dict]:
        """Sesiones terminadas del usuario, la más reciente primero."""
        self._exigir_usuario(usuario)
        with self.bd.transaccion() as s:
            filas = s.scalars(select(SesionWeb).where(SesionWeb.usuario_id == usuario, SesionWeb.estado == "cerrada")
                              .order_by(SesionWeb.creada.desc())).all()
            return [{"id": f.id, "modo": f.modo, "puesto_id": f.puesto_id,
                     "codigo": self.codigos.get(f.puesto_id) if f.puesto_id else None,
                     "calle": self.puestos[f.puesto_id].calle if f.puesto_id in self.puestos else None,
                     "fecha": f.creada.isoformat().replace("+00:00", "Z") if f.creada else None,
                     "pagado_min": f.pagado_min, "debitado": tar.usd(f.debitado),
                     "motivo": f.motivo, "mensaje": f.mensaje} for f in filas]

    def activos(self) -> List[dict]:
        """Autos de la app en la simulación, con el nombre de su usuario (etiquetas del visor)."""
        with self.bd.transaccion() as s:
            filas = s.scalars(select(SesionWeb).where(SesionWeb.estado.in_(ABIERTAS))).all()
            return [{"veh_id": f.veh_id, "usuario_id": f.usuario_id,
                     "nombre": NOMBRES.get(f.usuario_id, "Invitado"), "estado": f.estado} for f in filas]

    def _exigir_usuario(self, usuario: str) -> None:
        if not usuario.startswith("app_"):
            raise ErrorNucleo(C.VALIDACION, "Usuario inválido.")

    def _abierta(self, s, usuario: str) -> Optional[SesionWeb]:
        return s.scalar(select(SesionWeb).where(SesionWeb.usuario_id == usuario, SesionWeb.estado.in_(ABIERTAS)))

    def _exigir_sim(self) -> None:
        if not self.sim_activa():
            raise ErrorNucleo(C.DEMO_NO_DISPONIBLE, "La simulación está detenida. Pídela en el visor (Iniciar).")

    # ------------------------------------------------------------------ acciones del usuario

    def buscar(self, usuario: str, lat: float, lon: float) -> dict:
        self._exigir_usuario(usuario)
        self._exigir_sim()
        self._exigir_saldo(usuario, 30)
        with self.bd.transaccion() as s:
            if self._abierta(s, usuario) is not None:
                raise ErrorNucleo(C.SESION_ACTIVA, "Ya tienes una sesión en curso.")
            ses = self._nueva(s, usuario, "buscar", lat, lon, None)
        self._ordenar(tipo="buscar", veh_id=ses.veh_id, lat=lat, lon=lon)
        return self.estado(usuario)

    def estacionado(self, usuario: str, codigo: str) -> dict:
        self._exigir_usuario(usuario)
        self._exigir_sim()
        codigo = codigo.strip().zfill(3)
        pid = self.por_codigo.get(codigo)
        if pid is None:
            raise ErrorNucleo(C.PUESTO_NO_EXISTE, f"No existe el puesto con código {codigo}.")
        p = self.puestos[pid]
        if self.ocupacion_real.get(pid, 0) >= p.capacidad:
            raise ErrorNucleo(C.PUESTO_LLENO, f"El puesto {codigo} no tiene plazas libres.")
        self._exigir_saldo(usuario, 30)
        with self.bd.transaccion() as s:
            if self._abierta(s, usuario) is not None:
                raise ErrorNucleo(C.SESION_ACTIVA, "Ya tienes una sesión en curso.")
            ses = self._nueva(s, usuario, "estacionado", p.lat, p.lon, pid)
        self._ordenar(tipo="estacionado", veh_id=ses.veh_id, puesto_id=pid)
        return self.estado(usuario)

    def elegir_tiempo(self, usuario: str, minutos: int) -> dict:
        self._exigir_usuario(usuario)
        if minutos not in OPCIONES_MIN:
            raise ErrorNucleo(C.VALIDACION, "Elige 30, 60, 90 o 120 minutos.")
        with self.bd.transaccion() as s:
            ses = self._abierta(s, usuario)
            if ses is None or ses.estado != "llego":
                raise ErrorNucleo(C.TRANSICION_INVALIDA, "Todavía no estás estacionado.")
            self._pagar(s, ses, minutos, self.t_sim or 0.0)
        return self.estado(usuario)

    def extender(self, usuario: str, minutos: int = 30) -> dict:
        self._exigir_usuario(usuario)
        if minutos <= 0 or minutos % 30:
            raise ErrorNucleo(C.VALIDACION, "Se extiende en bloques de 30 minutos.")
        with self.bd.transaccion() as s:
            ses = self._abierta(s, usuario)
            if ses is None or ses.estado != "activa":
                raise ErrorNucleo(C.TRANSICION_INVALIDA, "No tienes un tiempo activo para extender.")
            if ses.pagado_min + minutos > tar.tarifa_vigente().tiempo_maximo_min:
                raise ErrorNucleo(C.VALIDACION, "El máximo es 120 minutos en el mismo puesto.")
            self._pagar(s, ses, minutos, self.t_sim or 0.0, renovacion=True)
            ses.mensaje = f"Extendiste tu tiempo: +{minutos} min."
        return self.estado(usuario)

    def me_voy(self, usuario: str) -> dict:
        self._exigir_usuario(usuario)
        with self.bd.transaccion() as s:
            ses = self._abierta(s, usuario)
            if ses is None:
                raise ErrorNucleo(C.SESION_NO_EXISTE, "No tienes una sesión en curso.")
            if ses.estado in ("pendiente", "yendo"):
                raise ErrorNucleo(C.TRANSICION_INVALIDA, "Todavía no llegas al puesto.")
            if ses.estado != "volviendo":
                self._volver(ses, self.t_sim or 0.0, "me_voy", "Vas de vuelta al auto…")
        return self.estado(usuario)

    # ------------------------------------------------------------------ cobro y estados

    def _exigir_saldo(self, usuario: str, minutos: int) -> None:
        necesario = tar.centavos(tar.costo(minutos))
        disponible = self.billetera.estado_centavos(usuario)["disponible"]
        if disponible < necesario:
            raise ErrorNucleo(C.SALDO_INSUFICIENTE, f"Necesitas al menos ${tar.usd(necesario):.2f} de saldo.")

    def _pagar(self, s, ses: SesionWeb, minutos: int, t: float, renovacion: bool = False) -> None:
        centavos = tar.centavos(tar.costo(minutos))
        self.billetera.cobrar(ses.usuario_id, centavos, f"web:{ses.id}", s=s)
        ses.debitado += centavos
        ses.pagado_min += minutos
        if not renovacion or ses.pagado_hasta is None:
            ses.t_inicio = t
            ses.pagado_hasta = t + minutos * 60
        else:
            ses.pagado_hasta += minutos * 60
        ses.estado = "activa"

    def _volver(self, ses: SesionWeb, t: float, motivo: str, mensaje: str) -> None:
        ses.estado, ses.motivo, ses.mensaje = "volviendo", motivo, mensaje
        self._ordenar(tipo="volver", veh_id=ses.veh_id)

    @staticmethod
    def _cerrar(ses: SesionWeb, t: float, motivo: str, mensaje: str) -> None:
        ses.estado, ses.t_fin, ses.motivo, ses.mensaje = "cerrada", t, motivo, mensaje

    def _cerrar_todas(self, motivo: str, mensaje: str) -> None:
        with self.bd.transaccion() as s:
            for ses in s.scalars(select(SesionWeb).where(SesionWeb.estado.in_(ABIERTAS))).all():
                self._cerrar(ses, self.t_sim or 0.0, motivo, mensaje)

    def _nueva(self, s, usuario: str, modo: str, lat: float, lon: float, pid: Optional[str]) -> SesionWeb:
        corto = uuid.uuid4().hex[:8]
        ses = SesionWeb(id=f"web_{corto}", usuario_id=usuario, veh_id=f"sim_web_{corto}", modo=modo,
                        estado="pendiente", lat=lat, lon=lon, puesto_id=pid)
        s.add(ses)
        s.flush()
        self._creadas_wall[ses.id] = self.reloj()
        return ses

    # ------------------------------------------------------------------ lectura

    def estado(self, usuario: str) -> dict:
        """Todo lo que la app web dibuja: saldo, sesión, auto, puesto y temporizador."""
        self._exigir_usuario(usuario)
        billetera = self.billetera.estado(usuario)
        with self.bd.transaccion() as s:
            ses = self._abierta(s, usuario) or s.scalar(
                select(SesionWeb).where(SesionWeb.usuario_id == usuario).order_by(SesionWeb.creada.desc()))
            datos = None
            if ses is not None:
                datos = {c: getattr(ses, c) for c in ("id", "veh_id", "modo", "estado", "puesto_id", "pagado_min",
                                                       "pagado_hasta", "t_inicio", "t_llegada", "motivo", "mensaje")}
                datos["debitado"] = tar.usd(ses.debitado)
        respuesta = {"usuario_id": usuario, "nombre": NOMBRES.get(usuario, "Invitado"),
                     "saldo": billetera["saldo"], "t_sim": self.t_sim,
                     "sim_activa": self.sim_activa(), "sesion": None}
        if datos is None:
            return respuesta
        t = self.t_sim or 0.0
        restante = None if datos["pagado_hasta"] is None else max(0.0, datos["pagado_hasta"] - t)
        maximo = tar.tarifa_vigente().tiempo_maximo_min
        aviso = tar.tarifa_vigente().aviso_tiempo_min * 60
        datos["restante_s"] = None if restante is None else round(restante)
        datos["alerta"] = None
        if datos["estado"] == "activa" and restante is not None and restante <= aviso:
            avisar = tar.tarifa_vigente().aviso_tiempo_min
            datos["alerta"] = (f"Faltan {avisar} min y llegarás al máximo de {maximo} min: retira el vehículo."
                               if datos["pagado_min"] >= maximo else
                               f"Faltan {avisar} min: si no te vas, se debitarán $0,25 por otra media hora.")
        datos["puede_extender"] = datos["estado"] == "activa" and datos["pagado_min"] < maximo
        datos["opciones_min"] = list(OPCIONES_MIN)
        datos["eleccion_restante_s"] = (None if datos["estado"] != "llego" or datos["t_llegada"] is None
                                        else max(0, round(ESPERA_ELECCION_S - (t - datos["t_llegada"]))))
        pid = datos["puesto_id"]
        datos["puesto"] = None if pid is None else {
            "puesto_id": pid, "codigo": self.codigos.get(pid), "calle": self.puestos[pid].calle,
            "lat": self.puestos[pid].lat, "lon": self.puestos[pid].lon}
        auto = self.autos.get(datos["veh_id"])
        datos["auto"] = None if auto is None or datos["estado"] == "cerrada" else {
            "lat": auto.lat, "lon": auto.lon, "estado": auto.estado, "modo": auto.modo,
            "ruta": [list(c) for c in auto.ruta]}
        respuesta["sesion"] = datos
        return respuesta

    def lista_puestos(self) -> List[dict]:
        return [{"puesto_id": pid, "codigo": self.codigos[pid], "calle": p.calle, "lat": p.lat, "lon": p.lon,
                 "capacidad": p.capacidad, "ocupados": min(p.capacidad, self.ocupacion_real.get(pid, 0))}
                for pid, p in sorted(self.puestos.items())]
