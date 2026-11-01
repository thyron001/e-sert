"""Construye la red SUMO del Centro Histórico de Cuenca (zona SERT).

Uso (dentro del contenedor van3twin, desde esta carpeta):
    python3 construir_red.py [--bbox S,W,N,E] [--sin-descarga] [--sin-gui]

Pasos:
    1. Descarga el OSM de la bbox con la API Overpass -> centro.osm.xml (ignorado por git).
    2. netconvert -> centro.net.xml (autos + peatones, veredas, cruces, UTM).
    3. polyconvert -> centro.poly.xml (edificios como fondo).
    4. Escribe ../centro_red.sumocfg (solo red + polígonos, sin demanda).
    5. Valida la red (sumolib) y la corre 10 s con sumo.
    6. Prueba peatonal: 20 peatones con randomTrips.py, sin teletransportes.
    7. Gráfica de evidencia (matplotlib) y captura de sumo-gui.
Todas las cifras quedan en red_info.json.
"""
import argparse
import datetime
import hashlib
import json
import os
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if "SUMO_HOME" not in os.environ:
    sys.exit("Falta SUMO_HOME: ejecuta este script dentro del contenedor van3twin.")
SUMO_HOME = Path(os.environ["SUMO_HOME"])
sys.path.append(str(SUMO_HOME / "tools"))
import sumolib  # noqa: E402

# Del río Tomebamba (Calle Larga) a la Av. Gaspar Sangurima,
# y de la Av. Huayna Cápac a la calle Coronel Talbot.
BBOX_DEFECTO = "-2.9050,-79.0130,-2.8895,-78.9945"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
N_PEATONES = 20
SEMILLA = 42

DIR_RED = Path(__file__).resolve().parent
DIR_SUMO = DIR_RED.parent
OSM = DIR_RED / "centro.osm.xml"
NET = DIR_RED / "centro.net.xml"
POLY = DIR_RED / "centro.poly.xml"
INFO = DIR_RED / "red_info.json"
CFG = DIR_SUMO / "centro_red.sumocfg"
# Archivos temporales: red cruda, podas y pruebas (ignorados por git)
SALIDAS = DIR_SUMO / "salidas"
NET_CRUDA = SALIDAS / "centro_cruda.net.xml"


def dir_evidencias():
    """En semanas/SN/<Nombre>/codigo/sumo/red -> semanas/SN/<Nombre>/evidencias."""
    candidata = DIR_RED.parents[2] / "evidencias"
    return candidata if candidata.is_dir() else SALIDAS


def ejecutar(cmd, cwd=DIR_RED):
    print("$", " ".join(shlex.quote(str(c)) for c in cmd), flush=True)
    res = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout[-3000:], res.stderr[-3000:], sep="\n")
        sys.exit(f"Falló: {cmd[0]} (código {res.returncode})")
    return res


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ---------------------------------------------------------------- 1. descarga
def descargar_osm(bbox):
    import requests

    s, w, n, e = bbox
    # Todos los nodos de la bbox, las vías/relaciones que los usan y los nodos de esas vías
    consulta = f"[out:xml][timeout:180];(node({s},{w},{n},{e});<;);(._;>;);out body;"
    for url in OVERPASS_URLS:
        try:
            print(f"Descargando OSM desde {url} ...", flush=True)
            r = requests.post(url, data={"data": consulta}, timeout=300,
                              headers={"User-Agent": "e-sert/0.1 (Universidad de Cuenca)"})
            r.raise_for_status()
            if b"<osm" not in r.content[:500]:
                raise RuntimeError("la respuesta no es OSM XML")
            OSM.write_bytes(r.content)
            print(f"  {len(r.content) / 1e6:.1f} MB -> {OSM.name}")
            return url
        except Exception as ex:  # probar el siguiente espejo
            print(f"  error: {ex}")
    sys.exit("No se pudo descargar el OSM de ningún servidor Overpass.")


