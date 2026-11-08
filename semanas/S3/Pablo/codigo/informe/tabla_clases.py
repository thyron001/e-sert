"""
Tabla de ventanas por clase y fuente -> ia/reportes/clases_por_fuente.csv (Tabla 1) y ia/reportes/sensibilidad_resumen.csv (macro-F1 medio por sigma de entrenamiento).

    python3 informe/tabla_clases.py

Lee los parquet de S2 (ignorados por git, en semanas/S2/Pablo/codigo/ia/datos/procesados/) y las
metricas de generalizacion (soporte por clase de los escenarios SUMO).
"""
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ.parents[2] / "S2/Pablo/codigo/ia/datos/procesados"
CLASES = ["a_pie", "quieto", "vehiculo"]


def conteo(parquet: str) -> dict:
    t = pq.read_table(PROC / parquet, columns=["modo_real"]).to_pandas()["modo_real"].value_counts()
    return {c: int(t.get(c, 0)) for c in CLASES}


def main():
    filas = [("Entrenamiento (GeoLife + SUMO simulado + aumento)", "entrenamiento", conteo("ventanas_v2.parquet")),
             ("GeoLife, 10 usuarios no vistos", "prueba", conteo("ventanas_prueba_geolife.parquet"))]
    m = json.loads((RAIZ / "ia/reportes/metricas_generalizacion.json").read_text())["fuentes"]
    for clave, nombre in (("sumo_normal", "SUMO normal (σ = 5 m)"), ("sumo_trafico_lento", "SUMO tráfico lento (σ = 5 m)"),
                          ("sumo_peaton_rapido", "SUMO peatón rápido (σ = 5 m)")):
        pc = m[clave]["rf"]["por_clase"]
        filas.append((nombre, "prueba", {c: int(pc[c]["support"]) for c in CLASES}))
    df = pd.DataFrame([{"fuente": n, "uso": u, **c, "total": sum(c.values())} for n, u, c in filas])
    destino = RAIZ / "ia/reportes/clases_por_fuente.csv"
    df.to_csv(destino, index=False)
    print(df.to_string())
    sens = pd.read_csv(RAIZ / "ia/reportes/sensibilidad_sigma.csv")
    res = sens.groupby("sigma_entr", sort=False)["macro_f1"].mean().round(4).reset_index()
    res.to_csv(RAIZ / "ia/reportes/sensibilidad_resumen.csv", index=False)
    print(res.to_string())


if __name__ == "__main__":
    main()
