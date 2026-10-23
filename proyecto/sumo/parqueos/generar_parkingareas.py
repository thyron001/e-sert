"""Genera los puestos SERT (parkingArea de SUMO) sobre las calles tarifadas.

Uso (dentro del contenedor van3twin, desde esta carpeta):
    python3 generar_parkingareas.py [--red ../red/centro.net.xml] [--config calles_sert.yaml]
                                    [--sin-prueba] [--sin-grafica]

Salidas (en esta carpeta):
    parqueos.add.xml     parkingArea con id pa_<edgeId>_0 (pa_<edgeId>_1 si lado: ambos)
    puestos.csv          puesto_id,edge,lane,calle,capacidad,lat,lon,x,y  (contrato)
    parqueos_info.json   resumen: número de parkingArea, capacidad total y por calle
    ../centro_parqueos.sumocfg
La salida es determinista: los edges se recorren ordenados por id y no hay marcas de tiempo.
"""
import argparse
import csv
import json
import math
import os
import random
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

if "SUMO_HOME" not in os.environ:
    sys.exit("Falta SUMO_HOME: ejecuta este script dentro del contenedor van3twin.")
sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import sumolib  # noqa: E402
from sumolib.geomhelper import positionAtShapeOffset  # noqa: E402
import yaml  # noqa: E402

DIR = Path(__file__).resolve().parent
DIR_SUMO = DIR.parent
RED_DEFECTO = DIR_SUMO / "red" / "centro.net.xml"
ADD = DIR / "parqueos.add.xml"
CSV = DIR / "puestos.csv"
INFO = DIR / "parqueos_info.json"
CFG = DIR_SUMO / "centro_parqueos.sumocfg"
SALIDAS = DIR_SUMO / "salidas"
COLUMNAS = ["puesto_id", "edge", "lane", "calle", "capacidad", "lat", "lon", "x", "y"]
N_PRUEBA = 10
SEMILLA = 42


def normalizar(nombre):
    """Sin tildes, sin mayúsculas y sin el prefijo 'Avenida'/'Av.'."""
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    s = " ".join(s.replace(".", " ").split())
    for prefijo in ("avenida ", "av "):
        if s.startswith(prefijo):
            s = s[len(prefijo):]
    return s


def leer_config(ruta):
    cfg = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    cfg.setdefault("excluir_sin_nombre", True)
    cfg.setdefault("bbox_s_w_n_e", None)
    if cfg["lado"] not in ("derecho", "ambos"):
        sys.exit("calles_sert.yaml: lado debe ser 'derecho' o 'ambos'")
    return cfg


def carriles_passenger(edge):
    """Índices de los carriles que permiten passenger (0 = más a la derecha)."""
    return [l for l in edge.getLanes() if l.allows("passenger")]


def es_un_sentido(edge):
    """Sin edge en sentido contrario entre los mismos nodos."""
    return not any(e.getToNode() == edge.getFromNode()
                   for e in edge.getToNode().getOutgoing()
                   if e.getFunction() == "")


def elegir_edges(net, cfg):
    tipos = set(cfg["incluir_tipos"])
    excluir = {normalizar(n) for n in cfg["excluir_nombres"]}
    incluir = {normalizar(n) for n in cfg["incluir_nombres"]}
    elegidos = []
    for edge in sorted(net.getEdges(), key=lambda e: e.getID()):
        nombre = edge.getName() or ""
        if edge.getFunction() != "" or not edge.allows("passenger"):
            continue
        if edge.getType() not in tipos:
            continue
        if not nombre and cfg["excluir_sin_nombre"]:
            continue
        if normalizar(nombre) in excluir:
            continue
        if incluir and normalizar(nombre) not in incluir:
            continue
        elegidos.append(edge)
    return elegidos


def punto_en_carril(lane, pos):
    """(x, y) a la posición pos del carril; su geometría puede no medir lane.getLength()."""
    forma = lane.getShape()
    largo_forma = sum(math.dist(a, b) for a, b in zip(forma, forma[1:]))
    return positionAtShapeOffset(forma, pos * largo_forma / lane.getLength())


def dentro_bbox(net, bbox, *puntos):
    if bbox is None:
        return True
    s, w, n, e = bbox
    for x, y in puntos:
        lon, lat = net.convertXY2LonLat(x, y)
        if not (s <= lat <= n and w <= lon <= e):
            return False
    return True


