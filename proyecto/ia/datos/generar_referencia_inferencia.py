"""
Genera ia/tests/datos/referencia_s2.json: ventanas limpias de GeoLife con la
prediccion de la ruta original de S2 (pandas + caracteristicas.extraer + pipeline sklearn).

    python -m ia.datos.generar_referencia_inferencia
"""
import json
from pathlib import Path

import joblib
import numpy as np

from ia.caracteristicas import NOMBRES_FEATURES, extraer
from ia.datos.ventanas_prueba import a_puntos, cargar

RAIZ = Path(__file__).resolve().parent.parent
N_VENTANAS = 150


def main():
    vs = cargar(N_VENTANAS)
    pipe = joblib.load(RAIZ / "modelos/rf_v1.joblib")
    salida = []
    for sub, _ in vs:
        f = extraer(sub)
        X = np.array([[f[n] for n in NOMBRES_FEATURES]])
        p = pipe.predict_proba(X)[0]
        i = int(np.argmax(p))
        pts = a_puntos(sub)
        salida.append({"ventana": pts, "modo": str(pipe.classes_[i]), "confianza": float(p[i])})
    ruta = RAIZ / "tests/datos/referencia_s2.json"
    ruta.write_text(json.dumps(salida))
    print(len(salida), "ventanas ->", ruta)


if __name__ == "__main__":
    main()