# ------------------------------------------------------------- 2. netconvert
def comando_netconvert():
    return [
        "netconvert",
        "--osm-files", OSM.name,
        "--output.street-names", "true",
        "--output.original-names", "true",
        "--geometry.remove",
        "--roundabouts.guess",
        "--ramps.guess", "false",
        "--junctions.join",
        "--junctions.corner-detail", "5",
        "--tls.guess-signals", "--tls.discard-simple", "--tls.join",
        "--sidewalks.guess", "--crossings.guess", "--walkingareas",
        "--keep-edges.by-vclass", "passenger,pedestrian",
        "--remove-edges.isolated",
        "--proj.utm",
        "--output-file", f"../{SALIDAS.name}/{NET_CRUDA.name}",
    ]


def podar_componentes(max_vueltas=5):
    """Deja la red de autos como una sola componente fuertemente conexa.

    Los edges de autos fuera de la componente principal (sobre todo calles de un sentido
    cortadas por el borde de la bbox) se quitan con netconvert -s; se repite porque al
    quitar unos pueden quedar otros sin salida. Devuelve la lista de edges podados.
    """
    actual, podados = NET_CRUDA, []
    for vuelta in range(1, max_vueltas + 1):
        comps = componentes_autos(sumolib.net.readNet(str(actual)))
        print(f"  poda {vuelta}: {len(comps)} componente(s) de autos", flush=True)
        if len(comps) <= 1:
            break
        fuera = sorted(set().union(*comps[1:]))
        podados += fuera
        lista = SALIDAS / "edges_podados.txt"
        lista.write_text("\n".join(fuera) + "\n", encoding="utf-8")
        siguiente = SALIDAS / f"centro_poda{vuelta}.net.xml"
        ejecutar(["netconvert", "-s", actual, "--remove-edges.input-file", lista,
                  "--remove-edges.isolated", "--output-file", siguiente])
        actual = siguiente
    NET.write_bytes(actual.read_bytes())
    return podados


# ------------------------------------------------------------ 3. polyconvert
def comando_polyconvert():
    return [
        "polyconvert",
        "--net-file", NET.name,
        "--osm-files", OSM.name,
        "--type-file", str(SUMO_HOME / "data" / "typemap" / "osmPolyconvert.typ.xml"),
        "--output-file", POLY.name,
    ]


# ------------------------------------------------------------ 4. sumocfg
def escribir_sumocfg():
    CFG.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!-- Solo la red del Centro Histórico y los edificios, sin demanda. -->
<configuration>
    <input>
        <net-file value="red/centro.net.xml"/>
        <additional-files value="red/centro.poly.xml"/>
    </input>
    <time>
        <begin value="0"/>
    </time>