def generar(net, cfg):
    """Devuelve la lista de puestos (dicts) en orden determinista."""
    largo, margen = cfg["largo_puesto_m"], cfg["margen_esquina_m"]
    puestos = []
    for edge in elegir_edges(net, cfg):
        carriles = carriles_passenger(edge)
        # El carril 0 suele ser la vereda: el lado derecho es el primer carril con passenger
        lados = [carriles[0]]
        # lado: ambos -> también el borde izquierdo en calles de un sentido con 2+ carriles
        if cfg["lado"] == "ambos" and len(carriles) >= 2 and es_un_sentido(edge):
            lados.append(carriles[-1])
        for n, lane in enumerate(lados):
            L = lane.getLength()
            inicio, fin = margen, L - margen
            if fin - inicio < cfg["largo_minimo_tramo_m"]:
                continue
            capacidad = math.floor((fin - inicio) / largo)
            if capacidad < 1:
                continue
            if not dentro_bbox(net, cfg["bbox_s_w_n_e"], punto_en_carril(lane, inicio),
                               punto_en_carril(lane, fin)):
                continue
            x, y = punto_en_carril(lane, (inicio + fin) / 2)
            lon, lat = net.convertXY2LonLat(x, y)
            puestos.append({
                "puesto_id": f"pa_{edge.getID()}_{n}",
                "edge": edge.getID(),
                "lane": lane.getID(),
                "calle": edge.getName(),
                "capacidad": capacidad,
                "lat": round(lat, 7),
                "lon": round(lon, 7),
                "x": round(x, 2),
                "y": round(y, 2),
                "startPos": round(inicio, 2),
                "endPos": round(fin, 2),
            })
    return puestos


def escribir_add(puestos):
    lineas = ['<?xml version="1.0" encoding="UTF-8"?>',
              "<!-- Generado por generar_parkingareas.py a partir de calles_sert.yaml."
              " No editar a mano. -->",
              "<additional>"]
    for p in puestos:
        lineas.append(
            f'    <parkingArea id="{xml_attr(p["puesto_id"])}" lane="{xml_attr(p["lane"])}" '
            f'startPos="{p["startPos"]:.2f}" endPos="{p["endPos"]:.2f}" '
            f'roadsideCapacity="{p["capacidad"]}" friendlyPos="true" '
            f'name="{xml_attr(p["calle"])}"/>')
    lineas.append("</additional>")
    ADD.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def xml_attr(s):
    return (s.replace("&", "&amp;").replace('"', "&quot;")
             .replace("<", "&lt;").replace(">", "&gt;"))


def escribir_csv(puestos):
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for p in puestos:
            fila = dict(p)
            fila["lat"], fila["lon"] = f"{p['lat']:.7f}", f"{p['lon']:.7f}"
            fila["x"], fila["y"] = f"{p['x']:.2f}", f"{p['y']:.2f}"
            w.writerow(fila)


def escribir_sumocfg():
    CFG.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!-- Red del Centro Histórico + edificios + puestos SERT, sin demanda. -->
<configuration>
    <input>
        <net-file value="red/centro.net.xml"/>
        <additional-files value="red/centro.poly.xml,parqueos/parqueos.add.xml"/>
    </input>
    <time>
        <begin value="0"/>
    </time>
