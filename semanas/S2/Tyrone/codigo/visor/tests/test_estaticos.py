"""Tests 4 y 5: la página del visor se sirve y solo usa rutas relativas (sirve en / y en /visor/)."""
import re

import pytest

from conftest import INDEX

requiere_index = pytest.mark.skipif(
    not INDEX.exists(), reason="todavía no existe visor/index.html (lo hace otra persona)"
)


@requiere_index
@pytest.mark.parametrize("ruta", ["/visor/", "/"])
def test_index_servido(cliente, ruta):
    r = cliente.get(ruta)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<html" in r.text.lower()


def _referencias(html):
    """Valores de src= y href= del HTML."""
    return re.findall(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html, flags=re.IGNORECASE)


@requiere_index
def test_index_rutas_relativas():
    html = INDEX.read_text(encoding="utf-8")
    refs = _referencias(html)
    assert refs, "index.html no referencia ningún archivo"
    for ref in refs:
        if ref.startswith("#") or ref.startswith("data:"):
            continue
        # Nada absoluto (rompería al servir en /visor/), ni http sin cifrar.
        assert not ref.startswith("/"), f"ruta absoluta: {ref}"
        assert not ref.startswith("http://"), f"recurso sin https: {ref}"
    propias = [r for r in refs if not r.startswith("https://") and not r.startswith(("#", "data:"))]
    for ref in propias:
        assert ref.startswith("./"), f"archivo propio sin './': {ref}"
    assert "./visor.js" in refs, "index.html no carga ./visor.js"
    assert "./estilos.css" in refs, "index.html no carga ./estilos.css"


@requiere_index
def test_leaflet_por_https():
    refs = _referencias(INDEX.read_text(encoding="utf-8"))
    leaflet = [r for r in refs if "leaflet" in r.lower()]
    assert leaflet, "index.html no carga Leaflet"
    for ref in leaflet:
        assert ref.startswith("https://"), f"Leaflet sin https: {ref}"
