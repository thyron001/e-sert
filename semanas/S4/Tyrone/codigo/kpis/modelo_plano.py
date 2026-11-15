"""RF de Pablo como arrays planos de numpy, para usarlo dentro del contenedor sin sklearn.

El contenedor `van3twin` tiene Python 3.10 y no hay `scikit-learn==1.9.1` para esa versión, así
que `joblib.load(rf_final.joblib)` no funciona ahí. En la computadora (con el `.venv` de `ia`)
se exporta el `BosquePlano` de Pablo a un `.npz`:

    proyecto/ia/.venv/bin/python -m kpis.modelo_plano exportar \
        --joblib kpis/externo/ia/modelos/rf_final.joblib --salida kpis/externo/rf_final.plano.npz

y dentro del contenedor `cargar(npz)` reconstruye el mismo objeto (mismas probabilidades) sin
sklearn. `instalar(npz)` sustituye la carga perezosa de `ia.inferencia` por este objeto.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

CAMPOS = ("_izq", "_der", "_feat", "_umbral", "_valor", "_raices", "classes_")


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def exportar(joblib_path: Path, salida: Path) -> dict:
    """Carga el joblib con sklearn, lo compila con `BosquePlano` y guarda los arrays en `.npz`."""
    sys.path.insert(0, str(joblib_path.resolve().parents[2]))  # carpeta que contiene `ia/`
    from joblib import load
    from ia.bosque_plano import BosquePlano

    plano = BosquePlano(load(joblib_path))
    datos = {c: getattr(plano, c) for c in CAMPOS}
    datos["classes_"] = np.asarray(plano.classes_).astype(str)  # sin objetos: se carga sin pickle
    datos["_medianas"] = plano._medianas if plano._medianas is not None else np.array([])
    datos["_prof"] = np.array(plano._prof)
    datos["n_arboles"] = np.array(plano.n_arboles)
    np.savez_compressed(salida, **datos)
    info = {"joblib": joblib_path.name, "joblib_sha256": sha256(joblib_path), "npz_sha256": sha256(salida),
            "n_arboles": int(plano.n_arboles), "profundidad": int(plano._prof)}
    salida.with_suffix(".json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


class BosqueNpz:
    """Mismo algoritmo que `ia.bosque_plano.BosquePlano.predict_proba`, leído de un `.npz`."""

    def __init__(self, npz: Path):
        d = np.load(npz, allow_pickle=False)
        for c in CAMPOS:
            setattr(self, c, d[c])
        med = d["_medianas"]
        self._medianas = med if med.size else None
        self._prof = int(d["_prof"])
        self.n_arboles = int(d["n_arboles"])

    def predict_proba(self, X):
        X = np.asarray(X, dtype=np.float64)
        if self._medianas is not None:
            X = np.where(np.isnan(X), self._medianas, X)
        X = X.astype(np.float32)
        n = X.shape[0]
        nodo = np.broadcast_to(self._raices, (n, self.n_arboles)).copy()
        filas = np.arange(n)[:, None]
        for _ in range(self._prof):
            xv = X[filas, self._feat[nodo]]
            nodo = np.where(xv <= self._umbral[nodo], self._izq[nodo], self._der[nodo])
        return self._valor[nodo].mean(axis=1, dtype=np.float64)

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


def instalar(npz: Path) -> BosqueNpz:
    """Hace que `ia.inferencia` use el bosque del `.npz` (el paquete `ia` ya debe estar en `sys.path`)."""
    import ia.inferencia as inf

    modelo = BosqueNpz(npz)
    inf._cargar_modelo = lambda: modelo  # la inferencia llama a la función global en cada uso
    return modelo


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("exportar")
    ex.add_argument("--joblib", required=True, type=Path)
    ex.add_argument("--salida", required=True, type=Path)
    args = ap.parse_args(argv)
    print(json.dumps(exportar(args.joblib, args.salida), indent=2))


if __name__ == "__main__":
    main()