</configuration>
""", encoding="utf-8")


def resumen(puestos, cfg, red):
    por_calle = Counter()
    for p in puestos:
        por_calle[p["calle"]] += p["capacidad"]
    top = sorted(por_calle.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    return {
        "red": os.path.relpath(red, DIR).replace(os.sep, "/"),
        "config": cfg,
        "parking_areas": len(puestos),
        "capacidad_total": sum(p["capacidad"] for p in puestos),
        "calles_con_puestos": len(por_calle),
        "capacidad_media_por_parking_area": round(
            sum(p["capacidad"] for p in puestos) / max(len(puestos), 1), 2),
        "capacidad_por_calle_top10": [{"calle": c, "capacidad": k} for c, k in top],
    }


# ------------------------------------------------------------------ pruebas
def ejecutar(cmd, cwd=DIR_SUMO):
    res = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout[-3000:], res.stderr[-3000:], sep="\n")
        sys.exit(f"Falló: {cmd[0]} (código {res.returncode})")
    return res


def prueba_carga():
    """sumo --end 10 con los parkingArea: sin errores ni advertencias."""
    res = ejecutar(["sumo", "-c", CFG.name, "--end", "10", "--no-step-log"])
    avisos = [l for l in res.stderr.splitlines() if "Warning" in l]
    return {"comando": f"sumo -c {CFG.name} --end 10", "codigo": res.returncode,
            "advertencias": len(avisos), "ejemplos_advertencias": avisos[:5]}


def prueba_estacionar(net, puestos):
    """10 vehículos, cada uno con un stop de 60 s en un parkingArea aleatorio."""
    SALIDAS.mkdir(exist_ok=True)
    rng = random.Random(SEMILLA)
    elegidos = rng.sample(puestos, N_PRUEBA)
    origenes = sorted((e for e in net.getEdges()
                       if e.getFunction() == "" and e.allows("passenger")
                       and e.getLength() > 30), key=lambda e: e.getID())
    rutas = SALIDAS / "prueba_parqueo.rou.xml"
    stops = SALIDAS / "prueba_parqueo.stops.xml"
    tripinfo = SALIDAS / "prueba_parqueo.tripinfo.xml"
    lineas = ["<routes>", '    <vType id="auto" vClass="passenger"/>']
    for i, p in enumerate(elegidos):
        origen = rng.choice([e for e in origenes if e.getID() != p["edge"]])
        lineas += [
            f'    <trip id="prueba{i}" type="auto" depart="{i * 5}" from="{xml_attr(origen.getID())}"'
            f' to="{xml_attr(p["edge"])}" departLane="best">',
            f'        <stop parkingArea="{xml_attr(p["puesto_id"])}" duration="60"/>',
            "    </trip>"]
    lineas.append("</routes>")
    rutas.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    ejecutar(["sumo", "-c", CFG.name, "-r", rutas, "--stop-output", stops,
              "--tripinfo-output", tripinfo, "--end", "3600", "--no-step-log",
              "--seed", str(SEMILLA)])
    estacionados = {s.get("id"): s.get("parkingArea")
                    for s in ET.parse(stops).getroot().iter("stopinfo")
                    if s.get("parkingArea")}
    esperados = {f"prueba{i}": p["puesto_id"] for i, p in enumerate(elegidos)}
    llegados = len(ET.parse(tripinfo).getroot().findall("tripinfo"))
    ok = estacionados == esperados and llegados == N_PRUEBA
    return {"vehiculos": N_PRUEBA, "estacionaron": len(estacionados),
            "llegaron_a_destino": llegados, "parking_areas": sorted(esperados.values()),
            "ok": ok}


def grafica(net, puestos, info, destino):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import Normalize

    fig, ax = plt.subplots(figsize=(11, 9.5))
    red = [e.getShape() for e in net.getEdges() if e.allows("passenger")]
    ax.add_collection(LineCollection(red, colors="#c8c8c8", linewidths=0.9, zorder=1))
    segmentos, caps = [], []
    for p in puestos:
        lane = net.getLane(p["lane"])
        pasos = 8
        segmentos.append([punto_en_carril(
            lane, p["startPos"] + (p["endPos"] - p["startPos"]) * j / pasos)
            for j in range(pasos + 1)])
        caps.append(p["capacidad"])
    norma = Normalize(vmin=min(caps), vmax=max(caps))
    lc = LineCollection(segmentos, array=caps, cmap="viridis", norm=norma,
                        linewidths=2.6, zorder=2)
    ax.add_collection(lc)
    fig.colorbar(lc, ax=ax, shrink=0.75, label="Capacidad del parkingArea (puestos)")
    xmin, ymin, xmax, ymax = net.getBoundary()
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m, UTM desplazado)")
    ax.set_ylabel("y (m, UTM desplazado)")
    ax.set_title(f"Puestos SERT generados: {info['parking_areas']} parkingArea · "
                 f"capacidad total {info['capacidad_total']} puestos · "
                 f"{info['calles_con_puestos']} calles", fontsize=11)
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    print(f"Gráfica -> {destino}")


def dir_evidencias():
    candidata = DIR.parents[2] / "evidencias"
    return candidata if candidata.is_dir() else SALIDAS


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--red", default=str(RED_DEFECTO))
    ap.add_argument("--config", default=str(DIR / "calles_sert.yaml"))
    ap.add_argument("--sin-prueba", action="store_true", help="no correr las pruebas con sumo")
    ap.add_argument("--sin-grafica", action="store_true")
    args = ap.parse_args()

    red = Path(args.red).resolve()
    cfg = leer_config(args.config)
    net = sumolib.net.readNet(str(red))
    puestos = generar(net, cfg)
    if not puestos:
        sys.exit("Ningún edge cumple los filtros de calles_sert.yaml.")
    escribir_add(puestos)
    escribir_csv(puestos)
    escribir_sumocfg()
    info = resumen(puestos, cfg, red)
    INFO.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"parkingArea: {info['parking_areas']}")
    print(f"capacidad total: {info['capacidad_total']} puestos en "
          f"{info['calles_con_puestos']} calles")
    print("capacidad por calle (10 mayores):")
    for fila in info["capacidad_por_calle_top10"]:
        print(f"  {fila['capacidad']:5d}  {fila['calle']}")

    ok = True
    if not args.sin_prueba:
        carga = prueba_carga()
        print(f"sumo --end 10: código {carga['codigo']}, {carga['advertencias']} advertencias")
        for a in carga["ejemplos_advertencias"]:
            print("  ", a)
        parqueo = prueba_estacionar(net, puestos)
        print(f"prueba de parqueo: {parqueo['estacionaron']}/{parqueo['vehiculos']} estacionaron,"
              f" {parqueo['llegaron_a_destino']} llegaron -> {'OK' if parqueo['ok'] else 'FALLA'}")
        # Las pruebas van a salidas/ para no romper el determinismo de parqueos_info.json
        (SALIDAS / "parqueos_pruebas.json").write_text(
            json.dumps({"carga": carga, "parqueo": parqueo}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        ok = carga["advertencias"] == 0 and parqueo["ok"]
    if not args.sin_grafica:
        ev = dir_evidencias()
        ev.mkdir(parents=True, exist_ok=True)
        grafica(net, puestos, info, ev / "s2_puestos-sert.png")
    if not ok:
        sys.exit("Las pruebas fallaron.")


if __name__ == "__main__":
    main()
