"""
Línea base de un solo atributo: árbol de decisión sobre `desplazamiento_neto` (la característica que más usa el RF).

    python3 -m ia.linea_base_desplazamiento

Entrena con las mismas ventanas de `rf_final` (ia/datos/procesados/ventanas_final.parquet) y evalúa en los usuarios
de GeoLife no vistos y en SUMO normal (sigma = 5 m, semillas 101 a 105, las mismas ventanas que rf_final). Sirve para saber cuánto aporta el Random Forest
más allá de un umbral de desplazamiento. Escribe ia/reportes/linea_base_desplazamiento.json.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
from sklearn.tree import DecisionTreeClassifier

from ia import inferencia
from ia.analisis_errores import cargar_sumo
from ia.caracteristicas import NOMBRES_FEATURES
from ia.evaluar_final import PROCESADOS, usar_modelo
from ia.inferencia import _extraer_features_lote

AQUI = Path(__file__).resolve().parent
CLASES = ["a_pie", "quieto", "vehiculo"]


def main():
    usar_modelo(None)
    j = NOMBRES_FEATURES.index("desplazamiento_neto")
    d = pd.read_parquet(AQUI / "datos/procesados/ventanas_final.parquet", columns=["desplazamiento_neto", "modo_real"])
    arbol = DecisionTreeClassifier(max_depth=3, class_weight="balanced", random_state=42)
    arbol.fit(d[["desplazamiento_neto"]].to_numpy(), d["modo_real"])
    umbrales = sorted(float(t) for t in arbol.tree_.threshold if t > -2)

    geo = pd.read_parquet(PROCESADOS / "ventanas_prueba_geolife.parquet")
    part = json.loads((AQUI / "particion_usuarios.json").read_text())
    geo = geo[geo["usuario_id"].isin(part["usuarios_prueba"])]
    f_geo = f1_score(geo["modo_real"], arbol.predict(geo[["desplazamiento_neto"]].to_numpy()), labels=CLASES, average="macro")

    y, X = [], []
    for sem in (101, 102, 103, 104, 105):
        filas, arrs = cargar_sumo(sem, 5, 60_000)
        for f, a, feats in zip(filas, arrs, _extraer_features_lote(arrs)):
            if f["escenario"] == "normal" and feats is not None:
                y.append(f["modo_real"])
                X.append(feats[j])
    f_sumo = f1_score(y, arbol.predict(np.array(X).reshape(-1, 1)), labels=CLASES, average="macro")
    m = json.loads((AQUI / "reportes/metricas_rf_final.json").read_text())
    out = {"descripcion": "arbol de decision de profundidad 3 sobre desplazamiento_neto, entrenado con las ventanas de rf_final",
           "umbrales_desplazamiento_m": [round(u, 1) for u in umbrales],
           "geolife_prueba": {"f1_macro": float(f_geo), "n_ventanas": int(len(geo))},
           "sumo_normal_sigma5_semillas_101_105": {"f1_macro": float(f_sumo), "n_ventanas": len(y)},
           "rf_final": {"geolife_prueba": m["fuentes"]["geolife_prueba"]["rf_final"]["macro_f1"],
                        "sumo_normal": m["fuentes"]["sumo_normal"]["rf_final"]["macro_f1"]}}
    (AQUI / "reportes/linea_base_desplazamiento.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
