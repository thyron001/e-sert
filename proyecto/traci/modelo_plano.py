"""RF de Pablo (`rf_final`) como arrays de numpy, para clasificar con él dentro del contenedor.

El contenedor `van3twin` tiene Python 3.10 y no hay `scikit-learn==1.9.1` (con la que Pablo
entrenó `rf_final`) para esa versión: `joblib.load` falla y `ia.inferencia` cae al umbral, que
con ruido de GPS de 5 m libera puestos en falso. El bosque se exporta una vez en la computadora,
donde sí está sklearn, a un `.npz` sin pickle:

    proyecto/ia/.venv/bin/python -m traci.modelo_plano exportar          # desde semanas/S4/Freddy/codigo

y en el contenedor `instalar_si_falta()` (lo llama `clasificacion.cargar_inferencia`) hace que
`ia.inferencia` use ese bosque cuando su propio `_cargar_modelo()` no pudo cargar el joblib.
Mismo algoritmo que `ia.bosque_plano.BosquePlano.predict_proba` (mismas probabilidades).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

AQUI = Path(__file__).resolve().parent
# En `proyecto/` el modelo vive en `ia/modelos/` (versionado, S4-U final); en la copia de semana de
# Freddy, en `traci/escenario/pablo/`.
_NPZ_PROYECTO = AQUI.parent / "ia" / "modelos" / "rf_final.plano.npz"
_NPZ_SEMANA = AQUI / "escenario" / "pablo" / "rf_final.plano.npz"
IA_PABLO = AQUI.parent / "ia" if (AQUI.parent / "ia" / "inferencia.py").exists() else AQUI / "escenario" / "pablo" / "ia"
NPZ_DEFECTO = _NPZ_PROYECTO if _NPZ_PROYECTO.exists() or not _NPZ_SEMANA.exists() else _NPZ_SEMANA
CAMPOS = ("_izq", "_der", "_feat", "_umbral", "_valor", "_raices", "classes_")


def ruta_npz() -> Path:
    """`$ESERT_RF_PLANO`, o `ia/modelos/rf_final.plano.npz` (proyecto), o `traci/escenario/pablo/` (semana)."""
    env = os.environ.get("ESERT_RF_PLANO", "")
    return Path(env) if env else NPZ_DEFECTO


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def exportar(joblib_path: Path, salida: Path) -> dict:
    """Carga el joblib con sklearn, lo compila con `BosquePlano` de Pablo y guarda los arrays."""
    sys.path.insert(0, str(joblib_path.resolve().parents[2]))  # carpeta que contiene `ia/`
    from joblib import load
    from ia.bosque_plano import BosquePlano

    plano = BosquePlano(load(joblib_path))
    datos = {c: getattr(plano, c) for c in CAMPOS}
    datos["classes_"] = np.asarray(plano.classes_).astype(str)  # sin objetos: se carga sin pickle
    datos["_medianas"] = plano._medianas if plano._medianas is not None else np.array([])
    datos["_prof"] = np.array(plano._prof)
    datos["n_arboles"] = np.array(plano.n_arboles)
    salida.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(salida, **datos)
    info = {"joblib": joblib_path.name, "joblib_sha256": _sha256(joblib_path), "npz_sha256": _sha256(salida),
            "n_arboles": int(plano.n_arboles), "profundidad": int(plano._prof)}
    salida.with_suffix(".json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


class BosqueNpz:
    """`predict_proba` del bosque plano, leído de un `.npz` (sin sklearn ni pickle)."""

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


def instalar_si_falta(inf) -> Optional[str]:
    """Envuelve `ia.inferencia._cargar_modelo` (módulo `inf`) para que use el `.npz` si el joblib
    no carga. Devuelve la ruta del `.npz` instalado, o None si no hay `.npz` o `inf` no es la
    inferencia de Pablo.

    La decisión se toma en cada llamada, no al instalar: `correr_kpis` define
    `ESERT_CLASIFICADOR` después de importar la inferencia, y con `umbral` no se usa ningún RF.
    """
    original = getattr(inf, "_cargar_modelo", None)
    if original is None or getattr(original, "_plano", False):
        return None
    npz = ruta_npz()
    if not npz.is_file():
        return None
    cache = {}

    def cargar():
        if os.environ.get("ESERT_CLASIFICADOR", "").lower() == "umbral":
            return None
        try:
            modelo = original()
        except Exception:  # un joblib incompatible no debe impedir usar el .npz
            modelo = None
        if modelo is not None:
            return modelo
        if "npz" not in cache:
            cache["npz"] = BosqueNpz(npz)
            log.info("RF de %s (el joblib no cargó en este Python)", npz.name)
        return cache["npz"]

    cargar._plano = True
    inf._cargar_modelo = cargar  # la inferencia llama a la función global en cada uso
    return str(npz)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("exportar", help="joblib → .npz (en la computadora, con sklearn 1.9.1)")
    ex.add_argument("--joblib", type=Path, default=IA_PABLO / "modelos" / "rf_final.joblib")
    ex.add_argument("--salida", type=Path, default=NPZ_DEFECTO)
    args = ap.parse_args(argv)
    print(json.dumps(exportar(args.joblib, args.salida), indent=2))


if __name__ == "__main__":
    main()
