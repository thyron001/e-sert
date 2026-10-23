"""Carga y validación de `tarifa.json`, y cálculos de cobro del contrato v1 (§5).

El backend y el controlador TraCI usan solo estas funciones para cobrar; la app las replica
en TypeScript. Los montos se calculan en centavos enteros y se devuelven en USD.
"""

from __future__ import annotations

import json
import math
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional, Union

from .esquemas import Tarifa

RUTA_TARIFA = Path(__file__).resolve().parent / "tarifa.json"


def cargar_tarifa(ruta: Optional[Union[str, Path]] = None) -> Tarifa:
    """Lee `tarifa.json` (o la ruta dada) y la valida.

    Además del esquema, comprueba la coherencia entre parámetros. Lanza `ValueError` si algo
    no cuadra (pydantic.ValidationError también es un ValueError).
    """
    datos = json.loads(Path(ruta or RUTA_TARIFA).read_text(encoding="utf-8"))
    tarifa = Tarifa.model_validate(datos)
    if tarifa.cobro_minimo_min > tarifa.bloque_minimo_min:
        raise ValueError("cobro_minimo_min no puede ser mayor que bloque_minimo_min")
    if tarifa.aviso_tiempo_min >= tarifa.tiempo_maximo_min:
        raise ValueError("aviso_tiempo_min debe ser menor que tiempo_maximo_min")
    if tarifa.bloque_minimo_min % tarifa.fraccion_min != 0:
        raise ValueError("bloque_minimo_min debe ser múltiplo de fraccion_min")
    return tarifa


def a_centavos(usd: float) -> int:
    """Convierte USD a centavos enteros, redondeando mitad hacia arriba."""
    return int(Decimal(str(usd)).scaleb(2).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def costo_usd(minutos: float, tarifa: Tarifa) -> float:
    """Costo de `minutos` a la tarifa por hora, redondeado al centavo."""
    centavos = Decimal(str(minutos)) * Decimal(str(tarifa.valor_hora_usd)) * 100 / 60
    return float(centavos.quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 100)


def minutos_cobrados(minutos_reales: float, tarifa: Tarifa) -> int:
    """Minutos a cobrar: fracciones de `fraccion_min` hacia arriba, con mínimo de cobro."""
    fracciones = math.ceil(max(0.0, minutos_reales) / tarifa.fraccion_min - 1e-9)
    return max(tarifa.cobro_minimo_min, fracciones * tarifa.fraccion_min)


def monto_retencion(tarifa: Tarifa) -> float:
    """Monto que se retiene al confirmar la llegada (bloque mínimo)."""
    return costo_usd(tarifa.bloque_minimo_min, tarifa)


def monto_debito(minutos_reales: float, tarifa: Tarifa) -> float:
    """Monto que se debita al cerrar la sesión."""
    return costo_usd(minutos_cobrados(minutos_reales, tarifa), tarifa)


def tarjeta_sert_usd(minutos_reales: float, tarifa: Tarifa) -> float:
    """Lo que costaría con tarjetas SERT de papel: bloques completos, al menos uno."""
    bloques = max(1, math.ceil(max(0.0, minutos_reales) / tarifa.tarjeta_bloque_min - 1e-9))
    return round(bloques * costo_usd(tarifa.tarjeta_bloque_min, tarifa), 2)
