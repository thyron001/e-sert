"""
Graba episodios de parqueo completos desde SUMO (estacionar -> caminar -> volver -> manejar).

Se ejecuta DENTRO del contenedor van3twin, reutilizando el controlador y los peatones de Freddy
(`proyecto/traci/`, solo lectura). Por cada auto de busqueda que estaciona guarda, cada segundo,
la posicion LIMPIA del telefono (el peatón si camina, el auto si está dentro) y su modo real.
El ruido GPS se aplica despues (`ia/ruido.py`), asi se puede barrer sigma sin repetir SUMO.

    docker exec -w /home/vanet/results/e-sert/semanas/S3/Pablo/codigo van3twin \
        bash -lc "python3 ia/grabar_episodios.py --semilla 101 --hasta 2400"

Salida: ia/sumo/salidas/episodios_s<semilla>.csv (ignorada por git). Solo usa la biblioteca estandar.
"""
import argparse
import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[5]  # raiz del repo (o results/e-sert en el contenedor)
sys.path.insert(0, str(RAIZ / "proyecto"))

from traci.controlador import ConfigControlador, Controlador  # noqa: E402
from traci.gps import modo_real_persona, modo_real_vehiculo  # noqa: E402
from traci.peatones import GestorPeatones  # noqa: E402

SALIDAS = Path(__file__).resolve().parent / "sumo" / "salidas"
CFG = RAIZ / "proyecto" / "sumo" / "centro_base.sumocfg"
COLUMNAS = ["usuario_id", "t", "lat", "lon", "modo_real", "puesto_lat", "puesto_lon", "semilla"]


class GrabadorEpisodios:
    """Hook `on_paso`: una fila limpia por segundo y por sesion, desde que el auto estaciona."""

    def __init__(self, ruta: Path, semilla: int):
        self.semilla = semilla
        self.activos: dict = {}
        self.n_episodios = 0
        self._f = ruta.open("w", newline="", encoding="utf-8")
        self._w = csv.writer(self._f)
        self._w.writerow(COLUMNAS)

    def on_paso(self, ctrl, t: float) -> None:
        tr = ctrl.traci
        tc = tr.constants
        for veh in tr.simulation.getParkingStartingVehiclesIDList():
            if veh in self.activos or tr.vehicle.getParameter(veh, "clase") != "busca":
                continue
            x, y = tr.vehicle.getPosition(veh)
            self.activos[veh] = ctrl.a_geo(x, y)
            self.n_episodios += 1
        for veh in list(self.activos):
            if veh not in ctrl.vehiculos:
                del self.activos[veh]
                continue
            ped = f"ped_{veh}"
            if ped in ctrl.personas and tr.person.getStage(ped).description != "en_auto":
                x, y = ctrl.personas[ped][tc.VAR_POSITION]
                modo = modo_real_persona(tr.person.getStage(ped).type)
            else:
                datos = ctrl.vehiculos[veh]
                x, y = datos[tc.VAR_POSITION]
                modo = modo_real_vehiculo(ctrl.estacionado(datos))
            lat, lon = ctrl.a_geo(x, y)
            if lat != lat or lon != lon:  # NaN
                continue
            p = self.activos[veh]
            self._w.writerow([f"sim_{veh}", round(t, 1), round(lat, 7), round(lon, 7), modo,
                              round(p[0], 7), round(p[1], 7), self.semilla])

    def cerrar(self) -> None:
        self._f.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--semilla", type=int, required=True)
    ap.add_argument("--hasta", type=float, default=2400)
    args = ap.parse_args()
    SALIDAS.mkdir(parents=True, exist_ok=True)
    ruta = SALIDAS / f"episodios_s{args.semilla}.csv"
    # el dataset del RF se grabó con todos los conductores caminando
    peatones = GestorPeatones(CFG.parent / "demanda" / "destinos.csv", semilla=args.semilla, solo_web=False)
    grab = GrabadorEpisodios(ruta, args.semilla)
    config = ConfigControlador(cfg=CFG, semilla=args.semilla, etiqueta=f"s3_episodios_{args.semilla}")
    try:
        with Controlador(config) as ctrl:
            ctrl.agregar_hook(peatones.on_paso)
            ctrl.agregar_hook(grab.on_paso)
            ctrl.correr(args.hasta)
    finally:
        grab.cerrar()
    print(f"semilla {args.semilla}: {grab.n_episodios} episodios -> {ruta}")


if __name__ == "__main__":
    main()
