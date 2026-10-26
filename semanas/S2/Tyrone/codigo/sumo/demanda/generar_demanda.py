"""Genera la demanda de hora pico y los rerouters de búsqueda a ciegas (línea base).

Uso (dentro del contenedor van3twin, desde esta carpeta):
    python3 generar_demanda.py [--veh-hora 1800] [--porc-paso 40] [--duracion-s 3600]
                               [--warmup-s 900] [--ocupacion-fondo 0.80] [--semilla 1]
                               [--salida demanda.rou.xml]

Tres clases de vehículos, todos con <param key="con_app" value="0"/>:
    busca  llega por un edge de borde, va al parkingArea más cercano a su destino
           (destinos.csv, elegido por peso), estaciona una estadía lognormal (media 45 min,
           recortada a 10-120 min) y sale por otro edge de borde.
    paso   cruza la zona sin estacionar (--porc-paso % de las llegadas).
    fondo  ya está estacionado al empezar (larga estadía: trabajadores y residentes) y no
           se mueve en toda la corrida; ocupa --ocupacion-fondo de cada parkingArea.
Las llegadas de busca y paso son Poisson con tasa --veh-hora durante warm-up + duración.

También escribe rerouters.add.xml: para cada parkingArea, un <rerouter> en su edge con
<parkingAreaReroute visible="false"> hacia los parkingArea a menos de 400 m (el conductor
solo sabe si hay lugar cuando llega). Es determinista para una misma semilla.
"""
import argparse
import csv
import math
import os
import random
import sys
from pathlib import Path

if "SUMO_HOME" not in os.environ:
    sys.exit("Falta SUMO_HOME: ejecuta este script dentro del contenedor van3twin.")
sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import sumolib  # noqa: E402

DIR = Path(__file__).resolve().parent
DIR_SUMO = DIR.parent
RED = DIR_SUMO / "red" / "centro.net.xml"
PUESTOS = DIR_SUMO / "parqueos" / "puestos.csv"
ADD_PARQUEOS = DIR_SUMO / "parqueos" / "parqueos.add.xml"
DESTINOS = DIR / "destinos.csv"
REROUTERS = DIR / "rerouters.add.xml"
CFG = DIR_SUMO / "centro_base.sumocfg"
SALIDAS = DIR_SUMO / "salidas"
# Misma bbox que la red (S1-1): define el perímetro por el que se entra y se sale
BBOX = (-2.9050, -79.0130, -2.8895, -78.9945)
RADIO_ALTERNATIVAS_M = 400.0
MARGEN_PERIMETRO_M = 100.0
ESTADIA_MEDIA_MIN, ESTADIA_SIGMA = 45.0, 0.5
ESTADIA_MIN_MIN, ESTADIA_MAX_MIN = 10.0, 120.0
# El prompt pide HBEFA4/PC_petrol_Euro-4, que no existe en SUMO 1.12: su equivalente
# HBEFA3 es el auto a gasolina Euro 4
CLASE_EMISION = "HBEFA3/PC_G_EU4"
FONDO_DURACION_S = 86400  # larga estadía: no sale durante la corrida
# Búsqueda "lo más cerca del destino": distancia desde la posición actual (peso 1) más la
# cercanía al parkingArea original codificada en el atributo probability (peso 0.5)
PARAMS_BUSQUEDA = {
    "parking.distance.weight": "1",
    "parking.probability.weight": "0.5",
}