</configuration>
""", encoding="utf-8")


# ------------------------------------------------------------ 5. validación
def componentes_autos(net):
    """Componentes fuertemente conexas del grafo de edges que permiten 'passenger'."""
    edges = [e for e in edges_normales(net) if e.allows("passenger")]
    ids = {e.getID() for e in edges}
    sucesores = {
        e.getID(): [d.getID() for d, cons in e.getOutgoing().items()
                    if d.getID() in ids and any(c.getFromLane().allows("passenger")
                                                and c.getToLane().allows("passenger")
                                                for c in cons)]
        for e in edges
    }
    # Tarjan iterativo
    indice, bajo, en_pila, pila, comps, cont = {}, {}, set(), [], [], [0]
    for raiz in ids:
        if raiz in indice:
            continue
        trabajo = [(raiz, iter(sucesores[raiz]))]
        indice[raiz] = bajo[raiz] = cont[0]
        cont[0] += 1
        pila.append(raiz)
        en_pila.add(raiz)
        while trabajo:
            v, it = trabajo[-1]
            avanzo = False
            for w in it:
                if w not in indice:
                    indice[w] = bajo[w] = cont[0]
                    cont[0] += 1
                    pila.append(w)
                    en_pila.add(w)
                    trabajo.append((w, iter(sucesores[w])))
                    avanzo = True
                    break
                if w in en_pila:
                    bajo[v] = min(bajo[v], indice[w])
            if avanzo:
                continue
            trabajo.pop()
            if trabajo:
                bajo[trabajo[-1][0]] = min(bajo[trabajo[-1][0]], bajo[v])
            if bajo[v] == indice[v]:
                comp = set()
                while True:
                    w = pila.pop()
                    en_pila.discard(w)
                    comp.add(w)
                    if w == v:
                        break
                comps.append(comp)
    return sorted(comps, key=len, reverse=True)


def edges_normales(net):
    """Con withPedestrianConnections sumolib también carga los edges internos (':...')."""
    return [e for e in net.getEdges() if e.getFunction() == ""]


def contar_funciones():
    """Cuenta edges internos especiales (crossing, walkingarea) leyendo el XML."""
    cuenta = {"crossing": 0, "walkingarea": 0}
    for _, el in ET.iterparse(NET, events=("end",)):
        if el.tag == "edge" and el.get("function") in cuenta:
            cuenta[el.get("function")] += 1
        el.clear()
    return cuenta


def validar_red():
    net = sumolib.net.readNet(str(NET), withPedestrianConnections=True)
    edges = edges_normales(net)
    autos = [e for e in edges if e.allows("passenger")]
    peat = [e for e in edges if e.allows("pedestrian")]
    con_vereda = [e for e in autos
                  if any(l.allows("pedestrian") and not l.allows("passenger")
                         for l in e.getLanes())]
    semaforos = net.getTrafficLights()
    nodos_tls = [n for n in net.getNodes() if "traffic_light" in n.getType()]
    comps = componentes_autos(net)
    fuera = sorted(set().union(*comps[1:])) if len(comps) > 1 else []
    especiales = contar_funciones()
    loc = net._location if hasattr(net, "_location") else {}
    info = {
        "edges_total": len(edges),
        "edges_passenger": len(autos),
        "edges_pedestrian": len(peat),
        "edges_passenger_con_vereda": len(con_vereda),
        "cruces_peatonales": especiales["crossing"],
        "walkingareas": especiales["walkingarea"],
        "semaforos_tls": len(semaforos),
        "nodos_con_semaforo": len(nodos_tls),
        "longitud_total_km": round(sum(e.getLength() for e in edges) / 1000, 2),
        "longitud_autos_km": round(sum(e.getLength() for e in autos) / 1000, 2),
        "componentes_autos": len(comps),
        "edges_autos_componente_principal": len(comps[0]) if comps else 0,
        "edges_autos_fuera_componente_principal": len(fuera),
        "ids_edges_autos_fuera": fuera,
        "proyeccion": {
            "proj": loc.get("projParameter"),
            "netOffset": loc.get("netOffset"),
            "convBoundary": loc.get("convBoundary"),
            "origBoundary": loc.get("origBoundary"),
        },
    }
    return net, info


def prueba_sumo_10s():
    res = ejecutar(["sumo", "-c", CFG.name, "--end", "10", "--no-step-log"], cwd=DIR_SUMO)
    return {"comando": f"sumo -c {CFG.name} --end 10", "codigo": res.returncode,
            "advertencias": res.stderr.count("Warning")}


# ------------------------------------------------------- 6. prueba peatonal
def prueba_peatonal():
    SALIDAS.mkdir(exist_ok=True)
    trips = SALIDAS / "peatones.rou.xml"
    stats = SALIDAS / "peatones.stats.xml"
    tripinfo = SALIDAS / "peatones.tripinfo.xml"
    ejecutar([sys.executable, SUMO_HOME / "tools" / "randomTrips.py",
              "-n", NET, "-o", trips, "-r", SALIDAS / "peatones.validados.rou.xml",
              "--pedestrians", "--validate",
              "-b", "0", "-e", str(3 * N_PEATONES), "-p", "1", "--seed", str(SEMILLA),
              "--min-distance", "200"])
    # --validate descarta los viajes sin ruta peatonal; se sobregeneran y se toman los 20 primeros
    arbol = ET.parse(trips)
    personas = arbol.getroot().findall("person")
    validos = len(personas)
    for sobra in personas[N_PEATONES:]:
        arbol.getroot().remove(sobra)
    arbol.write(trips, encoding="UTF-8", xml_declaration=True)
    res = ejecutar(["sumo", "-n", NET, "-r", trips, "--duration-log.statistics",
                    "--statistic-output", stats, "--tripinfo-output", tripinfo,
                    "--seed", str(SEMILLA), "--end", "7200", "--no-step-log"], cwd=DIR_SUMO)
    generados = len(ET.parse(trips).getroot().findall("person"))
    raiz = ET.parse(stats).getroot()
    tele = raiz.find("teleports")
    ped = raiz.find("pedestrianStatistics")
    personas = raiz.find("persons")
    llegados = len(ET.parse(tripinfo).getroot().findall("personinfo"))
    resultado = {
        "viajes_sorteados": 3 * N_PEATONES,
        "viajes_descartados_sin_ruta": 3 * N_PEATONES - validos,
        "peatones_generados": generados,
        "peatones_llegados": llegados,
        "teletransportes_total": int(tele.get("total")) if tele is not None else None,
        "distancia_media_m": float(ped.get("routeLength")) if ped is not None else None,
        "duracion_media_s": float(ped.get("duration")) if ped is not None else None,
        "peatones_atascados": int(personas.get("jammed")) if personas is not None else None,
        "avisos_teleport": (res.stdout + res.stderr).lower().count("teleport"),
    }
    # SUMO 1.12 solo imprime la línea de teletransportes si hay alguno: se usa statistic-output
    resultado["ok"] = (generados == N_PEATONES and llegados == N_PEATONES
                       and resultado["teletransportes_total"] == 0
                       and resultado["peatones_atascados"] == 0
                       and resultado["avisos_teleport"] == 0)
    return resultado


# ------------------------------------------------------------- 7. evidencias
def grafica(net, info, destino):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection, PolyCollection

    fig, ax = plt.subplots(figsize=(11, 10))
    edificios = [[tuple(map(float, p.split(","))) for p in el.get("shape").split()]
                 for el in ET.parse(POLY).getroot().iter("poly")
                 if el.get("type", "").startswith("building")]
    ax.add_collection(PolyCollection(edificios, facecolor="#ece6dc", edgecolor="none",
                                     zorder=0))
    veredas, autos = [], []
    for e in edges_normales(net):
        forma = e.getShape()
        if e.allows("passenger"):
            autos.append(forma)
        if e.allows("pedestrian"):
            veredas.append(forma)
    ax.add_collection(LineCollection(veredas, colors="#bdbdbd", linewidths=3.2, zorder=1,
                                     label="Veredas y vías peatonales"))
    ax.add_collection(LineCollection(autos, colors="#333333", linewidths=1.1, zorder=2,
                                     label="Edges de autos"))
    xs = [n.getCoord()[0] for n in net.getNodes() if "traffic_light" in n.getType()]
    ys = [n.getCoord()[1] for n in net.getNodes() if "traffic_light" in n.getType()]
    ax.scatter(xs, ys, s=14, c="#d62728", zorder=3, label="Semáforos")
    xmin, ymin, xmax, ymax = net.getBoundary()
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m, UTM desplazado)")
    ax.set_ylabel("y (m, UTM desplazado)")
    ax.legend(loc="lower right", framealpha=0.9)
    ax.set_title(
        "Red SUMO del Centro Histórico de Cuenca\n"
        f"{info['edges_passenger']} edges de autos · {info['edges_pedestrian']} peatonales · "
        f"{info['cruces_peatonales']} cruces · {info['semaforos_tls']} semáforos · "
        f"{info['longitud_total_km']} km · {info['componentes_autos']} componente(s) de autos",
        fontsize=11)
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    print(f"Gráfica -> {destino}")


def grafica_poda(podados, destino):
    """Muestra sobre la red cruda qué edges de autos se podaron."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    cruda = sumolib.net.readNet(str(NET_CRUDA))
    quitar = set(podados)
    autos = [e for e in cruda.getEdges() if e.allows("passenger")]
    fig, ax = plt.subplots(figsize=(11, 8))
    ax.add_collection(LineCollection([e.getShape() for e in autos if e.getID() not in quitar],
                                     colors="#9e9e9e", linewidths=1, label="Se conservan"))
    ax.add_collection(LineCollection([e.getShape() for e in autos if e.getID() in quitar],
                                     colors="#e65100", linewidths=2.2,
                                     label=f"Podados ({len(quitar)} edges)"))
    xmin, ymin, xmax, ymax = cruda.getBoundary()
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.legend(loc="lower right")
    ax.set_title("Edges de autos fuera de la componente fuertemente conexa principal")
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    print(f"Gráfica de la poda -> {destino}")


