"""Puente entre el controlador TraCI y el núcleo del backend (S2-3).

El controlador importa `backend/nucleo/` **directamente** (sin HTTP): en los experimentos los
autos simulados nunca llaman a Payphone ni al backend vivo. `PuenteNucleo` crea una `Billetera`,
un `ServicioSesiones` y un `MapaOcupacion` sobre `sqlite:///:memory:`, carga los puestos y da una
recarga inicial `U(5, 20)` USD a cada usuario simulado `sim_<veh>`.

`Publicador` es opcional (`--publicar URL`): empuja cada segundo simulado el estado del mundo a
`POST /api/v1/interno/snapshot` en un hilo aparte, con una cola de tamaño 1. Si la red se atrasa,
se descarta el snapshot viejo: **la simulación nunca espera a la red**.
"""

from __future__ import annotations

import csv
import json
import queue
import random
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List, Optional

CODIGO = Path(__file__).resolve().parents[1]  # semanas/S3/Freddy/codigo
if str(CODIGO) not in sys.path:
    sys.path.insert(0, str(CODIGO))

import httpx  # noqa: E402

from backend.nucleo import tarifa as tar  # noqa: E402
from backend.nucleo.billetera import Billetera  # noqa: E402
from backend.nucleo.db import BaseDatos, distancia_m, leer_puestos_csv  # noqa: E402
from backend.nucleo.errores import ErrorNucleo  # noqa: E402
from backend.nucleo.ocupacion import MapaOcupacion  # noqa: E402
from backend.nucleo.sesiones import ServicioSesiones  # noqa: E402
from comun.esquemas import EstadoSesion, MotivoCierre, TipoMovimiento as TM  # noqa: E402

RECARGA_USD = (5.0, 20.0)
CABECERAS_SESIONES = ["sesion_id", "usuario_id", "puesto_id", "t_inicio", "t_fin", "minutos_reales",
                      "minutos_cobrados", "debitado", "motivo"]


class PuenteNucleo:
    """Billetera, sesiones y mapa de ocupación del núcleo, en memoria, para una corrida."""

    def __init__(self, puestos_csv: Path, semilla: int, recarga_usd=RECARGA_USD):
        self.bd = BaseDatos("sqlite:///:memory:")
        self.bd.cargar_puestos(leer_puestos_csv(puestos_csv))
        self.billetera = Billetera(self.bd)
        self.mapa = MapaOcupacion.desde_bd(self.bd)
        self.servicio = ServicioSesiones(self.bd, self.billetera, self.mapa)
        self._rng = random.Random(semilla)
        self._recarga = recarga_usd
        self.recargas: Dict[str, float] = {}
        self.abiertas: Dict[str, dict] = {}
        self.cerradas: List[dict] = []
        self.no_abiertas: Counter = Counter()  # motivo → cuántas llegadas quedaron sin sesión
        # Oyentes de cierre (S3-1): `KPIsSistema` recibe la fila de cada sesión cerrada.
        self.al_cerrar: List[Callable[[dict], None]] = []
        self._placas = 0

    # ------------------------------------------------------------------ usuarios y sesiones

    def registrar(self, usuario: str) -> None:
        """Recarga inicial `U(5, 20)` USD (una sola vez por usuario)."""
        if usuario in self.recargas:
            return
        monto = round(self._rng.uniform(*self._recarga), 2)
        self.billetera.recargar(usuario, monto)
        self.recargas[usuario] = monto

    def iniciar(self, usuario: str, puesto: str, t_sim: float) -> Optional[str]:
        """Llegada confirmada: abre la sesión. Devuelve su id, o None si el núcleo la rechaza."""
        self._placas += 1
        placa = f"SIM-{self._placas:04d}"  # el formato de placa exige 3-4 dígitos
        try:
            creada = self.servicio.iniciar(usuario, placa, puesto, t_sim=t_sim)
        except ErrorNucleo as err:
            self.no_abiertas[err.codigo.value] += 1
            return None
        self.abiertas[creada.sesion_id] = {"usuario_id": usuario, "puesto_id": puesto, "t_inicio": t_sim}
        return creada.sesion_id

    def transicion(self, sesion_id: str, hacia: str, t_sim: float) -> None:
        """Transición de la máquina de estados (§3). El núcleo solo acepta las legales."""
        try:
            self.servicio.transicion(sesion_id, EstadoSesion(hacia), t_sim=t_sim)
        except ErrorNucleo as err:
            self.no_abiertas[f"transicion:{err.codigo.value}"] += 1

    def cerrar(self, sesion_id: str, t_sim: float, motivo: MotivoCierre = MotivoCierre.deteccion) -> dict:
        """Salida: debita el tiempo real y libera la retención (`deteccion`, o `manual` si el auto se fue sin detección)."""
        info = self.abiertas.pop(sesion_id)
        r = self.servicio.cerrar(sesion_id, motivo=motivo, t_sim=t_sim)
        fila = {"sesion_id": sesion_id, "usuario_id": info["usuario_id"], "puesto_id": info["puesto_id"],
                "t_inicio": info["t_inicio"], "t_fin": t_sim, "minutos_reales": r.minutos_reales,
                "minutos_cobrados": r.minutos_cobrados, "debitado": r.debitado,
                "motivo": motivo.value}
        self.cerradas.append(fila)
        for oyente in self.al_cerrar:
            oyente(fila)
        return fila

    # ------------------------------------------------------------------ salidas

    def libro(self) -> Dict[str, dict]:
        """Por usuario, en centavos: recargas, débitos, retención neta y saldo calculado del libro."""
        salida = {}
        for usuario in self.recargas:
            t = self.billetera.sumas(usuario)
            saldo = t[TM.recarga] - t[TM.debito]
            retenido = t[TM.retencion] - t[TM.liberacion]
            salida[usuario] = {
                "recarga_centavos": t[TM.recarga],
                "debito_centavos": t[TM.debito],
                "retencion_neta_centavos": retenido,
                "saldo_centavos": saldo,
                "saldo_usd": tar.usd(saldo),
            }
        return salida

    def guardar_sesiones(self, ruta: Path) -> None:
        with ruta.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CABECERAS_SESIONES)
            w.writeheader()
            for fila in self.cerradas:
                w.writerow(fila)

    def guardar_libro(self, ruta: Path) -> None:
        ruta.write_text(json.dumps(self.libro(), indent=2, ensure_ascii=False), encoding="utf-8")

    def resumen(self) -> dict:
        return {
            "usuarios_con_recarga": len(self.recargas),
            "sesiones_cerradas": len(self.cerradas),
            "sesiones_abiertas_al_final": len(self.abiertas),
            "sin_sesion": dict(self.no_abiertas),
        }