def xml_attr(s):
    return (str(s).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def leer_puestos():
    with open(PUESTOS, encoding="utf-8") as f:
        return [dict(r, capacidad=int(r["capacidad"]), x=float(r["x"]), y=float(r["y"]))
                for r in csv.DictReader(f)]


def leer_destinos(net):
    with open(DESTINOS, encoding="utf-8") as f:
        destinos = list(csv.DictReader(f))
    for d in destinos:
        d["peso"] = float(d["peso"])
        d["x"], d["y"] = net.convertLonLat2XY(float(d["lon"]), float(d["lat"]))
    return destinos


def distancia_a_bbox(net, nodo):
    """Metros desde el nodo hasta el borde de la bbox (negativo si está fuera)."""
    lon, lat = net.convertXY2LonLat(*nodo.getCoord())
    s, w, n, e = BBOX
    m_lat = 110574.0
    m_lon = 111320.0 * math.cos(math.radians(lat))
    return min((lat - s) * m_lat, (n - lat) * m_lat, (lon - w) * m_lon, (e - lon) * m_lon)


def es_extremo(nodo):
    """Nodo sin salida: solo conecta con un nodo vecino (fin de calle cortada por el borde)."""
    vecinos = {e.getFromNode().getID() for e in nodo.getIncoming() if e.allows("passenger")}
    vecinos |= {e.getToNode().getID() for e in nodo.getOutgoing() if e.allows("passenger")}
    return len(vecinos) == 1


def edges_borde(net):
    """Entradas y salidas de la zona.

    Entrada: edge de autos que nace en un nodo sin salida del perímetro, o que cruza la bbox
    hacia adentro. Salida: lo mismo en sentido contrario.
    """
    entradas, salidas = set(), set()
    for e in net.getEdges():
        if e.getFunction() != "" or not e.allows("passenger") or e.getLength() < 20:
            continue
        d_desde = distancia_a_bbox(net, e.getFromNode())
        d_hacia = distancia_a_bbox(net, e.getToNode())
        if (es_extremo(e.getFromNode()) and d_desde < MARGEN_PERIMETRO_M) or (d_desde < 0 <= d_hacia):
            entradas.add(e.getID())
        if (es_extremo(e.getToNode()) and d_hacia < MARGEN_PERIMETRO_M) or (d_hacia < 0 <= d_desde):
            salidas.add(e.getID())
    return sorted(entradas), sorted(salidas)


def escribir_rerouters(puestos):
    lineas = ['<?xml version="1.0" encoding="UTF-8"?>',
              "<!-- Búsqueda a ciegas: alternativas a menos de "
              f"{RADIO_ALTERNATIVAS_M:.0f} m, invisibles hasta llegar. Generado por "
              "generar_demanda.py. -->",
              "<additional>"]
    n_alt = []
    for p in puestos:
        cercanos = sorted(
            ((math.hypot(q["x"] - p["x"], q["y"] - p["y"]), q["puesto_id"]) for q in puestos),
            key=lambda t: (t[0], t[1]))
        cercanos = [(d, q) for d, q in cercanos if d <= RADIO_ALTERNATIVAS_M]
        n_alt.append(len(cercanos) - 1)
        lineas.append(f'    <rerouter id="rr_{xml_attr(p["puesto_id"])}" '
                      f'edges="{xml_attr(p["edge"])}">')
        lineas.append(f'        <interval begin="0" end="{FONDO_DURACION_S}">')
        for d, q in cercanos:
            # Cercanía al parkingArea original: 1 en el mismo, 0.1 a 400 m
            prob = 1.0 - 0.9 * d / RADIO_ALTERNATIVAS_M
            lineas.append(f'            <parkingAreaReroute id="{xml_attr(q)}" '
                          f'probability="{prob:.3f}" visible="false"/>')
        lineas.append("        </interval>")
        lineas.append("    </rerouter>")
    lineas.append("</additional>")
    REROUTERS.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return sum(n_alt) / len(n_alt)


def estadia_s(rng):
    mu = math.log(ESTADIA_MEDIA_MIN) - ESTADIA_SIGMA ** 2 / 2  # media de la lognormal = 45
    minutos = min(max(rng.lognormvariate(mu, ESTADIA_SIGMA), ESTADIA_MIN_MIN), ESTADIA_MAX_MIN)
    return round(minutos * 60)


def generar(net, args):
    rng = random.Random(args.semilla)
    puestos = leer_puestos()
    destinos = leer_destinos(net)
    entradas, salidas = edges_borde(net)
    if not entradas or not salidas:
        sys.exit("No se encontraron edges de borde.")
    # parkingArea objetivo de cada destino: el de punto medio más cercano
    for d in destinos:
        d["pa"] = min(puestos, key=lambda p: (math.hypot(p["x"] - d["x"], p["y"] - d["y"]),
                                              p["puesto_id"]))
    pesos = [d["peso"] for d in destinos]
    fin = args.warmup_s + args.duracion_s

    vehiculos = []  # (depart, xml)
    # --- fondo: ocupación inicial de larga estadía
    n_fondo = 0
    for p in puestos:
        ocupados = sum(rng.random() < args.ocupacion_fondo for _ in range(p["capacidad"]))
        for k in range(ocupados):
            vid = f"fondo_{p['puesto_id'][3:]}_{k}"
            vehiculos.append((k * 4.0, (
                f'    <vehicle id="{xml_attr(vid)}" type="auto" depart="{k * 4.0:.2f}" '
                f'departPos="0" departSpeed="0">\n'
                f'        <route edges="{xml_attr(p["edge"])}"/>\n'
                f'        <stop parkingArea="{xml_attr(p["puesto_id"])}" '
                f'duration="{FONDO_DURACION_S}"/>\n'
                f'        <param key="con_app" value="0"/>\n'
                f'        <param key="clase" value="fondo"/>\n'
                f'    </vehicle>')))
            n_fondo += 1
    # --- llegadas Poisson: busca y paso
    t, n_busca, n_paso = 0.0, 0, 0
    tasa = args.veh_hora / 3600.0
    while True:
        t += rng.expovariate(tasa)
        if t >= fin:
            break
        origen = rng.choice(entradas)
        destino_salida = rng.choice([s for s in salidas if s != origen])
        if rng.random() * 100 < args.porc_paso:
            vid = f"paso_{n_paso}"
            n_paso += 1
            vehiculos.append((t, (
                f'    <trip id="{vid}" type="auto" depart="{t:.2f}" from="{xml_attr(origen)}" '
                f'to="{xml_attr(destino_salida)}" departLane="best" departSpeed="max">\n'
                f'        <param key="con_app" value="0"/>\n'
                f'        <param key="clase" value="paso"/>\n'
                f'    </trip>')))
        else:
            d = rng.choices(destinos, weights=pesos)[0]
            pa = d["pa"]
            vid = f"busca_{n_busca}"
            n_busca += 1
            vehiculos.append((t, (
                f'    <trip id="{vid}" type="auto" depart="{t:.2f}" from="{xml_attr(origen)}" '
                f'to="{xml_attr(destino_salida)}" departLane="best" departSpeed="max">\n'
                f'        <stop parkingArea="{xml_attr(pa["puesto_id"])}" '
                f'duration="{estadia_s(rng)}"/>\n'
                f'        <param key="con_app" value="0"/>\n'
                f'        <param key="clase" value="busca"/>\n'
                f'        <param key="destino" value="{xml_attr(d["nombre"])}"/>\n'
                f'        <param key="pa_objetivo" value="{xml_attr(pa["puesto_id"])}"/>\n'
                f'    </trip>')))
    vehiculos.sort(key=lambda v: v[0])  # SUMO exige orden por depart (sort estable)

    params = "".join(f'        <param key="{k}" value="{v}"/>\n'
                     for k, v in PARAMS_BUSQUEDA.items())
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        # (en un comentario XML no se permite "--")
        f.write(f"<!-- generar_demanda.py: veh_hora={args.veh_hora} porc_paso={args.porc_paso}"
                f" duracion_s={args.duracion_s} warmup_s={args.warmup_s}"
                f" ocupacion_fondo={args.ocupacion_fondo} semilla={args.semilla} -->\n")
        f.write("<routes>\n")
        f.write('    <vType id="auto" vClass="passenger" '
                f'emissionClass="{CLASE_EMISION}">\n' + params + "    </vType>\n")
        for _, xml in vehiculos:
            f.write(xml + "\n")
        f.write("</routes>\n")
    return {"fondo": n_fondo, "busca": n_busca, "paso": n_paso,
            "entradas": len(entradas), "salidas": len(salidas),
            "capacidad_total": sum(p["capacidad"] for p in puestos),
            "destinos": {d["nombre"]: d["pa"]["puesto_id"] for d in destinos}}


def escribir_sumocfg(fin):
    CFG.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Escenario base: búsqueda a ciegas, sin app. Semilla 1; otras semillas con correr_base.py. -->
<configuration>
    <input>
        <net-file value="red/centro.net.xml"/>
        <route-files value="demanda/demanda.rou.xml"/>
        <additional-files value="red/centro.poly.xml,parqueos/parqueos.add.xml,demanda/rerouters.add.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{fin}"/>
    </time>
    <output>
        <tripinfo-output value="salidas/base_1/tripinfo.xml"/>
        <stop-output value="salidas/base_1/stops.xml"/>
        <stop-output.write-unfinished value="true"/>
        <vehroute-output value="salidas/base_1/vehroutes.xml"/>
        <vehroute-output.exit-times value="true"/>
        <vehroute-output.route-length value="true"/>
        <vehroute-output.write-unfinished value="true"/>
        <emission-output value="salidas/base_1/emisiones.xml"/>
        <statistic-output value="salidas/base_1/estadisticas.xml"/>
    </output>
    <emissions>
        <device.emissions.probability value="1"/>
        <device.emissions.period value="10"/>
    </emissions>
    <processing>
        <time-to-teleport value="300"/>
        <ignore-route-errors value="true"/>
    </processing>
    <random_number>
        <seed value="1"/>
    </random_number>
    <report>
        <no-step-log value="true"/>
        <duration-log.statistics value="true"/>
    </report>
</configuration>
""", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # Calibrado en S1-3 para 85-95 % de ocupación en la hora pico (el prompt sugería 600):
    # 600 -> 82.4 %, 1000 -> 84.0 %, 1400 -> 85.5 %, 1800 -> 87.0 % (semilla 1, fondo 0.80)
    ap.add_argument("--veh-hora", type=float, default=1800.0,
                    help="llegadas por hora (busca + paso)")
    ap.add_argument("--porc-paso", type=float, default=40.0,
                    help="porcentaje de tráfico de paso")
    ap.add_argument("--duracion-s", type=int, default=3600, help="duración de la hora pico")
    ap.add_argument("--warmup-s", type=int, default=900, help="calentamiento previo")
    ap.add_argument("--ocupacion-fondo", type=float, default=0.80,
                    help="fracción de puestos ocupados por larga estadía desde el inicio")
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--salida", default=str(DIR / "demanda.rou.xml"))
    args = ap.parse_args()

    net = sumolib.net.readNet(str(RED))
    info = generar(net, args)
    alt = escribir_rerouters(leer_puestos())
    escribir_sumocfg(args.warmup_s + args.duracion_s)
    (SALIDAS / f"base_{args.semilla}").mkdir(parents=True, exist_ok=True)
    print(f"vehículos: {info['fondo']} de fondo, {info['busca']} buscan, {info['paso']} de paso")
    print(f"edges de borde: {info['entradas']} entradas, {info['salidas']} salidas")
    print(f"rerouters: {len(leer_puestos())} (media de {alt:.1f} alternativas a "
          f"<= {RADIO_ALTERNATIVAS_M:.0f} m)")
    print(f"demanda -> {args.salida}")


if __name__ == "__main__":
    main()
