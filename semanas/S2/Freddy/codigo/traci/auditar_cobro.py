"""Auditoría del cobro de una corrida con app (S2-3).

Comprueba, para cada sesión cerrada:

1. Coherencia interna: `debitado == tarifa.costo(t_fin − t_inicio)`, con los tiempos de la sesión.
2. Error de facturación frente a la realidad: `debitado − tarifa.costo(t_fin_real − t_inicio_real)`,
   donde `t_inicio_real` y `t_fin_real` son el inicio y el fin de la parada del auto en
   `stop-output` de SUMO. La diferencia viene de cuánto tarda la máquina de estados en detectar
   la salida.

Y para todos los usuarios, que el libro cuadra: `saldo = Σ recargas − Σ débitos` y que la
retención neta es exactamente la de las sesiones que siguen abiertas (bloque mínimo por sesión).

Uso dentro del contenedor, desde `semanas/S2/Freddy/codigo`:

    python3 -m traci.auditar_cobro --escenario app50_s1
"""

from __future__ import annotations

import argparse
import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

from backend.nucleo import tarifa as tar

from .puente_nucleo import CODIGO  # noqa: F401  (configura sys.path para backend/comun)

AQUI = Path(__file__).resolve().parent
SALIDAS = AQUI / "salidas"
SUMO = AQUI / "escenario" / "tyrone" / "sumo"


def paradas_reales(stops_xml: Path) -> Dict[str, Tuple[float, float]]:
    """{vehId: (inicio, fin)} de la parada de estacionamiento de cada auto en `stop-output`."""
    salida: Dict[str, Tuple[float, float]] = {}
    for nodo in ET.parse(stops_xml).getroot().iter("stopinfo"):
        veh = nodo.get("id")
        if veh is None or nodo.get("parking") != "1" or nodo.get("ended") is None:
            continue
        salida.setdefault(veh, (float(nodo.get("started")), float(nodo.get("ended"))))
    return salida


def auditar(sesiones_csv: Path, libro_json: Path, stops_xml: Path) -> dict:
    filas = list(csv.DictReader(sesiones_csv.open(encoding="utf-8")))
    reales = paradas_reales(stops_xml)
    libro = json.loads(libro_json.read_text(encoding="utf-8"))

    coherencia_mal = 0
    errores = []
    sin_parada = 0
    for f in filas:
        t_ini, t_fin = float(f["t_inicio"]), float(f["t_fin"])
        debito = float(f["debitado"])
        if abs(debito - tar.costo((t_fin - t_ini) / 60)) > 0.005:  # tar.costo recibe minutos
            coherencia_mal += 1
        veh = f["usuario_id"].removeprefix("sim_")
        if veh not in reales:
            sin_parada += 1
            continue
        ini_real, fin_real = reales[veh]
        errores.append(debito - tar.costo((fin_real - ini_real) / 60))

    # Cada sesión abierta retiene exactamente un bloque mínimo; la retención neta de un usuario
    # debe ser un múltiplo exacto del bloque, y la suma de todos, el número de sesiones abiertas.
    bloque = tar.centavos(tar.retencion())
    libro_mal = []
    retencion_mal = []
    abiertas_libro = 0
    for usuario, c in libro.items():
        if c["recarga_centavos"] - c["debito_centavos"] != c["saldo_centavos"]:
            libro_mal.append(usuario)
        neta = c["retencion_neta_centavos"]
        if neta % bloque != 0:
            retencion_mal.append(usuario)
        abiertas_libro += neta // bloque
    abiertas_resumen = _abiertas_del_resumen(sesiones_csv.parent, sesiones_csv.stem.replace("sesiones_", ""))

    return {
        "sesiones_cerradas": len(filas),
        "coherencia_debito_fallos": coherencia_mal,
        "sesiones_sin_parada_en_sumo": sin_parada,
        "error_facturacion_medio_usd": round(sum(errores) / len(errores), 4) if errores else None,
        "error_facturacion_maximo_usd": round(max((abs(e) for e in errores), default=0.0), 4),
        "usuarios": len(libro),
        "libro_no_cuadra": libro_mal,
        "retencion_no_explicada": retencion_mal,
        "retencion_final_usd": round(sum(c["retencion_neta_centavos"] for c in libro.values()) / 100, 2),
        "sesiones_abiertas_en_libro": abiertas_libro,
        "sesiones_abiertas_en_resumen": abiertas_resumen,
    }


def _abiertas_del_resumen(carpeta: Path, escenario: str) -> Optional[int]:
    """Sesiones abiertas al final, según el resumen de la corrida."""
    ruta = carpeta / f"resumen_guiado_{escenario}.json"
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))["nucleo"]["sesiones_abiertas_al_final"]


def main(argv: Optional[Sequence[str]] = None) -> dict:
    ap = argparse.ArgumentParser(description="Auditoría del cobro de una corrida con app")
    ap.add_argument("--escenario", default="app50_s1")
    ap.add_argument("--stops", type=Path, default=None, help="stop-output de SUMO (por defecto, el del escenario)")
    args = ap.parse_args(argv)
    stops = args.stops or SUMO / "salidas" / args.escenario / "stops.xml"
    resultado = auditar(SALIDAS / f"sesiones_{args.escenario}.csv", SALIDAS / f"libro_{args.escenario}.json", stops)
    (SALIDAS / f"auditoria_cobro_{args.escenario}.json").write_text(
        json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    return resultado


if __name__ == "__main__":
    main()
