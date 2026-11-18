"""El backend (`api`) habla con el servicio `sim` (`servicio.py`) por la red interna de Dokploy.

Tiene la misma interfaz que `GestorSimulacion` (`estado`, `iniciar`, `detener`, `corriendo`), así
que las rutas `/api/v1/demo/*` no cambian: con `ESERT_URL_SIM` usan este cliente y sin ella, el
gestor local (desarrollo y pruebas).
"""

from __future__ import annotations

from typing import Optional

import httpx

from .gestor import Escenario, Estado, estado_desde_dict

TIEMPO_S = 30.0   # detener puede esperar ~15 s a que el controlador cierre SUMO


class ClienteSimulacion:
    def __init__(self, url: str, token: Optional[str], http: Optional[httpx.Client] = None):
        self.url = url.rstrip("/")
        self.http = http or httpx.Client(base_url=self.url, timeout=TIEMPO_S)
        self.cabeceras = {"Authorization": f"Bearer {token}"} if token else {}

    def _pedir(self, metodo: str, ruta: str, **kw) -> Estado:
        try:
            r = self.http.request(metodo, ruta, headers=self.cabeceras, **kw)
        except httpx.HTTPError as exc:
            raise LookupError(f"el servicio de simulación no responde ({type(exc).__name__})") from exc
        if r.status_code == 409:
            raise RuntimeError(r.json().get("detail", "ya hay una simulación en curso"))
        if r.status_code >= 400:
            detalle = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else r.text
            raise LookupError(f"servicio de simulación: {r.status_code} {detalle}")
        return estado_desde_dict(r.json())

    def estado(self) -> Estado:
        try:
            return self._pedir("GET", "/estado")
        except LookupError as exc:
            return Estado(disponible=False, motivo=str(exc), corriendo=False, fase="inactiva")

    def iniciar(self, esc: Escenario) -> Estado:
        return self._pedir("POST", "/iniciar", json={"penetracion": esc.penetracion, "semilla": esc.semilla,
                                                      "ritmo": esc.ritmo, "hasta_s": esc.hasta_s,
                                                      "clasificador": esc.clasificador})

    def detener(self) -> Estado:
        return self._pedir("POST", "/detener")

    def corriendo(self) -> bool:
        return self.estado().corriendo
