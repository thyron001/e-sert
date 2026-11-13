"""Los cuatro errores de negocio del contrato, contra el backend vivo.

Cada uno responde **exactamente** `{"error": {"codigo", "mensaje"[, "detalle"]}}` con el código
HTTP de `comun.esquemas.HTTP_POR_CODIGO` y el header `X-Contrato-Version: 1`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from comun import esquemas as e

pytestmark = pytest.mark.e2e

HTTP_ESPERADO = {"SALDO_INSUFICIENTE": 402, "SESIONES_BLOQUEADAS": 403, "SESION_NO_EXISTE": 404,
                 "PUESTO_LLENO": 409}


def ahora() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def comprobar_error(r, codigo: str) -> dict:
    assert r.status_code == HTTP_ESPERADO[codigo] == e.HTTP_POR_CODIGO[e.CodigoError(codigo)], r.text
    assert r.headers["x-contrato-version"] == "1"
    assert r.headers["content-type"].startswith("application/json")
    cuerpo = r.json()
    assert set(cuerpo) == {"error"}, cuerpo
    assert {"codigo", "mensaje"} <= set(cuerpo["error"]) <= {"codigo", "mensaje", "detalle"}, cuerpo
    assert cuerpo["error"]["codigo"] == codigo
    assert isinstance(cuerpo["error"]["mensaje"], str) and cuerpo["error"]["mensaje"]
    e.CuerpoError.model_validate(cuerpo)
    return cuerpo["error"]


def iniciar(cliente, usuario: str, puesto: str, placa: str = "ABC-1234"):
    return cliente.post("/sesiones", json={"usuario_id": usuario, "placa": placa, "puesto_id": puesto,
                                           "ts": ahora()})


def puesto_mas_chico(cliente) -> dict:
    return min(cliente.get("/puestos").json(), key=lambda p: (p["capacidad"], p["puesto_id"]))


def test_saldo_insuficiente_402(cliente, nuevo_usuario):
    u = nuevo_usuario()
    err = comprobar_error(iniciar(cliente, u.id, puesto_mas_chico(cliente)["puesto_id"]), "SALDO_INSUFICIENTE")
    assert err["detalle"]["disponible"] == 0


def test_puesto_lleno_409(cliente, nuevo_usuario):
    p = puesto_mas_chico(cliente)
    for i in range(p["capacidad"] - p["ocupados"]):
        u = nuevo_usuario()
        u.recargar(5.0)
        assert iniciar(cliente, u.id, p["puesto_id"], placa=f"PLL-{i:04d}").status_code == 201
    otro = nuevo_usuario()
    otro.recargar(5.0)
    comprobar_error(iniciar(cliente, otro.id, p["puesto_id"], placa="PLL-9999"), "PUESTO_LLENO")
    assert otro.billetera()["retenido"] == 0, "un rechazo no debe retener saldo"


def test_sesion_no_existe_404(cliente, token_sim):
    fantasma = f"ses_{uuid.uuid4()}"
    comprobar_error(cliente.get(f"/sesiones/{fantasma}"), "SESION_NO_EXISTE")
    comprobar_error(cliente.post(f"/sesiones/{fantasma}/cerrar",
                                 json={"ts": ahora(), "motivo": "manual"}), "SESION_NO_EXISTE")
    comprobar_error(cliente.post(f"/sesiones/{fantasma}/transicion", headers=token_sim,
                                 json={"estado": "A_PIE", "ts": ahora()}), "SESION_NO_EXISTE")


def test_sesiones_bloqueadas_403(cliente, nuevo_usuario):
    """Saldo $5 y una sesión cerrada a mano tras 11,5 h: se debita el tiempo real ($5,75) → saldo < 0."""
    u = nuevo_usuario()
    u.recargar(5.0)
    p = puesto_mas_chico(cliente)
    inicio = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    r = cliente.post("/sesiones", json={"usuario_id": u.id, "placa": "BLQ-0001", "puesto_id": p["puesto_id"],
                                        "ts": inicio.isoformat()})
    assert r.status_code == 201, r.text
    fin = inicio.replace(hour=19, minute=30)
    r = cliente.post(f"/sesiones/{r.json()['sesion_id']}/cerrar",
                     json={"ts": fin.isoformat(), "motivo": "manual"})
    assert r.status_code == 200, r.text
    b = u.billetera()
    assert b["saldo"] < 0 and b["bloqueada"], b
    comprobar_error(iniciar(cliente, u.id, p["puesto_id"], placa="BLQ-0002"), "SESIONES_BLOQUEADAS")


def test_contrato_incompatible_400(servidor):
    """Extra: una app con otro contrato recibe el mismo formato de error."""
    import httpx

    r = httpx.get(f"{servidor.url}/api/v1/puestos", headers={"X-Contrato-Version": "2"})
    assert r.status_code == 400 and r.json()["error"]["codigo"] == "CONTRATO_INCOMPATIBLE"
