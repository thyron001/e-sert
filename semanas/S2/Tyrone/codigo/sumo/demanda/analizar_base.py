"""Análisis PROVISIONAL de una corrida del escenario base (el cálculo formal de KPIs es de S2).

Uso:
    python3 analizar_base.py ../salidas/base_1 [../salidas/base_2 ...]
                             [--histograma ruta.png] [--ocupacion ruta.png]

Para cada carpeta de salidas lee stops.xml, vehroutes.xml, estadisticas.xml, sumo.log y la
demanda (demanda.rou.xml de la carpeta o, si no existe, la de demanda/), y escribe
resumen.json en esa misma carpeta:
    - ocupación de los puestos cada 60 s y su media en la hora pico (después del warm-up);
    - tiempo de búsqueda de cada vehículo 'busca': desde que entra por primera vez al edge de
      su parkingArea objetivo hasta que estaciona (vehroute exitTimes + stop-output);
    - teletransportes por vehículo (sumo.log) y vehículos con con_app.
"""
import argparse
import csv
import json
import re
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path

DIR = Path(__file__).resolve().parent
PUESTOS = DIR.parent / "parqueos" / "puestos.csv"
PASO_S = 60


def leer_demanda(ruta):
    """id -> {clase, pa_objetivo, con_app}; y los parámetros de la cabecera."""
    vehiculos = {}
    cabecera = ""
    for _, el in ET.iterparse(ruta, events=("end",)):
        if el.tag in ("vehicle", "trip"):
            params = {p.get("key"): p.get("value") for p in el.findall("param")}
            vehiculos[el.get("id")] = params
            el.clear()
    texto = Path(ruta).read_text(encoding="utf-8")[:600]
    m = re.search(r"<!-- generar_demanda\.py: (.*?) -->", texto)
    if m:
        cabecera = dict(kv.split("=") for kv in m.group(1).split())
    return vehiculos, cabecera


def ocupacion(stops, capacidad, fin, warmup):
    intervalos = []
    for s in stops:
        inicio = float(s.get("started"))
        termino = float(s.get("ended"))
        intervalos.append((inicio, fin if termino < 0 else termino))
    serie = []
    for t in range(0, int(fin), PASO_S):  # en t = fin la simulación ya terminó
        serie.append((t, sum(1 for a, b in intervalos if a <= t < b) / capacidad))
    pico = [o for t, o in serie if warmup <= t < fin]
    return serie, statistics.mean(pico)


def tiempos_busqueda(vehroutes, paradas, demanda, edge_de_pa):
    tiempos = {}
    for v in ET.parse(vehroutes).getroot().iter("vehicle"):
        vid = v.get("id")
        params = demanda.get(vid, {})
        if params.get("clase") != "busca" or vid not in paradas:
            continue
        rutas = v.findall("route") or v.findall("routeDistribution/route")
        final = rutas[-1]
        edges = final.get("edges").split()
        salidas = [float(x) for x in final.get("exitTimes", "").split()]
        objetivo = edge_de_pa[params["pa_objetivo"]]
        if objetivo not in edges:
            continue
        i = edges.index(objetivo)
        if i == 0 or i - 1 >= len(salidas):
            continue
        llegada = salidas[i - 1]  # entra al edge objetivo al salir del anterior
        tiempos[vid] = max(0.0, paradas[vid] - llegada)
    return tiempos


