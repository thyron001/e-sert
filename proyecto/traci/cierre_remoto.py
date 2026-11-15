"""Cierre automático de una sesión contra un backend vivo, por HTTP (S4-1).

El backend no decide el cierre: guarda los eventos (`/eventos/ubicacion`, `/eventos/modo`) y
acepta las transiciones que le informa el controlador (contrato §3). Dentro de SUMO eso lo hace
`ControlSesiones` con el núcleo en memoria; `CierreRemoto` es lo mismo para **un** usuario de la
app y por HTTP: cada ventana de 5 s publica la ubicación y el modo, la pasa por `MaquinaSesion`
(los mismos umbrales) y, si hay transición, la informa con el token del simulador. Al llegar a
`SALIENDO` cierra con motivo `deteccion`.

Lo usan las pruebas de punta a punta (`backend/tests/e2e/test_flujo_app.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from .clasificacion import haversine_m
from .estados import MaquinaSesion, Transicion


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class CierreRemoto:
    """Controlador de una sesión `sesion_id` del usuario `usuario_id` contra `cliente` (base `/api/v1`)."""

    cliente: object  # httpx.Client
    usuario_id: str
    sesion_id: str
    puesto_lat: float
    puesto_lon: float
    t0: datetime  # hora de inicio de la sesión (t_sim = 0)
    token: dict = field(default_factory=dict)  # {"X-Sim-Token": ...}
    fuente: str = "rf"
    maquina: Optional[MaquinaSesion] = None
    transiciones: List[Transicion] = field(default_factory=list)
    cierre: Optional[dict] = None

    def __post_init__(self):
        self.maquina = self.maquina or MaquinaSesion(self.usuario_id)

    @property
    def estado(self) -> str:
        return self.maquina.estado

    def ventana(self, t_sim: float, lat: float, lon: float, modo: str, velocidad_mps: float = 1.2,
                confianza: float = 0.9) -> List[Transicion]:
        """Una ventana de 5 s: publica los eventos y aplica la máquina de estados."""
        ts = iso(self.t0 + timedelta(seconds=t_sim))
        r = self.cliente.post("/eventos/ubicacion", json={
            "usuario_id": self.usuario_id, "origen": "app", "ts": ts, "t_sim": t_sim,
            "lat": lat, "lon": lon, "velocidad_mps": velocidad_mps, "precision_m": 5})
        assert r.status_code == 202, r.text
        r = self.cliente.post("/eventos/modo", json={
            "usuario_id": self.usuario_id, "ts": ts, "t_sim": t_sim, "modo": modo,
            "confianza": confianza, "fuente": self.fuente})
        assert r.status_code == 202, r.text

        distancia = haversine_m(lat, lon, self.puesto_lat, self.puesto_lon)
        nuevas = self.maquina.actualizar(modo, distancia, t_sim, fuente=self.fuente, confianza=confianza)
        for tr in nuevas:
            if tr.hacia == "CERRADA":
                r = self.cliente.post(f"/sesiones/{self.sesion_id}/cerrar", headers=self.token,
                                      json={"ts": ts, "t_sim": t_sim, "motivo": "deteccion"})
                assert r.status_code == 200, r.text
                self.cierre = r.json()
            else:
                r = self.cliente.post(f"/sesiones/{self.sesion_id}/transicion", headers=self.token,
                                      json={"estado": tr.hacia, "ts": ts, "t_sim": t_sim})
                assert r.status_code == 200, r.text
        self.transiciones.extend(nuevas)
        return nuevas