def captura_gui(net, destino):
    import traci

    try:
        traci.start(["sumo-gui", "-c", str(CFG), "--start", "--quit-on-end",
                     "--window-size", "1400,1200", "--delay", "0"])
        vista = traci.gui.DEFAULT_VIEW
        xmin, ymin, xmax, ymax = net.getBoundary()
        traci.gui.setBoundary(vista, xmin, ymin, xmax, ymax)
        traci.gui.screenshot(vista, str(destino))
        traci.simulationStep()  # la captura se toma al avanzar un paso
        traci.simulationStep()
        traci.close()
        print(f"Captura sumo-gui -> {destino}")
        return True
    except Exception as ex:
        print(f"No se pudo capturar sumo-gui: {ex}")
        try:
            traci.close()
        except Exception:
            pass
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bbox", default=BBOX_DEFECTO, help="S,W,N,E en grados (WGS84)")
    ap.add_argument("--sin-descarga", action="store_true",
                    help="usar centro.osm.xml local en vez de descargarlo")
    ap.add_argument("--sin-gui", action="store_true", help="no capturar sumo-gui")
    args = ap.parse_args()
    bbox = [float(v) for v in args.bbox.split(",")]
    if len(bbox) != 4:
        sys.exit("--bbox debe ser S,W,N,E")

    fuente = "local"
    if args.sin_descarga:
        if not OSM.exists():
            sys.exit(f"--sin-descarga: no existe {OSM.name}")
    else:
        fuente = descargar_osm(bbox)

    SALIDAS.mkdir(exist_ok=True)
    cmd_net = comando_netconvert()
    ejecutar(cmd_net)
    podados = podar_componentes()
    cmd_poly = comando_polyconvert()
    ejecutar(cmd_poly)
    escribir_sumocfg()

    net, info_red = validar_red()
    info = {
        "generado": datetime.datetime.now().isoformat(timespec="seconds"),
        "sumo": ejecutar(["sumo", "--version"]).stdout.splitlines()[0],
        "bbox_s_w_n_e": bbox,
        "osm": {"archivo": OSM.name, "fuente": fuente, "sha256": sha256(OSM),
                "bytes": OSM.stat().st_size},
        "netconvert": " ".join(shlex.quote(str(c)) for c in cmd_net),
        "polyconvert": " ".join(shlex.quote(str(c)) for c in cmd_poly)
                          .replace(str(SUMO_HOME), "$SUMO_HOME"),
        "poda_componentes": {
            "descripcion": "edges de autos fuera de la componente fuertemente conexa "
                           "principal, quitados con netconvert -s --remove-edges.input-file",
            "edges_podados": len(podados),
            "ids": podados,
        },
        "red": info_red,
        "prueba_sumo_10s": prueba_sumo_10s(),
        "prueba_peatonal": prueba_peatonal(),
    }
    INFO.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")

    r = info_red
    print("\n== Resumen de la red ==")
    print(f"edges con passenger:   {r['edges_passenger']}")
    print(f"edges con pedestrian:  {r['edges_pedestrian']}")
    print(f"cruces peatonales:     {r['cruces_peatonales']}")
    print(f"semáforos (tls):       {r['semaforos_tls']}")
    print(f"longitud total:        {r['longitud_total_km']} km")
    print(f"componentes de autos:  {r['componentes_autos']} "
          f"({r['edges_autos_fuera_componente_principal']} edges fuera de la principal)")
    print(f"sumo --end 10:         código {info['prueba_sumo_10s']['codigo']}")
    p = info["prueba_peatonal"]
    print(f"peatones:              {p['peatones_llegados']}/{p['peatones_generados']} llegaron, "
          f"{p['teletransportes_total']} teletransportes -> {'OK' if p['ok'] else 'FALLA'}")

    ev = dir_evidencias()
    ev.mkdir(parents=True, exist_ok=True)
    grafica(net, info_red, ev / "s1_red-centro.png")
    if podados:
        grafica_poda(podados, ev / "s1_componentes-podadas.png")
    if not args.sin_gui:
        captura_gui(net, ev / "s1_red-centro-gui.png")
    print(f"\nInfo -> {INFO}")
    if not p["ok"]:
        sys.exit("La prueba peatonal falló.")


if __name__ == "__main__":
    main()
