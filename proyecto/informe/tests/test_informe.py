"""Pruebas del armado y la verificación del informe, con secciones sintéticas en un directorio temporal."""
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

INFORME = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(INFORME))
import construir_informe as ci  # noqa: E402
import verificar_informe as vi  # noqa: E402

PERSONAS = ["freddy", "tyrone", "pablo", "miguel"]
BIB = """@article{kk2020,
  author = {Gómez, Ana and Pérez, Luis},
  title = {Un artículo de prueba},
  journal = {Revista de Prueba},
  year = {2020}, volume = {3}, number = {1}, pages = {1--9}
}
"""


def relleno(n: int) -> str:
    return " ".join(f"palabra{i % 50}" for i in range(n))


def seccion(nombre: str, palabras=850, extra="") -> str:
    return (f"## Sección de {nombre}\n\n{relleno(palabras)} [@kk2020].\n\n"
            f"### Detalle\n\nLa métrica vale 0,87. <!-- fuente: datos/r.json:metrica -->\n\n"
            f"*Resultados de {nombre}.*\n\n| a | b |\n|---|---:|\n| x | 1 |\n\n"
            f"![](figuras/{nombre}/f.png)\n*Pie de la figura de {nombre}.*\n{extra}\n")


@pytest.fixture
def base(tmp_path):
    b = tmp_path / "informe"
    (b / "comun").mkdir(parents=True)
    (b / "anexos").mkdir()
    for p in PERSONAS:
        (b / f"{p}.md").write_text(seccion(p))
        (b / "figuras" / p).mkdir(parents=True)
        Image.new("RGB", (4, 4), "green").save(b / "figuras" / p / "f.png")
    (b / "comun" / "02_intro.md").write_text("## Introducción\n\nTexto de la introducción.\n")
    (b / "anexos" / "preguntas.md").write_text("## Preguntas\n\n1. ¿Por qué RF?\n")
    (b / "referencias.bib").write_text(BIB)
    (b / "informe.md").write_text(
        "<!-- indice -->\n\n<!-- incluir: comun/02_intro.md -->\n\n"
        + "\n\n".join(f"<!-- incluir: {p}.md -->" for p in PERSONAS)
        + "\n\n<!-- referencias -->\n\n<!-- incluir: anexos/preguntas.md -->\n")
    return b


def construir(b, modo="proyecto", pdf=False):
    return ci.construir(b, modo, pdf=pdf)


def salida(b) -> str:
    return (b / "salida" / "informe_e-sert.md").read_text()


# ── Armado ──────────────────────────────────────────────────────────────────


def test_construye_con_fuentes_proyecto(base):
    assert construir(base) == 0
    md = salida(base)
    assert "## 1 Introducción" in md and "### 2.1 Detalle" in md          # numeración de secciones
    assert "*Tabla 1. Resultados de freddy.*" in md                       # pie de tabla numerado
    assert "*Figura 1. Pie de la figura de freddy.*" in md and "*Figura 4." in md
    assert "](../figuras/freddy/f.png)" in md                              # ruta relativa a salida/
    assert "## Referencias" in md and "Gómez, A.; Pérez, L. (2020)" in md  # lista resuelta contra el .bib
    assert "<!-- fuente: datos/r.json:metrica -->" in md                  # conserva la trazabilidad


def test_seccion_faltante_da_codigo_2_y_recuadro(base):
    (base / "tyrone.md").unlink()
    assert construir(base) == 2
    md = salida(base)
    assert "[SECCIÓN PENDIENTE: Tyrone]" in md
    assert "Sección de tyrone" not in md                                   # no inventa contenido


def test_cli_devuelve_el_codigo(base):
    (base / "miguel.md").unlink()
    r = subprocess.run([sys.executable, str(INFORME / "construir_informe.py"), "--carpeta", str(base), "--sin-pdf"],
                       capture_output=True, text=True)
    assert r.returncode == 2 and "SECCIÓN PENDIENTE" in r.stdout


def test_sin_numero_deja_el_titulo(base):
    (base / "informe.md").write_text("<!-- incluir: comun/02_intro.md sin-numero -->\n")
    construir(base)
    assert "## Introducción" in salida(base)


def test_genera_pdf_sin_pandoc(base):
    construir(base, pdf=True)
    assert (base / "salida" / "informe_e-sert.pdf").stat().st_size > 1000 or (base / "salida" / "informe_e-sert.html").exists()


def test_ramas_sin_ramas_marca_pendientes(base):
    assert construir(base, "ramas") == 2
    md = salida(base)
    assert all(f"[SECCIÓN PENDIENTE: {n}]" in md for n in ("Freddy", "Tyrone", "Miguel"))
    assert "Sección de pablo" in md                                        # la propia sección se lee local


