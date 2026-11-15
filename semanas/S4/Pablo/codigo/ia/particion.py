"""
Partición fija de usuarios GeoLife y semillas SUMO para prueba.

    python -m ia.particion [ruta_ventanas.parquet]

Genera ia/particion_usuarios.json (inmutable una vez creado).
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DIR_IA = Path(__file__).resolve().parent
DIR_DATOS = DIR_IA / "datos" / "procesados"
RUTA_PARTICION = DIR_IA / "particion_usuarios.json"

SEMILLA_BASE = 2026
FRACCION_PRUEBA = 0.20
MIN_MINUTOS_CLASE = 10.0
MIN_TOTAL_PRUEBA_MIN = 60.0
SEMILLAS_SUMO_PRUEBA = [101, 102, 103, 104, 105]


def _minutos_por_usuario_clase(df: pd.DataFrame) -> pd.DataFrame:
    """Minutos aproximados por usuario y clase (paso 5s por ventana)."""
    conteo = df.groupby(["usuario_id", "modo_real"]).size().reset_index(name="n")
    conteo["minutos"] = conteo["n"] * 5.0 / 60.0
    return conteo


def _hash_lista(lst: list[str]) -> str:
    h = hashlib.sha256(json.dumps(sorted(lst), ensure_ascii=False).encode())
    return h.hexdigest()


def generar_particion(ruta_ventanas: Path | None = None) -> dict:
    ruta = ruta_ventanas or DIR_DATOS / "ventanas_geolife.parquet"
    df = pd.read_parquet(ruta, columns=["usuario_id", "modo_real"])
    usuarios = sorted(df["usuario_id"].unique())
    mins = _minutos_por_usuario_clase(df)

    elegibles = set(usuarios)
    for clase in ["a_pie", "vehiculo"]:
        con_min = mins[(mins["modo_real"] == clase) & (mins["minutos"] >= MIN_MINUTOS_CLASE)]
        elegibles &= set(con_min["usuario_id"])

    elegibles = sorted(elegibles)
    n_prueba = max(1, round(len(usuarios) * FRACCION_PRUEBA))

    semilla = SEMILLA_BASE
    for intento in range(20):
        rng = np.random.default_rng(semilla)
        candidatos = rng.choice(elegibles, size=min(n_prueba, len(elegibles)), replace=False)
        candidatos = sorted(candidatos.tolist())

        mins_prueba = mins[mins["usuario_id"].isin(candidatos)]
        total_por_clase = mins_prueba.groupby("modo_real")["minutos"].sum()

        ok = True
        for clase in ["a_pie", "vehiculo", "quieto"]:
            if total_por_clase.get(clase, 0) < MIN_TOTAL_PRUEBA_MIN:
                ok = False
                break

        if ok:
            break
        semilla += 1
    else:
        print(f"AVISO: no se cumplió el criterio de ≥{MIN_TOTAL_PRUEBA_MIN} min por clase tras 20 intentos")

    entrenamiento = sorted(set(usuarios) - set(candidatos))
    mins_prueba = mins[mins["usuario_id"].isin(candidatos)]
    resumen_prueba = mins_prueba.groupby("modo_real")["minutos"].sum().to_dict()

    particion = {
        "semilla": semilla,
        "criterio": f"≥{MIN_MINUTOS_CLASE} min a_pie o vehiculo por usuario; ≥{MIN_TOTAL_PRUEBA_MIN} min por clase en prueba",
        "usuarios_prueba": candidatos,
        "usuarios_entrenamiento": entrenamiento,
        "n_prueba": len(candidatos),
        "n_entrenamiento": len(entrenamiento),
        "semillas_sumo_prueba": SEMILLAS_SUMO_PRUEBA,
        "minutos_prueba_por_clase": {k: round(v, 1) for k, v in resumen_prueba.items()},
        "hash_usuarios_prueba": _hash_lista(candidatos),
        "intentos_semilla": semilla - SEMILLA_BASE + 1,
    }
    return particion


def guardar_particion(particion: dict, ruta: Path | None = None):
    ruta = ruta or RUTA_PARTICION
    with open(ruta, "w") as f:
        json.dump(particion, f, indent=2, ensure_ascii=False)
    print(f"Partición guardada: {ruta}")
    print(f"  Prueba: {particion['n_prueba']} usuarios, Entrenamiento: {particion['n_entrenamiento']}")
    print(f"  Semilla: {particion['semilla']} (intento {particion['intentos_semilla']})")
    print(f"  Minutos prueba: {particion['minutos_prueba_por_clase']}")
    print(f"  Hash: {particion['hash_usuarios_prueba']}")


if __name__ == "__main__":
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    p = generar_particion(ruta)
    guardar_particion(p)