def analizar(carpeta):
    carpeta = Path(carpeta)
    with open(PUESTOS, encoding="utf-8") as f:
        puestos = list(csv.DictReader(f))
    capacidad = sum(int(p["capacidad"]) for p in puestos)
    edge_de_pa = {p["puesto_id"]: p["edge"] for p in puestos}
    ruta_demanda = carpeta / "demanda.rou.xml"
    if not ruta_demanda.exists():
        ruta_demanda = DIR / "demanda.rou.xml"
    demanda, cabecera = leer_demanda(ruta_demanda)
    warmup = float(cabecera.get("warmup_s", 900))
    fin = warmup + float(cabecera.get("duracion_s", 3600))

    stops = [s for s in ET.parse(carpeta / "stops.xml").getroot().iter("stopinfo")
             if s.get("parkingArea")]
    serie, media_pico = ocupacion(stops, capacidad, fin, warmup)
    # Primera vez que estaciona cada vehículo
    paradas = {}
    for s in stops:
        paradas.setdefault(s.get("id"), float(s.get("started")))
    busq = tiempos_busqueda(carpeta / "vehroutes.xml", paradas, demanda, edge_de_pa)

    est = ET.parse(carpeta / "estadisticas.xml").getroot()
    log = (carpeta / "sumo.log").read_text(encoding="utf-8", errors="replace") \
        if (carpeta / "sumo.log").exists() else ""
    teletransportados = set(re.findall(r"Teleporting vehicle '([^']+)'", log))
    cargados = int(est.find("vehicles").get("loaded"))
    clases = {}
    for params in demanda.values():
        clases[params.get("clase")] = clases.get(params.get("clase"), 0) + 1
    buscadores = [vid for vid, p in demanda.items() if p.get("clase") == "busca"]
    estacionados = [vid for vid in buscadores if vid in paradas]
    valores = sorted(busq.values())
    resumen = {
        "carpeta": carpeta.name,
        "parametros_demanda": cabecera,
        "capacidad_total": capacidad,
        "ocupacion_media_hora_pico": round(media_pico, 4),
        "ocupacion_min_max_hora_pico": [round(min(o for t, o in serie if warmup <= t < fin), 4),
                                        round(max(o for t, o in serie if warmup <= t < fin), 4)],
        "vehiculos_cargados": cargados,
        "vehiculos_por_clase": clases,
        "vehiculos_con_param_con_app": sum(1 for p in demanda.values() if "con_app" in p),
        "teletransportes_total": int(est.find("teleports").get("total")),
        "vehiculos_teletransportados": len(teletransportados),
        "porc_vehiculos_teletransportados": round(100 * len(teletransportados) / cargados, 3),
        "buscadores": len(buscadores),
        "buscadores_estacionados": len(estacionados),
        "buscadores_con_tiempo_busqueda": len(valores),
        "busqueda_s": {
            "media": round(statistics.mean(valores), 1) if valores else None,
            "mediana": round(statistics.median(valores), 1) if valores else None,
            "p90": round(valores[int(0.9 * (len(valores) - 1))], 1) if valores else None,
            "max": round(valores[-1], 1) if valores else None,
            "porc_mayor_60s": round(100 * sum(v > 60 for v in valores) / len(valores), 1)
            if valores else None,
        },
        "serie_ocupacion": serie,
        "tiempos_busqueda_s": {k: round(v, 1) for k, v in sorted(busq.items())},
    }
    (carpeta / "resumen.json").write_text(json.dumps(resumen, indent=1, ensure_ascii=False),
                                          encoding="utf-8")
    return resumen


def histograma(resumenes, destino):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5.5))
    todos = [v for r in resumenes for v in r["tiempos_busqueda_s"].values()]
    tope = max(todos) if todos else 1
    bins = [i * 15 for i in range(int(tope // 15) + 2)]
    colores = ["#1E63D6", "#FF9F1C", "#2E9E4F", "#C62828"]
    for r, c in zip(resumenes, colores):
        v = list(r["tiempos_busqueda_s"].values())
        b = r["busqueda_s"]
        ax.hist(v, bins=bins, alpha=0.55, color=c, edgecolor="white",
                label=f"{r['carpeta']}: n={len(v)}, media {b['media']} s, mediana {b['mediana']} s")
    ax.set_xlabel("Tiempo de búsqueda (s): desde que llega a su parkingArea objetivo hasta que estaciona")
    ax.set_ylabel("Vehículos")
    occ = ", ".join(f"{100 * r['ocupacion_media_hora_pico']:.1f} %" for r in resumenes)
    vh = resumenes[0]["parametros_demanda"].get("veh_hora", "?")
    ax.set_title(f"Búsqueda a ciegas (línea base) · {vh} veh/h · ocupación hora pico {occ}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    print(f"Histograma -> {destino}")


def grafica_ocupacion(resumenes, destino):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for r, c in zip(resumenes, ["#1E63D6", "#FF9F1C", "#2E9E4F", "#C62828"]):
        t = [s[0] / 60 for s in r["serie_ocupacion"]]
        o = [100 * s[1] for s in r["serie_ocupacion"]]
        ax.plot(t, o, color=c, label=f"{r['carpeta']} (media pico "
                                     f"{100 * r['ocupacion_media_hora_pico']:.1f} %)")
    warm = float(resumenes[0]["parametros_demanda"].get("warmup_s", 900)) / 60
    ax.axvspan(0, warm, color="#dddddd", alpha=0.6, label="warm-up")
    ax.axhspan(85, 95, color="#2E9E4F", alpha=0.12, label="objetivo 85-95 %")
    ax.set_xlabel("Tiempo de simulación (min)")
    ax.set_ylabel("Ocupación de los puestos (%)")
    ax.set_ylim(0, 100)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    print(f"Ocupación -> {destino}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpetas", nargs="+")
    ap.add_argument("--histograma")
    ap.add_argument("--ocupacion")
    args = ap.parse_args()
    resumenes = []
    for c in args.carpetas:
        r = analizar(c)
        resumenes.append(r)
        b = r["busqueda_s"]
        print(f"{r['carpeta']}: ocupación pico {100 * r['ocupacion_media_hora_pico']:.1f} % "
              f"(min-max {r['ocupacion_min_max_hora_pico']}), teletransportados "
              f"{r['vehiculos_teletransportados']}/{r['vehiculos_cargados']} "
              f"({r['porc_vehiculos_teletransportados']} %), buscadores estacionados "
              f"{r['buscadores_estacionados']}/{r['buscadores']}, búsqueda media {b['media']} s "
              f"mediana {b['mediana']} s p90 {b['p90']} s")
    if args.histograma:
        histograma(resumenes, args.histograma)
    if args.ocupacion:
        grafica_ocupacion(resumenes, args.ocupacion)


if __name__ == "__main__":
    main()
