"""
Genera ia/tests/datos/referencia_sklearn_final.json: ventanas limpias de GeoLife (usuarios no vistos) con la
prediccion de la ruta original (pandas + caracteristicas.extraer + pipeline de scikit-learn) de `rf_final`.

    python3 -m ia.datos.generar_referencia_inferencia

Las ventanas se toman de ia/tests/datos/referencia_sklearn_final.json si ya existe (asi no hay que releer
GeoLife); si no, se muestrean de los usuarios de prueba. Sirve para comprobar que el servicio de inferencia
(numpy, sin pandas) da lo mismo que scikit-learn.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ia.caracteristicas import NOMBRES_FEATURES, extraer

RAIZ = Path(__file__).resolve().parent.parent
RUTA = RAIZ / "tests/datos/referencia_sklearn_final.json"
N_VENTANAS = 150


def ventanas():
    if RUTA.exists():
        return [c["ventana"] for c in json.loads(RUTA.read_text())]
    from ia.datos.ventanas_prueba import a_puntos, cargar

    return [a_puntos(sub) for sub, _ in cargar(N_VENTANAS)]


def main():
    pipe = joblib.load(RAIZ / "modelos/rf_final.joblib")
    salida = []
    for pts in ventanas():
        df = pd.DataFrame(pts)
        df["precision_m"] = df["precision_m"].astype(float)
        f = extraer(df)
        X = np.array([[f[n] for n in NOMBRES_FEATURES]])
        p = pipe.predict_proba(X)[0]
        i = int(np.argmax(p))
        salida.append({"ventana": pts, "modo": str(pipe.classes_[i]), "confianza": float(p[i])})
    RUTA.write_text(json.dumps(salida))
    print(len(salida), "ventanas ->", RUTA)


if __name__ == "__main__":
    main()
