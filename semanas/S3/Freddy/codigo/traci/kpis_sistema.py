"""KPIs de sistema medidos dentro de la simulación (S3-1): falsas liberaciones, retardo de cierre,
error de facturación y precisión del mapa de ocupación.

`KPIsSistema(controlador, nucleo)` se registra como hook `on_paso` del `Controlador` y como oyente
de cierres del núcleo (`PuenteNucleo.al_cerrar`). Compara lo que cree el sistema con la verdad de
SUMO (`verdad.py`):

- **Falsa liberación:** la sesión pasa a `CERRADA` mientras `isStoppedParking(veh)` sigue en True.
  `falsas_lib_100 = 100 · n_falsas / n_sesiones` (sesiones cerradas, solo autos con app).
- **Retardo de cierre:** `t_cerrada − t_salida_real`, solo en cierres correctos.
- **Error de facturación:** `debitado − tarifa.costo(minutos_reales)`, con
  `minutos_reales = (t_salida_real − t_llegada_real) / 60`; `ahorro = tarjeta SERT − debitado`.
- **Precisión del mapa:** cada `intervalo_mapa_s`, por puesto, exactitud libre/lleno, MAE de
  ocupados y libres fantasma, contra la ocupación total y contra la de usuarios con app.

Interfaz para Tyrone (S3-Tyrone-1), estable: `resumen()`, `detalle_sesiones()` y `serie_mapa()`.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .puente_nucleo import tar  # tarifa del núcleo; puente_nucleo añade codigo/ al sys.path
from .verdad import VerdadSUMO

CLAVES_RESUMEN = (
    "falsas_lib_100", "n_sesiones", "n_falsas", "sin_cierre",
    "retardo_cierre_mediana_s", "retardo_cierre_p90_s",
    "error_fact_medio_usd", "error_fact_abs_max_usd", "ahorro_vs_tarjeta_medio_usd",
    "precision_mapa", "precision_mapa_app", "libres_fantasma_medio",
)
"""Claves de `resumen()` acordadas con Tyrone. No cambiarlas sin avisar."""

NAN = float("nan")


def _media(xs: List[float]) -> float:
    return statistics.fmean(xs) if xs else NAN


def _percentil(xs: List[float], q: float) -> float:
    """Percentil con interpolación lineal (igual que `numpy.percentile` por defecto)."""
    if not xs:
        return NAN
    s = sorted(xs)
    pos = (len(s) - 1) * q / 100
    i = int(math.floor(pos))
    j = min(i + 1, len(s) - 1)
    return s[i] + (s[j] - s[i]) * (pos - i)


def comparar_mapa(mapa: Dict[str, int], real: Dict[str, int], capacidad: Dict[str, int]) -> dict:
    """Compara puesto por puesto la ocupación del mapa con la real.

    `libre = ocupados < capacidad`. Devuelve exactitud del estado libre/lleno, MAE de ocupados y
    número de libres fantasma (libre en el mapa, lleno en la realidad).
    """
    aciertos, errores, fantasmas = 0, 0.0, 0
    for pid, cap in capacidad.items():
        m, r = mapa.get(pid, 0), real.get(pid, 0)
        libre_m, libre_r = m < cap, r < cap
        aciertos += libre_m == libre_r
        errores += abs(m - r)
        fantasmas += libre_m and not libre_r
    n = len(capacidad)
    return {"exactitud": aciertos / n if n else NAN, "mae": errores / n if n else NAN,
            "fantasmas": fantasmas}


class KPIsSistema:
    """KPIs de sistema de una corrida. Hook del `Controlador` y oyente de cierres del núcleo."""

    def __init__(self, controlador, nucleo, intervalo_mapa_s: float = 60, verdad: Optional[VerdadSUMO] = None,
                 intervalo_kpi_s: float = 10, publicador_kpi=None):
        self.ctrl = controlador
        self.nucleo = nucleo
        self.intervalo_mapa_s = intervalo_mapa_s
        self.intervalo_kpi_s = intervalo_kpi_s
        self.publicador_kpi = publicador_kpi  # `Publicador` con ruta /api/v1/sim/kpi (opcional)
        self.verdad = verdad
        if self.verdad is None:
            self.verdad = VerdadSUMO()
            controlador.agregar_hook(self.verdad.on_paso)
        controlador.agregar_hook(self.on_paso)
        nucleo.al_cerrar.append(self._al_cerrar)
        self.capacidad = {pid: p.capacidad for pid, p in nucleo.mapa.puestos.items()}
        self.sesiones: List[dict] = []
        self.falsas_sin_publicar: List[str] = []  # sesion_id cerrados en falso desde el último snapshot
        self.mapa: List[dict] = []
        self._proximo_mapa = 0.0
        self._proximo_kpi = 0.0

    # ------------------------------------------------------------------ hook y oyente

    def on_paso(self, ctrl, t: float) -> None:
        if t >= self._proximo_mapa:
            self._proximo_mapa = t + self.intervalo_mapa_s
            self.medir_mapa(ctrl, t)
        if self.publicador_kpi is not None and t >= self._proximo_kpi:
            self._proximo_kpi = t + self.intervalo_kpi_s
            self.publicador_kpi.publicar(self.mensaje_kpi(t))

    def _al_cerrar(self, fila: dict) -> None:
        """Cierre de una sesión en el núcleo: ¿el auto seguía estacionado en SUMO?"""
        veh = fila["usuario_id"].removeprefix("sim_")
        sigue = veh in self.ctrl.vehiculos and bool(self.ctrl.traci.vehicle.isStoppedParking(veh))
        self.sesiones.append({**fila, "veh": veh, "falsa": sigue})
        if sigue:
            self.falsas_sin_publicar.append(fila["sesion_id"])

    def medir_mapa(self, ctrl, t: float) -> dict:
        """Una muestra de precisión del mapa: total y solo usuarios con app."""
        real = self.verdad.ocupacion(ctrl, self.capacidad)
        mapa = {pid: self.nucleo.mapa.ocupados(pid) for pid in self.capacidad}
        total = comparar_mapa(mapa, {p: r[0] for p, r in real.items()}, self.capacidad)
        app = comparar_mapa(mapa, {p: r[1] for p, r in real.items()}, self.capacidad)
        fila = {"t_sim": t, "precision": total["exactitud"], "mae": total["mae"],
                "fantasmas": total["fantasmas"], "precision_app": app["exactitud"], "mae_app": app["mae"],
                "fantasmas_app": app["fantasmas"]}
        self.mapa.append(fila)
        return fila

    def tomar_falsas(self) -> List[str]:
        """Devuelve y vacía los `sesion_id` cerrados en falso desde la última llamada (para `verdad`)."""
        falsas, self.falsas_sin_publicar = self.falsas_sin_publicar, []
        return falsas

    # ------------------------------------------------------------------ resultados

    def _filas(self) -> List[dict]:
        """Una fila por sesión cerrada, con la verdad de SUMO y los errores calculados."""
        filas = []
        for s in self.sesiones:
            llegada, salida = self.verdad.estadia(s["veh"])
            fila = {**s, "t_llegada_real": llegada, "t_salida_real": salida, "minutos_reales_sumo": NAN,
                    "costo_ideal": NAN, "error_fact_usd": NAN, "tarjeta_sert_usd": NAN, "ahorro_usd": NAN,
                    "retardo_cierre_s": NAN}
            if llegada is not None and salida is not None:
                minutos = (salida - llegada) / 60
                ideal = tar.costo(minutos)
                tarjeta = tar.costo_tarjeta_sert(minutos)
                fila.update(minutos_reales_sumo=minutos, costo_ideal=ideal,
                            error_fact_usd=round(s["debitado"] - ideal, 2), tarjeta_sert_usd=tarjeta,
                            ahorro_usd=round(tarjeta - s["debitado"], 2))
                if not s["falsa"]:
                    fila["retardo_cierre_s"] = s["t_fin"] - salida
            filas.append(fila)
        return filas

    def resumen(self) -> dict:
        """KPIs agregados de la corrida (claves en `CLAVES_RESUMEN`, más algunas de apoyo)."""
        filas = self._filas()
        n = len(filas)
        n_falsas = sum(f["falsa"] for f in filas)
        retardos = [f["retardo_cierre_s"] for f in filas if not math.isnan(f["retardo_cierre_s"])]
        errores = [f["error_fact_usd"] for f in filas if not math.isnan(f["error_fact_usd"])]
        ahorros = [f["ahorro_usd"] for f in filas if not math.isnan(f["ahorro_usd"])]
        return {
            "falsas_lib_100": round(100 * n_falsas / n, 2) if n else NAN,
            "n_sesiones": n,
            "n_falsas": n_falsas,
            "sin_cierre": len(self.nucleo.abiertas),
            "retardo_cierre_mediana_s": _percentil(retardos, 50),
            "retardo_cierre_p90_s": _percentil(retardos, 90),
            "error_fact_medio_usd": _media(errores),
            "error_fact_abs_max_usd": max((abs(e) for e in errores), default=NAN),
            "ahorro_vs_tarjeta_medio_usd": _media(ahorros),
            "precision_mapa": _media([m["precision"] for m in self.mapa]),
            "precision_mapa_app": _media([m["precision_app"] for m in self.mapa]),
            "libres_fantasma_medio": _media([m["fantasmas"] for m in self.mapa]),
            # de apoyo (no forman parte de la interfaz acordada)
            "retardo_cierre_max_s": max(retardos, default=NAN),
            "error_fact_abs_medio_usd": _media([abs(e) for e in errores]),
            "n_cierre_manual": sum(f["motivo"] == "manual" for f in filas),
            "n_sin_estadia_real": n - len(errores),
            "mae_mapa": _media([m["mae"] for m in self.mapa]),
            "mae_mapa_app": _media([m["mae_app"] for m in self.mapa]),
            "libres_fantasma_app_medio": _media([m["fantasmas_app"] for m in self.mapa]),
            "n_muestras_mapa": len(self.mapa),
        }

    def detalle_sesiones(self):
        """`pandas.DataFrame` con una fila por sesión cerrada."""
        import pandas as pd

        return pd.DataFrame(self._filas())

    def serie_mapa(self):
        """`pandas.DataFrame` con una fila por muestra del mapa (cada `intervalo_mapa_s`)."""
        import pandas as pd

        return pd.DataFrame(self.mapa)

    def mensaje_kpi(self, t: float) -> dict:
        """Cuerpo de `{"tipo": "kpi"}` (contrato §6) con los nombres reservados; sin NaN."""
        r = self.resumen()
        valores = {
            "falsas_liberaciones_100": r["falsas_lib_100"],
            "retardo_cierre_medio_s": _media([f["retardo_cierre_s"] for f in self._filas()
                                              if not math.isnan(f["retardo_cierre_s"])]),
            "error_facturacion_medio_usd": r["error_fact_medio_usd"],
            "precision_mapa": r["precision_mapa"],
            "precision_mapa_app": r["precision_mapa_app"],
            "libres_fantasma": float(self.mapa[-1]["fantasmas"]) if self.mapa else NAN,
        }
        return {"tipo": "kpi", "t_sim": round(t, 1),
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "valores": {k: round(float(v), 4) for k, v in valores.items() if not math.isnan(v)}}
