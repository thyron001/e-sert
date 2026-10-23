"""`GET /guia`: puesto libre más cercano al destino."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from comun import esquemas as e

from ...nucleo.ocupacion import MapaOcupacion
from .. import dependencias as dep
from .. import ejemplos as ej

router = APIRouter(tags=["guia"])

_c = ej.cargar("guia_consulta")


@router.get("/guia", response_model=e.Guia, summary="Asignar un puesto libre",
            responses={**ej.respuesta(200, "guia"), **ej.errores("SIN_PUESTOS_LIBRES", "VALIDACION")})
def guiar(
    lat: float = Query(..., ge=-90, le=90, description="Latitud del auto", examples=[_c["lat"]]),
    lon: float = Query(..., ge=-180, le=180, description="Longitud del auto", examples=[_c["lon"]]),
    destino_lat: float = Query(..., ge=-90, le=90, examples=[_c["destino_lat"]]),
    destino_lon: float = Query(..., ge=-180, le=180, examples=[_c["destino_lon"]]),
    mapa: MapaOcupacion = Depends(dep.mapa),
) -> e.Guia:
    """Nunca devuelve un puesto lleno. `distancia_m` es la distancia del puesto al destino."""
    consulta = e.ConsultaGuia(lat=lat, lon=lon, destino_lat=destino_lat, destino_lon=destino_lon)
    return mapa.guiar(consulta)
