"""Funciones puras de tarifa sobre `comun/tarifa.json`.

Es una capa fina sobre `comun/tarifa.py`, para que haya una sola fórmula de cobro en todo el
proyecto. Los montos internos van en centavos enteros (`*_centavos`).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from comun import tarifa as _t
from comun.esquemas import Tarifa


@lru_cache(maxsize=1)
def tarifa_vigente() -> Tarifa:
    """La tarifa de `comun/tarifa.json`, cargada y validada una sola vez."""
    return _t.cargar_tarifa()


def _tar(tarifa: Optional[Tarifa]) -> Tarifa:
    return tarifa or tarifa_vigente()


def minutos_cobrables(minutos_reales: float, tarifa: Optional[Tarifa] = None) -> int:
    """Redondea hacia arriba a `fraccion_min` y aplica `cobro_minimo_min`."""
    return _t.minutos_cobrados(minutos_reales, _tar(tarifa))


def costo(minutos_reales: float, tarifa: Optional[Tarifa] = None) -> float:
    """Lo que se cobra en USD por una estadía de `minutos_reales`."""
    return _t.monto_debito(minutos_reales, _tar(tarifa))


def costo_en_curso(minutos_reales: float, tarifa: Optional[Tarifa] = None) -> float:
    """Costo proporcional, sin fracciones ni mínimo (lo que ve el espejo minuto a minuto)."""
    return _t.costo_usd(max(0.0, minutos_reales), _tar(tarifa))


def costo_tarjeta_sert(minutos_reales: float, tarifa: Optional[Tarifa] = None) -> float:
    """Costo con tarjetas SERT de papel: bloques de 30 min pagados por adelantado."""
    return _t.tarjeta_sert_usd(minutos_reales, _tar(tarifa))


def retencion(tarifa: Optional[Tarifa] = None) -> float:
    """Monto retenido al iniciar la sesión (bloque mínimo)."""
    return _t.monto_retencion(_tar(tarifa))


def centavos(usd: float) -> int:
    """USD → centavos enteros (mitad hacia arriba)."""
    return _t.a_centavos(usd)


def usd(centavos_: int) -> float:
    """Centavos enteros → USD."""
    return centavos_ / 100
