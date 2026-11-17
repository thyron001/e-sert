"""v1.4: `snapshot.puestos` suma el mapa estimado que manda el controlador (antes el visor quedaba en 0/610)."""

from __future__ import annotations

from backend.nucleo.mundo import EstadoMundo
from backend.nucleo.ocupacion import InfoPuesto, MapaOcupacion
from comun import esquemas as e

VERDAD = {"puestos": [], "estacionados": [], "falsas_liberaciones": []}


def _mundo() -> EstadoMundo:
    mapa = MapaOcupacion([InfoPuesto("pa_a_0", -2.897, -79.004, "A", 2),
                          InfoPuesto("pa_b_0", -2.898, -79.005, "B", 3)])
    mapa.ocupar("pa_a_0")  # una sesión creada por HTTP (teléfono real)
    return EstadoMundo(mapa)


def _paso(t: float, puestos=None) -> e.PasoSimulacion:
    cuerpo = {"t_sim": t, "ts": "2026-11-17T12:00:00Z", "vehiculos": [], "peatones": [], "verdad": VERDAD}
    if puestos is not None:
        cuerpo["puestos"] = puestos
    return e.PasoSimulacion.model_validate(cuerpo)


def _ocupados(difusion) -> dict:
    return {p.puesto_id: p.ocupados for p in difusion.snapshot.puestos}


def test_sin_puestos_del_controlador_queda_el_mapa_propio():
    assert _ocupados(_mundo().aplicar_paso(_paso(1.0))) == {"pa_a_0": 1, "pa_b_0": 0}


def test_suma_el_mapa_del_controlador_sin_pasar_la_capacidad():
    dif = _mundo().aplicar_paso(_paso(1.0, [{"puesto_id": "pa_a_0", "ocupados": 5, "capacidad": 2},
                                            {"puesto_id": "pa_b_0", "ocupados": 2, "capacidad": 3}]))
    assert _ocupados(dif) == {"pa_a_0": 2, "pa_b_0": 2}
    assert len(dif.snapshot.puestos) == 2  # el visor sigue recibiendo todos los puestos
