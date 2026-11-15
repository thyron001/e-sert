"""
Genera ia/tests/datos/ventanas_golden.json: 30 ventanas de prueba (10 por clase) con las salidas que da el
modelo congelado `rf_final`.

    python3 -m ia.datos.generar_golden

Composicion (semilla 2026, ventanas distintas):
  a_pie    5 de GeoLife (usuarios no vistos) + 5 de SUMO normal (sigma = 5 m)
  quieto   5 de GeoLife + 5 de SUMO normal
  vehiculo 4 de GeoLife + 3 de SUMO normal + 3 de SUMO trafico_lento
Si se reentrenara el modelo habria que regenerar este archivo (seria `rf_final_v2`).
"""
import json
from pathlib import Path

import numpy as np

from ia import inferencia
from ia.analisis_errores import _puntos, cargar_sumo
from ia.datos.ventanas_prueba import a_puntos, cargar

SALIDA = Path(__file__).resolve().parent.parent / "tests" / "datos" / "ventanas_golden.json"
PLAN = [("geolife", "a_pie", 5), ("geolife", "quieto", 5), ("geolife", "vehiculo", 4),
        ("sumo_normal", "a_pie", 5), ("sumo_normal", "quieto", 5), ("sumo_normal", "vehiculo", 3),
        ("sumo_trafico_lento", "vehiculo", 3)]


def main():
    rng = np.random.default_rng(2026)
    candidatas = {}
    for sub, modo in cargar(6000):
        candidatas.setdefault(("geolife", modo), []).append(a_puntos(sub))
    filas, arrs = cargar_sumo(101, 5, 40_000)
    for f, a in zip(filas, arrs):
        candidatas.setdefault((f"sumo_{f['escenario']}", f["modo_real"]), []).append(_puntos(a))

    golden = []
    for contexto, modo, n in PLAN:
        lista = candidatas[(contexto, modo)]
        for i in rng.choice(len(lista), n, replace=False):
            v = lista[int(i)]
            r = inferencia.clasificar(v)
            golden.append({"id": f"{contexto}_{modo}_{len(golden):02d}", "contexto": contexto, "modo_real": modo,
                           "ventana": v, "esperado": r})
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(golden))
    print(len(golden), "ventanas ->", SALIDA)


if __name__ == "__main__":
    main()
