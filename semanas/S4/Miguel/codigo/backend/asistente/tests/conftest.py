"""Configuración común de las pruebas del asistente.

- Registra la marca `llm` (pruebas reales contra la API de Anthropic).
- Antes y después de cada prueba vacía la caché y el cliente (`usar_cliente(None)`).
- En las pruebas que no son `llm` quita ANTHROPIC_API_KEY y apunta ARCHIVO_ENV a una ruta que
  no existe, para que ninguna prueba salga a la red ni lea un `.env` local.
- `ClienteFalso` imita `anthropic.Anthropic().messages.create(...)`.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from backend.asistente import interprete
from backend.asistente.destinos import normalizar


def pytest_configure(config):
    config.addinivalue_line("markers", "llm: prueba real contra la API de Anthropic; se omite sin ANTHROPIC_API_KEY")


@pytest.fixture(autouse=True)
def entorno_aislado(request, monkeypatch, tmp_path):
    """Sin clave ni .env en las pruebas normales; caché y cliente limpios antes y después."""
    if request.node.get_closest_marker("llm") is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ASISTENTE_MODELO", raising=False)
        monkeypatch.setattr(interprete, "ARCHIVO_ENV", tmp_path / "no-existe.env")
    interprete.usar_cliente(None)
    yield
    interprete.usar_cliente(None)


class ClienteFalso:
    """Cliente de Anthropic de mentira.

    respuestas: texto (se compara normalizado) → dict que irá en el `input` del tool_use.
    error: excepción que se lanza en cada llamada (timeout, red, 500…).
    stop_reason: "tool_use" por defecto; "refusal" para simular un rechazo.
    sin_tool_use: si es True, la respuesta trae solo un bloque de texto.
    """

    def __init__(
        self,
        respuestas: Optional[Dict[str, Dict[str, Any]]] = None,
        *,
        error: Optional[BaseException] = None,
        stop_reason: str = "tool_use",
        sin_tool_use: bool = False,
    ) -> None:
        self.respuestas = {normalizar(k): v for k, v in (respuestas or {}).items()}
        self.error = error
        self.stop_reason = stop_reason
        self.sin_tool_use = sin_tool_use
        self.llamadas: List[Dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._crear)

    def _crear(self, **kw: Any) -> SimpleNamespace:
        self.llamadas.append(kw)
        if self.error is not None:
            raise self.error
        texto = kw["messages"][-1]["content"]
        entrada = self.respuestas.get(normalizar(texto), {"destino": None, "duracion_min": None})
        if self.sin_tool_use:
            contenido = [SimpleNamespace(type="text", text="No puedo ayudar con eso.")]
        else:
            contenido = [SimpleNamespace(type="tool_use", name="registrar_intencion", input=dict(entrada), id="toolu_1")]
        return SimpleNamespace(
            content=contenido,
            stop_reason=self.stop_reason,
            model="claude-haiku-5-5",
            usage=SimpleNamespace(input_tokens=350, output_tokens=25),
        )


@pytest.fixture
def cliente_falso():
    """Fábrica: crea un ClienteFalso y lo instala como cliente del intérprete."""

    def _fabrica(respuestas=None, **kw) -> ClienteFalso:
        cliente = ClienteFalso(respuestas, **kw)
        interprete.usar_cliente(cliente)
        return cliente

    return _fabrica
