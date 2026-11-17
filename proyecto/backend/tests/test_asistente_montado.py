"""El asistente de Miguel queda montado en la app principal (S4-U final): antes daba 404 en el VPS."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import Config, crear_app

pytest.importorskip("backend.asistente.router")


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # sin clave: responde por reglas
    csv = tmp_path / "puestos.csv"
    csv.write_text("puesto_id,edge,lane,calle,capacidad,lat,lon,x,y\npa_a_0,e,l,A,1,-2.897,-79.004,0,0\n",
                   encoding="utf-8")
    app = crear_app(Config(db_url="sqlite:///:memory:", puestos_csv=str(csv), token_sim="t", visor_dir=None))
    with TestClient(app) as c:
        yield c


def test_interpretar_responde_por_reglas(cliente):
    assert cliente.app.state.asistente_montado
    r = cliente.post("/api/v1/asistente/interpretar", json={"texto": "cerca de la Catedral Nueva una hora"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["fuente"] == "reglas"
    assert cuerpo["destino"]["nombre"] == "Catedral Nueva"
    assert cuerpo["duracion_min"] == 60


def test_aparece_en_openapi(cliente):
    assert "/api/v1/asistente/interpretar" in cliente.get("/openapi.json").json()["paths"]