class Publicador:
    """Envía snapshots a `POST /api/v1/interno/snapshot` en un hilo aparte (cola de tamaño 1).

    Si el envío no termina, el snapshot pendiente se reemplaza por el más nuevo: el hilo de la
    simulación nunca espera a la red. Los fallos se reintentan con *backoff* y no paran la corrida.
    """

    RUTA = "/api/v1/interno/snapshot"

    def __init__(self, url: str, token: Optional[str] = None, timeout_s: float = 2.0,
                 reintentos: int = 3, backoff_s: float = 0.5, ruta: Optional[str] = None):
        self.ruta = ruta or self.RUTA
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._cliente = httpx.Client(base_url=url, headers=headers, timeout=timeout_s)
        self._cola: "queue.Queue[dict]" = queue.Queue(maxsize=1)
        self._reintentos = reintentos
        self._backoff_s = backoff_s
        self.enviados = 0
        self.descartados = 0
        self.fallidos = 0
        self._hilo = threading.Thread(target=self._bucle, name="publicador", daemon=True)
        self._hilo.start()

    def publicar(self, cuerpo: dict) -> None:
        """No bloquea: si hay un snapshot pendiente, lo reemplaza por este."""
        try:
            self._cola.get_nowait()
            self.descartados += 1
        except queue.Empty:
            pass
        self._cola.put_nowait(cuerpo)

    def _bucle(self) -> None:
        while True:
            cuerpo = self._cola.get()
            for intento in range(self._reintentos):
                try:
                    r = self._cliente.post(self.ruta, json=cuerpo)
                    if r.status_code < 300:
                        self.enviados += 1
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(self._backoff_s * (2 ** intento))
            else:
                self.fallidos += 1

    def cerrar(self, espera_s: float = 3.0) -> None:
        """Espera (hasta `espera_s`) a que se vacíe la cola y cierra la conexión."""
        limite = time.monotonic() + espera_s
        while not self._cola.empty() and time.monotonic() < limite:
            time.sleep(0.05)
        self._cliente.close()

    def resumen(self) -> dict:
        return {"enviados": self.enviados, "descartados": self.descartados, "fallidos": self.fallidos}
