"""Lectores en streaming de las salidas XML de SUMO para los KPIs.

Cada lector recorre el XML con lxml.etree.iterparse, libera los nodos ya leídos y devuelve un
pandas.DataFrame. No importan sumolib ni traci, así que corren en la computadora y en el
contenedor van3twin.
"""
from pathlib import Path

import pandas as pd
from lxml import etree


def _iterar(ruta, etiqueta):
    """Itera los elementos `etiqueta` de un XML y los libera al terminar cada uno."""
    for _, el in etree.iterparse(str(ruta), events=("end",), tag=etiqueta, huge_tree=True):
        yield el
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]


def _f(valor, defecto=float("nan")):
    return float(valor) if valor not in (None, "") else defecto


def leer_tripinfo(ruta):
    filas = [(el.get("id"), _f(el.get("depart")), _f(el.get("arrival")),
              _f(el.get("duration")), _f(el.get("routeLength")))
             for el in _iterar(ruta, "tripinfo")]
    return pd.DataFrame(filas, columns=["id", "depart", "arrival", "duration", "routeLength"])


def leer_stops(ruta):
    """Paradas en un parkingArea (stop-output). `ended` = -1 si la parada no terminó."""
    filas = [(el.get("id"), el.get("parkingArea"), _f(el.get("started")), _f(el.get("ended"), -1.0))
             for el in _iterar(ruta, "stopinfo") if el.get("parkingArea")]
    return pd.DataFrame(filas, columns=["id", "parkingArea", "started", "ended"])


def leer_vehroutes(ruta):
    """Una fila por edge de la ruta final de cada vehículo, con su hora de salida (exitTimes)."""
    filas = []
    for el in _iterar(ruta, "vehicle"):
        rutas = el.findall("route") or el.findall("routeDistribution/route")
        if not rutas:
            continue
        final = rutas[-1]
        edges = final.get("edges", "").split()
        # SUMO escribe -1 en los edges que un vehículo sin terminar todavía no ha dejado
        salidas = [float(x) if float(x) >= 0 else float("nan")
                   for x in final.get("exitTimes", "").split()]
        depart = _f(el.get("depart"))
        vid = el.get("id")
        for i, edge in enumerate(edges):
            filas.append((vid, depart, i, edge, salidas[i] if i < len(salidas) else float("nan")))
    return pd.DataFrame(filas, columns=["id", "depart", "orden", "edge", "salida"])


def leer_emisiones(ruta, ids=None):
    """CO2 (mg/s) por vehículo y periodo del emission-output; `ids` filtra los vehículos."""
    filas = []
    for paso in _iterar(ruta, "timestep"):
        t = float(paso.get("time"))
        for v in paso.iterfind("vehicle"):
            vid = v.get("id")
            if ids is None or vid in ids:
                filas.append((t, vid, _f(v.get("CO2"), 0.0)))
    return pd.DataFrame(filas, columns=["t", "id", "co2_mg_s"])


def leer_red(ruta_net):
    """Edges normales (sin `function`) con la longitud y la forma de su primer carril."""
    filas = []
    for el in _iterar(ruta_net, "edge"):
        if el.get("function"):
            continue
        carril = el.find("lane")
        if carril is None:
            continue
        forma = [tuple(float(c) for c in p.split(",")[:2]) for p in carril.get("shape", "").split()]
        filas.append((el.get("id"), float(carril.get("length")), forma))
    return pd.DataFrame(filas, columns=["edge", "longitud", "forma"])


def leer_proyeccion(ruta_net):
    """(netOffset_x, netOffset_y, projParameter) del elemento <location> de la red."""
    for el in _iterar(ruta_net, "location"):
        dx, dy = (float(v) for v in el.get("netOffset").split(","))
        return dx, dy, el.get("projParameter")
    raise ValueError(f"{ruta_net} no tiene <location>")


def leer_demanda(ruta_rou):
    """Parámetros de cada trip/vehicle de la demanda (clase, con_app, destino, pa_objetivo...)."""
    claves = ["clase", "con_app", "destino", "pa_objetivo", "destino_nombre"]
    filas = []
    for _, el in etree.iterparse(str(Path(ruta_rou)), events=("end",), tag=("trip", "vehicle")):
        params = {p.get("key"): p.get("value") for p in el.iterfind("param")}
        filas.append([el.get("id")] + [params.get(k, "") for k in claves])
        el.clear()
    return pd.DataFrame(filas, columns=["id"] + claves)
