"""Ruta restante de un vehículo como polilínea `[[lat, lon], ...]` para el modo espejo (S3-3).

`RutaGeo.ruta(ctrl, veh)`:

1. `traci.vehicle.getRoute(veh)` desde `getRouteIndex(veh)` (lo que falta recorrer); si se pasa
   `hasta_edge` (la arista del puesto), se corta ahí: la pantalla muestra el camino al puesto,
   no la salida posterior;
2. la forma de cada *edge* con `sumolib` (`net.getEdge(e).getShape()`), en coordenadas de la red;
3. `net.convertXY2LonLat` → `[lat, lon]`;
4. Douglas-Peucker hasta quedar en `max_puntos` (200) como máximo.

El resultado se guarda en caché por `(tupla_ruta, índice, hasta_edge)`: mientras el auto no
cambie de arista ni de ruta, no se recalcula. Las funciones `douglas_peucker` y `simplificar`
son puras (sin SUMO) y se prueban aparte.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from typing import List, Optional, Sequence, Tuple

Punto = Tuple[float, float]

MAX_PUNTOS = 200
TAM_CACHE = 512


def _dist_segmento(p: Punto, a: Punto, b: Punto) -> float:
    """Distancia del punto `p` al segmento `ab` (plano)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    u = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - (a[0] + u * dx), p[1] - (a[1] + u * dy))


def douglas_peucker(puntos: Sequence[Punto], tolerancia: float) -> List[Punto]:
    """Douglas-Peucker iterativo (sin recursión): conserva los extremos y los vértices que se
    apartan más de `tolerancia` de la recta que los une."""
    n = len(puntos)
    if n <= 2:
        return list(puntos)
    conservar = [False] * n
    conservar[0] = conservar[-1] = True
    pila = [(0, n - 1)]
    while pila:
        i, j = pila.pop()
        peor, k_peor = -1.0, -1
        medio = (i + j) / 2
        for k in range(i + 1, j):
            d = _dist_segmento(puntos[k], puntos[i], puntos[j])
            # con empates se parte por el más cercano al medio: divisiones parejas, O(n log n)
            if d > peor or (d == peor and abs(k - medio) < abs(k_peor - medio)):
                peor, k_peor = d, k
        if k_peor >= 0 and peor > tolerancia:
            conservar[k_peor] = True
            pila.append((i, k_peor))
            pila.append((k_peor, j))
    return [p for p, c in zip(puntos, conservar) if c]


def simplificar(puntos: Sequence[Punto], max_puntos: int = MAX_PUNTOS, tolerancia: float = 1.0) -> List[Punto]:
    """Quita puntos repetidos y aplica Douglas-Peucker (en metros de la red), duplicando la
    tolerancia hasta que queden `max_puntos` como máximo."""
    limpios: List[Punto] = []
    for p in puntos:
        if not limpios or p != limpios[-1]:
            limpios.append(p)
    salida = douglas_peucker(limpios, tolerancia)
    while len(salida) > max_puntos:
        tolerancia *= 2
        salida = douglas_peucker(limpios, tolerancia)
    return salida


class RutaGeo:
    """Ruta restante en lat/lon, con caché. `net` es la red de `sumolib.net.readNet`."""

    def __init__(self, net, max_puntos: int = MAX_PUNTOS, tolerancia_m: float = 1.0,
                 tam_cache: int = TAM_CACHE):
        self.net = net
        self.max_puntos = max_puntos
        self.tolerancia_m = tolerancia_m
        self.tam_cache = tam_cache
        self._cache: "OrderedDict[tuple, List[List[float]]]" = OrderedDict()
        self.calculadas = 0
        self.aciertos = 0

    def ruta(self, ctrl, veh: str, hasta_edge: Optional[str] = None) -> List[List[float]]:
        """`[[lat, lon], ...]` de lo que le falta recorrer a `veh` (vacía si no hay ruta)."""
        tr = ctrl.traci
        aristas = tuple(tr.vehicle.getRoute(veh))
        indice = max(0, int(tr.vehicle.getRouteIndex(veh)))
        return self.desde_aristas(aristas, indice, hasta_edge)

    def desde_aristas(self, aristas: Sequence[str], indice: int = 0,
                      hasta_edge: Optional[str] = None) -> List[List[float]]:
        clave = (tuple(aristas), indice, hasta_edge)
        if clave in self._cache:
            self.aciertos += 1
            self._cache.move_to_end(clave)
            return self._cache[clave]
        restantes = list(aristas[indice:])
        if hasta_edge is not None and hasta_edge in restantes:
            restantes = restantes[: restantes.index(hasta_edge) + 1]
        xy: List[Punto] = []
        for arista in restantes:
            if arista.startswith(":") or not self.net.hasEdge(arista):
                continue
            xy.extend(self.net.getEdge(arista).getShape())
        salida = []
        for x, y in simplificar(xy, self.max_puntos, self.tolerancia_m):
            lon, lat = self.net.convertXY2LonLat(x, y)
            salida.append([round(lat, 7), round(lon, 7)])
        self.calculadas += 1
        self._cache[clave] = salida
        if len(self._cache) > self.tam_cache:
            self._cache.popitem(last=False)
        return salida