def test_ramas_extrae_con_git_archive(base, tmp_path):
    repo = tmp_path / "repo"
    ruta = repo / "semanas/S4/Tyrone/codigo/informe"
    (ruta / "figuras/tyrone").mkdir(parents=True)
    (ruta / "tyrone.md").write_text(seccion("tyrone", extra="\nde la rama\n"))
    Image.new("RGB", (4, 4), "blue").save(ruta / "figuras/tyrone/f.png")
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)  # noqa: E731
    g("init", "-q")
    g("add", "-A")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x")
    g("update-ref", "refs/remotes/origin/tyrone/s4", "HEAD")
    b2 = repo / "informe_local"
    b2.mkdir()
    for f in base.iterdir():
        (b2 / f.name).symlink_to(f) if f.is_dir() else (b2 / f.name).write_text(f.read_text())
    (b2 / "tyrone.md").unlink(missing_ok=True)
    assert ci.construir(b2, "ramas", pdf=False) == 2                       # Freddy y Miguel no tienen rama
    md = (b2 / "salida" / "informe_e-sert.md").read_text()
    assert "de la rama" in md and "[SECCIÓN PENDIENTE: Freddy]" in md
    assert not (b2 / "tyrone.md").exists()                                  # no copia secciones ajenas
    assert vi.verificar(b2 / "salida" / "informe_e-sert.md", b2 / "referencias.bib")["imagenes"] == []


# ── Verificador ─────────────────────────────────────────────────────────────


def verificar(b):
    return vi.verificar(b / "salida" / "informe_e-sert.md", b / "referencias.bib")


def test_informe_sano_pasa(base):
    construir(base)
    r = verificar(base)
    assert not (r["personas"] or r["imagenes"] or r["prohibidos"] or r["citas"] or r["discrepancias"])
    assert vi.main(["--md", str(base / "salida" / "informe_e-sert.md")]) == 0


def test_detecta_seccion_corta(base):
    (base / "pablo.md").write_text(seccion("pablo", palabras=100))
    construir(base)
    assert any(p == "pablo.md" and "solo" in m for p, m in verificar(base)["personas"])


def test_detecta_seccion_ausente(base):
    (base / "freddy.md").unlink()
    construir(base)
    assert ("freddy.md", "ausente") in verificar(base)["personas"]
    assert vi.main(["--md", str(base / "salida" / "informe_e-sert.md")]) == 1


def test_detecta_imagen_inexistente(base):
    (base / "figuras/miguel/f.png").unlink()
    construir(base)
    assert verificar(base)["imagenes"]


@pytest.mark.parametrize("palabra", ["TODO", "MOCK", "PENDIENTE"])
def test_detecta_todo_mock_pendiente(base, palabra):
    (base / "tyrone.md").write_text(seccion("tyrone", extra=f"\nTexto con {palabra} dentro.\n"))
    construir(base)
    assert any(x[1] == palabra for x in verificar(base)["prohibidos"])


def test_los_comentarios_html_no_cuentan_como_prohibidos(base):
    (base / "tyrone.md").write_text(seccion("tyrone", extra="\n<!-- TODO interno -->\n"))
    construir(base)
    assert not verificar(base)["prohibidos"]


def test_detecta_cita_inexistente(base):
    (base / "miguel.md").write_text(seccion("miguel", extra="\nOtra cita [@no_existe].\n"))
    construir(base)
    assert ("no_existe") in [k for _, k in verificar(base)["citas"]]


def test_detecta_misma_metrica_con_valores_distintos(base):
    (base / "tyrone.md").write_text(seccion("tyrone").replace("vale 0,87", "vale 0,91"))
    construir(base)
    d = verificar(base)["discrepancias"]
    assert d and d[0][0] == "datos/r.json:metrica"
    assert vi.main(["--md", str(base / "salida" / "informe_e-sert.md")]) == 1


def test_misma_ruta_sin_clave_solo_avisa(base):
    for p in PERSONAS:
        t = (base / f"{p}.md").read_text().replace("datos/r.json:metrica", "datos/r.json")
        (base / f"{p}.md").write_text(t.replace("vale 0,87", "vale 0,91") if p == "tyrone" else t)
    construir(base)
    r = verificar(base)
    assert not r["discrepancias"] and r["avisos"]


def test_la_misma_cifra_en_dos_secciones_es_coherente(base):
    construir(base)
    assert verificar(base)["discrepancias"] == []
