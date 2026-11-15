"""Recorrido de la app paso a paso contra el backend vivo (uvicorn real, HTTP).

saldo 0 → no puede estacionar (debe recargar) → recarga → `/guia` → `POST /sesiones` → eventos
de ubicación y modo: se aleja a pie 40 m, vuelve y sale en vehículo 2 ventanas → la sesión llega
sola a `CERRADA` (el cierre lo decide `traci.cierre_remoto`, como el controlador), con el cobro
de `tarifa.json` y la retención liberada. Caso trampa: alejarse a pie **no** libera el puesto.

Nota: en el contrato `GET /guia` no recibe el usuario ni mira el saldo; la exigencia de recarga
la impone `POST /sesiones` con `SALDO_INSUFICIENTE` (y la app, leyendo `disponible`).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from comun.tarifa import cargar_tarifa, minutos_cobrados, monto_debito, monto_retencion
from traci.cierre_remoto import CierreRemoto, iso

pytestmark = pytest.mark.e2e

TARIFA = cargar_tarifa()
PARQUE_CALDERON = (-2.897308, -79.004488)
AUTO = (-2.8960, -79.0060)  # el auto, a unas cuadras del destino


def desplazar(lat: float, lon: float, norte_m: float = 0.0, este_m: float = 0.0) -> tuple:
    """Punto a `norte_m`/`este_m` metros de (lat, lon)."""
    return (lat + norte_m / 111_320.0, lon + este_m / (111_320.0 * math.cos(math.radians(lat))))


def ocupados(cliente, puesto_id: str) -> int:
    return next(p["ocupados"] for p in cliente.get("/puestos").json() if p["puesto_id"] == puesto_id)


def guiar(cliente) -> dict:
    r = cliente.get("/guia", params={"lat": AUTO[0], "lon": AUTO[1],
                                     "destino_lat": PARQUE_CALDERON[0], "destino_lon": PARQUE_CALDERON[1]})
    assert r.status_code == 200, r.text
    return r.json()


def estacionar(cliente, usuario, guia: dict, t0: datetime) -> dict:
    return cliente.post("/sesiones", json={"usuario_id": usuario.id, "placa": "ABC-1234",
                                           "puesto_id": guia["puesto_id"], "ts": iso(t0), "t_sim": 0})


def test_recorrido_completo_de_la_app(cliente, servidor, nuevo_usuario, token_sim):
    u = nuevo_usuario()
    t0 = datetime.now(timezone.utc).replace(microsecond=0)

    # 1) Saldo 0: la app debe pedir recargar; el backend no deja estacionar.
    b = u.billetera()
    assert b["saldo"] == 0 and b["disponible"] < monto_retencion(TARIFA)
    g = guiar(cliente)
    r = estacionar(cliente, u, g, t0)
    assert r.status_code == 402 and r.json()["error"]["codigo"] == "SALDO_INSUFICIENTE", r.text

    # 2) Recarga $5 (Payphone mock de Miguel, o la recarga directa marcada MOCK).
    b = u.recargar(5.0)
    assert b["saldo"] == pytest.approx(5.0) and b["disponible"] == pytest.approx(5.0)
    assert u.via == ("payphone_mock" if servidor.app.state.pagos_montado else "recarga_directa")
    if u.via == "payphone_mock":  # la recarga quedó con la referencia del pago, no "PRUEBA"
        assert [(m["tipo"], m["referencia_payphone"] != "PRUEBA") for m in b["movimientos"]] == [("recarga", True)]

    # 3) /guia devuelve un puesto libre.
    g = guiar(cliente)
    puesto = next(p for p in cliente.get("/puestos").json() if p["puesto_id"] == g["puesto_id"])
    assert puesto["ocupados"] < puesto["capacidad"]
    antes = puesto["ocupados"]

    # 4) Llega y estaciona: ESTACIONADO con la retención del bloque mínimo.
    r = estacionar(cliente, u, g, t0)
    assert r.status_code == 201, r.text
    ses = r.json()
    assert ses["estado"] == "ESTACIONADO"
    assert ses["retenido"] == pytest.approx(monto_retencion(TARIFA))
    assert u.billetera()["retenido"] == pytest.approx(monto_retencion(TARIFA))
    assert ocupados(cliente, g["puesto_id"]) == antes + 1

    ctrl = CierreRemoto(cliente, u.id, ses["sesion_id"], g["lat"], g["lon"], t0, token=token_sim)
    lat0, lon0 = g["lat"], g["lon"]

    # 5) Se aleja a pie 40 m (ventanas de 5 s) y hace diligencias 40 min.
    t = 0.0
    for d in (0, 5, 12, 20, 28, 35, 40):
        t += 5
        ctrl.ventana(t, *desplazar(lat0, lon0, norte_m=d), "a_pie" if d else "quieto")
    assert ctrl.estado == "A_PIE"
    for _ in range(4):
        t += 600
        ctrl.ventana(t, *desplazar(lat0, lon0, norte_m=40), "a_pie")
    # Caso trampa: alejarse a pie no libera el puesto ni cierra la sesión.
    assert cliente.get(f"/sesiones/{ses['sesion_id']}").json()["estado"] == "A_PIE"
    assert ocupados(cliente, g["puesto_id"]) == antes + 1

    # 6) Vuelve al auto.
    for d in (30, 20, 10, 3):
        t += 5
        ctrl.ventana(t, *desplazar(lat0, lon0, norte_m=d), "a_pie")
    t += 5
    ctrl.ventana(t, lat0, lon0, "quieto", velocidad_mps=0)
    assert ctrl.estado == "REGRESANDO"
    assert cliente.get(f"/sesiones/{ses['sesion_id']}").json()["estado"] == "REGRESANDO"

    # 7) Sale en vehículo: 2 ventanas → SALIENDO → CERRADA, sin que la app cierre nada.
    for este in (25, 70):
        t += 5
        ctrl.ventana(t, *desplazar(lat0, lon0, este_m=este), "vehiculo", velocidad_mps=8)
    assert ctrl.estado == "CERRADA"
    hacia = [tr.hacia for tr in ctrl.transiciones]
    # Entre 15 y 30 m la máquina puede ir y volver A_PIE ↔ REGRESANDO (umbrales del contrato §3).
    assert hacia[0] == "A_PIE" and hacia[-3:] == ["REGRESANDO", "SALIENDO", "CERRADA"], hacia

    final = cliente.get(f"/sesiones/{ses['sesion_id']}").json()
    assert final["estado"] == "CERRADA"
    minutos = t / 60
    assert final["minutos_reales"] == pytest.approx(minutos, abs=1e-3)
    assert final["minutos_cobrados"] == minutos_cobrados(minutos, TARIFA)
    assert ctrl.cierre["debitado"] == pytest.approx(monto_debito(minutos, TARIFA))

    b = u.billetera()
    assert b["retenido"] == 0, "la retención debe liberarse al cerrar"
    assert b["saldo"] == pytest.approx(5.0 - monto_debito(minutos, TARIFA))
    tipos = [m["tipo"] for m in b["movimientos"]]
    assert sorted(tipos) == sorted(["recarga", "retencion", "debito", "liberacion"])
    assert ocupados(cliente, g["puesto_id"]) == antes, "el puesto se libera al salir"


def test_alejarse_a_pie_no_libera_el_puesto(cliente, usuario_app, token_sim):
    """Caso trampa aislado: horas a pie lejos del auto, sin volver; nada se libera."""
    t0 = datetime.now(timezone.utc).replace(microsecond=0)
    g = guiar(cliente)
    antes = ocupados(cliente, g["puesto_id"])
    ses = estacionar(cliente, usuario_app, g, t0).json()
    ctrl = CierreRemoto(cliente, usuario_app.id, ses["sesion_id"], g["lat"], g["lon"], t0, token=token_sim)
    t = 0.0
    for d in (5, 15, 30, 60, 120, 250, 400, 400, 400):
        t += 5
        ctrl.ventana(t, *desplazar(g["lat"], g["lon"], norte_m=d), "a_pie")
    # Incluso un "vehiculo" aislado (bus, taxi corto) no basta: hacen falta 2 ventanas seguidas
    # y solo desde ESTACIONADO o REGRESANDO.
    t += 5
    ctrl.ventana(t, *desplazar(g["lat"], g["lon"], norte_m=600), "vehiculo", velocidad_mps=9)
    t += 5
    ctrl.ventana(t, *desplazar(g["lat"], g["lon"], norte_m=800), "vehiculo", velocidad_mps=9)
    assert ctrl.estado == "A_PIE" and ctrl.cierre is None
    assert cliente.get(f"/sesiones/{ses['sesion_id']}").json()["estado"] == "A_PIE"
    assert ocupados(cliente, g["puesto_id"]) == antes + 1
    assert usuario_app.billetera()["retenido"] == pytest.approx(monto_retencion(TARIFA))
