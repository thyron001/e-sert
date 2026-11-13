"""Bloque interno `espejo` de `POST /interno/snapshot` (S3-3, contrato §7, v1.2).

`EspejoPublicador.bloque(ctrl, t, espejos)` se llama en cada publicación de `PublicadorSnapshots`
(como mucho 1 por segundo simulado) y arma:

- `candidatos`: autos con app en `BUSCANDO` o `GUIADO` (`id`, `destino_nombre`, `estado`, `t_sim`);
- `detalle[veh_id]`, **solo para los vehículos que algún teléfono sigue** (`espejos`, lo que
  devolvió el backend en la respuesta anterior): estado, posición del teléfono del conductor (el
  peatón si se bajó, si no el auto), último modo clasificado, destino, puesto con la distancia que
  falta (`getDrivingDistance`), ruta (`RutaGeo`), sesión con el costo en vivo, billetera, avisos y,
  al cerrar, el recibo.

El recibo se arma al cerrar la sesión en el núcleo (`PuenteNucleo.al_cerrar`) y se repite en cada
detalle mientras el auto sigue en la red: el backend lo envía una sola vez por `sesion_id`.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, Optional, Tuple

from backend.nucleo import tarifa as tar

from .controlador import parametro
from .estados import EN_AUTO
from .guiado import destino_de
from .peatones import texto_traci
from .puente_nucleo import distancia_m

ESTADOS_CANDIDATO = ("BUSCANDO", "GUIADO")
INVALIDO = -1e9  # getDrivingDistance devuelve -2^30 (INVALID_DOUBLE_VALUE) si no hay camino


def estado_vehiculo(veh: str, sesiones, guia, cerrados: Iterable[str] = ()) -> Optional[str]:
    """Estado del contrato (§3) de un auto: el de su sesión, `CERRADA` tras el cobro, o el de la guía."""
    if veh in sesiones.maquinas:
        return sesiones.maquinas[veh].estado
    if veh in cerrados:
        return "CERRADA"
    if guia is not None and veh in guia.estado:
        estado = guia.estado[veh]
        return "BUSCANDO" if estado == "A_CIEGAS" else estado
    return None


def recibo_de(fila: dict) -> dict:
    """Recibo (§5) de una fila de sesión cerrada de `PuenteNucleo`, comparado con la tarjeta SERT."""
    tarjeta = tar.costo_tarjeta_sert(fila["minutos_reales"])
    return {
        "sesion_id": fila["sesion_id"],
        "minutos_reales": round(fila["minutos_reales"], 2),
        "minutos_cobrados": int(fila["minutos_cobrados"]),
        "cobrado_usd": round(fila["debitado"], 2),
        "tarjeta_sert_usd": round(tarjeta, 2),
        "ahorro_usd": round(tarjeta - fila["debitado"], 2),
    }


class EspejoPublicador:
    """Arma el bloque `espejo` a partir del estado de la corrida (sesiones, guía, núcleo y red)."""

    def __init__(self, sesiones, guia, puente, registro, destinos: Dict[str, tuple], a_geo, ruta_geo=None):
        self.sesiones = sesiones
        self.guia = guia
        self.puente = puente
        self.registro = registro  # RegistroBusqueda: con_app por vehículo
        self.destinos = destinos  # nombre → (lat, lon, peso), de destinos.csv
        self.a_geo = a_geo        # (x, y) → (lat, lon)
        self.ruta_geo = ruta_geo  # RutaGeo, o None para no mandar ruta
        self.recibos: Dict[str, dict] = {}  # veh → recibo de su última sesión cerrada
        self._puesto_lugar: Dict[str, Tuple[str, float]] = {}  # puesto → (edge, pos de inicio)
        self.detalles_armados = 0
        self.errores: Dict[str, int] = {}  # tipo de excepción → cuántas (el espejo nunca para la corrida)
        if puente is not None:
            puente.al_cerrar.append(self._al_cerrar)

    # ------------------------------------------------------------------ núcleo

    def _al_cerrar(self, fila: dict) -> None:
        usuario = fila["usuario_id"]
        if usuario.startswith("sim_"):
            self.recibos[usuario[4:]] = recibo_de(fila)

    def estado(self, veh: str) -> Optional[str]:
        return estado_vehiculo(veh, self.sesiones, self.guia, self.recibos)

    # ------------------------------------------------------------------ bloque

    def bloque(self, ctrl, t: float, espejos: Iterable[str] = ()) -> dict:
        """`{"candidatos": [...], "detalle": {veh_id: {...}}}` para el cuerpo del snapshot."""
        t_sim = round(t, 1)
        candidatos = []
        for veh, es_app in self.registro.con_app.items():
            if not es_app or veh not in ctrl.vehiculos:
                continue
            estado = self.estado(veh)
            if estado in ESTADOS_CANDIDATO:
                candidatos.append({"id": f"sim_{veh}", "destino_nombre": self._destino_nombre(ctrl, veh),
                                   "estado": estado, "t_sim": t_sim})
        detalle = {}
        for veh_id in espejos:
            veh = veh_id[4:] if veh_id.startswith("sim_") else veh_id
            if veh not in ctrl.vehiculos:
                continue
            try:
                d = self.detalle(ctrl, veh, t_sim)
            except Exception as err:  # noqa: BLE001 - un dato raro de SUMO no debe tumbar la simulación
                nombre = type(err).__name__
                self.errores[nombre] = self.errores.get(nombre, 0) + 1
                continue
            if d is not None:
                detalle[f"sim_{veh}"] = d
        return {"candidatos": candidatos, "detalle": detalle}

    def detalle(self, ctrl, veh: str, t_sim: float) -> Optional[dict]:
        """Lo que ve la pantalla del conductor de `veh` (campos de `DetalleEspejo`), o None si SUMO
        no da una posición válida en este paso (pasa con el auto recién estacionado)."""
        usuario = f"sim_{veh}"
        estado = self.estado(veh)
        pos = self._posicion_telefono(ctrl, veh)
        if pos is None:
            self.errores["posicion_no_finita"] = self.errores.get("posicion_no_finita", 0) + 1
            return None
        lat, lon = pos
        self.detalles_armados += 1
        ultimo = getattr(self.sesiones, "ultimo_modo", {}).get(usuario)
        destino = self._destino(ctrl, veh)
        pid = (self.guia.puesto.get(veh) if self.guia is not None else None) or self.sesiones.puesto_de.get(veh)
        conocido = pid is not None and self.puente is not None and pid in self.puente.mapa.puestos
        puesto = None
        if conocido and estado != "CERRADA":  # tras el cobro la pantalla ya no guía al puesto
            p = self.puente.mapa.puestos[pid]
            puesto = {"puesto_id": pid, "lat": p.lat, "lon": p.lon,
                      "distancia_m": round(self._distancia(ctrl, veh, pid, estado, lat, lon, p), 1)}
        ruta = []
        if self.ruta_geo is not None and estado in ESTADOS_CANDIDATO:
            hasta = self._lugar_puesto(ctrl, pid)[0] if conocido else None
            ruta = self.ruta_geo.ruta(ctrl, veh, hasta_edge=hasta)
        sesion, billetera, avisos = None, None, []
        if self.puente is not None:
            sid = self.sesiones.sesion_de.get(veh)
            if sid is not None and veh in self.sesiones.t_inicio:
                minutos = max(0.0, (t_sim - self.sesiones.t_inicio[veh]) / 60)
                sesion = {"sesion_id": sid, "minutos": round(minutos, 2),
                          "costo_usd": round(tar.costo_en_curso(minutos), 2),
                          "retenido_usd": tar.usd(self.puente.billetera.retenido_de_sesion(sid))}
                avisos = [a.value for a in self.puente.servicio.avisos(sid, t_sim=t_sim)]
            if usuario in self.puente.recargas:
                est = self.puente.billetera.estado(usuario)
                billetera = {"saldo": est["saldo"], "disponible": est["disponible"]}
                if sid is None:
                    avisos = [a.value for a in self.puente.servicio.avisos_usuario(usuario)]
        return {
            "t_sim": t_sim, "estado": estado, "lat": lat, "lon": lon,
            "modo": ultimo["modo"] if ultimo else None,
            "confianza": round(float(ultimo["confianza"]), 3) if ultimo else None,
            "destino": destino, "puesto": puesto, "ruta": ruta, "sesion": sesion,
            # el recibo de la última sesión cerrada, salvo que el auto ya tenga otra abierta
            "billetera": billetera, "avisos": avisos,
            "recibo": None if veh in self.sesiones.sesion_de else self.recibos.get(veh),
        }

    # ------------------------------------------------------------------ piezas

    def _destino_nombre(self, ctrl, veh: str) -> str:
        destino = destino_de(ctrl, veh, self.destinos)
        if destino is not None:
            return destino[0]
        # sin coordenadas conocidas, al menos el texto del parámetro
        return texto_traci(parametro(ctrl, veh, "destino_nombre") or parametro(ctrl, veh, "destino") or "")

    def _destino(self, ctrl, veh: str) -> Optional[dict]:
        destino = destino_de(ctrl, veh, self.destinos)
        if destino is None:
            return None
        nombre, lat, lon = destino
        return {"nombre": nombre, "lat": lat, "lon": lon}

    def _posicion_telefono(self, ctrl, veh: str) -> Optional[Tuple[float, float]]:
        """El teléfono va con el conductor: el peatón si camina, si no el auto. None si no es finita."""
        tc = ctrl.traci.constants
        ped = f"ped_{veh}"
        candidatas = []
        if ped in ctrl.personas and ctrl.traci.person.getStage(ped).description != EN_AUTO:
            candidatas.append(ctrl.personas[ped][tc.VAR_POSITION])
        candidatas.append(ctrl.vehiculos[veh][tc.VAR_POSITION])
        for x, y in candidatas:
            if not (math.isfinite(x) and math.isfinite(y)) or x <= INVALIDO or y <= INVALIDO:
                continue  # -2^30: posición inválida de SUMO
            lat, lon = self.a_geo(x, y)
            if math.isfinite(lat) and math.isfinite(lon):
                return round(lat, 7), round(lon, 7)
        return None

    def _lugar_puesto(self, ctrl, pid: str) -> Tuple[str, float]:
        if pid not in self._puesto_lugar:
            tr = ctrl.traci
            self._puesto_lugar[pid] = (tr.lane.getEdgeID(tr.parkingarea.getLaneID(pid)),
                                       tr.parkingarea.getStartPos(pid))
        return self._puesto_lugar[pid]

    def _distancia(self, ctrl, veh: str, pid: str, estado: Optional[str], lat: float, lon: float, p) -> float:
        """Conduciendo al puesto: distancia por la red. Estacionado o a pie: en línea recta al puesto."""
        if estado in ESTADOS_CANDIDATO:
            edge, pos = self._lugar_puesto(ctrl, pid)
            d = ctrl.traci.vehicle.getDrivingDistance(veh, edge, pos)
            if d > INVALIDO and math.isfinite(d):
                return max(0.0, d)
        if veh in self.sesiones.puesto_ll:  # el punto donde quedó el auto (no el centro del parkingArea)
            plat, plon = self.sesiones.puesto_ll[veh]
            return distancia_m(lat, lon, plat, plon)
        return distancia_m(lat, lon, p.lat, p.lon)
