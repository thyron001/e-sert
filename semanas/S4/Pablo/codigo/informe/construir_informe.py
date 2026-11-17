"""
Arma el informe completo a partir de las cuatro secciones y las partes comunes.

    python3 informe/construir_informe.py                    # --fuentes proyecto (lo que usa la unificación)
    python3 informe/construir_informe.py --fuentes ramas    # extrae las secciones ajenas de origin/<nombre>/s4

Fuentes de las secciones:
  * `proyecto` (por defecto): `tyrone.md`, `freddy.md`, `pablo.md`, `miguel.md`, `comun/` y `anexos/` se leen de la
    carpeta `informe/` donde está este script.
  * `ramas`: la sección de Pablo, `comun/` y `anexos/` se leen de la carpeta local; las de Tyrone, Freddy y Miguel
    se extraen con `git archive` de `semanas/S4/<Nombre>/codigo/informe/` de la rama `origin/<nombre>/s4` a una
    carpeta temporal fuera del repositorio (`<tmp>/informe_e-sert_ramas`; nunca se copian al repositorio) y sus figuras se referencian desde ahí.

Marcadores del maestro `informe.md`:
  `<!-- incluir: ruta.md [sin-numero] -->`   inserta el archivo (sin numerar sus títulos con `sin-numero`)
  `<!-- indice -->`                          índice de secciones y subsecciones
  `<!-- referencias -->`                     lista de referencias citadas, resuelta contra `referencias.bib`
  `<!-- salto -->`                           salto de página en el PDF

Numeración: cada `##` es "N Título" y cada `###` "N.M Título" (salvo `sin-numero`); un pie de figura en cursiva
justo debajo de una imagen pasa a "Figura N. pie"; un pie en cursiva justo encima de una tabla, a "Tabla N. pie".

Salida: `informe/salida/informe_e-sert.md` (con las citas `[@clave]` y los comentarios `<!-- fuente -->`, que usa
`verificar_informe.py`) y `informe_e-sert.pdf`. Con `pandoc` se usa `--citeproc --toc` (xelatex o wkhtmltopdf);
sin él, el PDF se genera con fpdf2 (el mismo mecanismo de `herramientas/explicacion_pdf.py`), con las citas ya
resueltas ("[Autor, año]") y la lista de referencias al final; si eso falla, un HTML autocontenido.

Códigos de salida: 0 todo bien; 2 falta alguna sección o anexo (se inserta `[SECCIÓN PENDIENTE: <Nombre>]`, no se
inventa contenido); 1 error de ejecución.
"""
from __future__ import annotations

import argparse
import base64
import html as _html
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ_REPO = next((p for p in AQUI.parents if (p / "herramientas" / "explicacion_pdf.py").is_file()), AQUI.parents[4])
PERSONAS = {"tyrone": "Tyrone", "freddy": "Freddy", "pablo": "Pablo", "miguel": "Miguel"}
RE_INCLUIR = re.compile(r"<!--\s*incluir:\s*(\S+)(?:\s+(sin-numero))?\s*-->")
RE_COMENTARIO = re.compile(r"<!--.*?-->", re.S)
RE_CITA = re.compile(r"\[(@[^\]]+)\]")
RE_PIE = re.compile(r"^\*[^*\s].*\*$")
RE_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")


# ── Bibliografía ───────────────────────────────────────────────────────────

_ACENTOS = {"'": "\u0301", "`": "\u0300", '"': "\u0308", "^": "\u0302", "~": "\u0303"}


def limpiar_latex(s: str) -> str:
    import unicodedata

    s = re.sub(r"\\url\{([^}]*)\}", r"\1", s).replace("\\%", "%").replace("\\&", "&")
    s = s.replace("{\\l}", "ł").replace("{\\L}", "Ł").replace("\\ss", "ß")

    def acento(m):
        base = m.group(2) or m.group(3)
        base = {"\\i": "i", "\\j": "j"}.get(base, base)
        return unicodedata.normalize("NFC", base + _ACENTOS[m.group(1)])

    s = re.sub(r"\{?\\([`'\"^~])\s*(?:\{(\\?[A-Za-z])\}|(\\?[A-Za-z]))\}?", acento, s)
    s = s.replace("--", "–").replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def leer_bib(ruta: Path) -> dict[str, dict]:
    """Parser mínimo de BibTeX (campos entre llaves o comillas, con llaves anidadas)."""
    if not ruta.is_file():
        return {}
    texto = ruta.read_text(encoding="utf-8")
    texto = re.sub(r"(?m)^\s*%.*$", "", texto)
    entradas: dict[str, dict] = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", texto):
        tipo, clave = m.group(1).lower(), m.group(2)
        i, prof, campos = m.end(), 1, {}
        ini = i
        while i < len(texto) and prof:
            prof += {"{": 1, "}": -1}.get(texto[i], 0)
            i += 1
        cuerpo = texto[ini:i - 1]
        for c in re.finditer(r"(\w+)\s*=\s*", cuerpo):
            j = c.end()
            if j >= len(cuerpo):
                continue
            if cuerpo[j] == "{":
                p, k = 1, j + 1
                while k < len(cuerpo) and p:
                    p += {"{": 1, "}": -1}.get(cuerpo[k], 0)
                    k += 1
                valor = cuerpo[j + 1:k - 1]
            elif cuerpo[j] == '"':
                k = cuerpo.index('"', j + 1)
                valor = cuerpo[j + 1:k]
            else:
                valor = re.match(r"[^,\s}]+", cuerpo[j:]).group(0)
            campos[c.group(1).lower()] = valor
        campos["_tipo"] = tipo
        entradas[clave] = campos
    return entradas


def _autores(e: dict) -> list[str]:
    a = e.get("author", "")
    if a.startswith("{") and a.endswith("}") and " and " not in a:
        return [a]
    return [x.strip() for x in re.split(r"\s+and\s+", a) if x.strip()]


def _apellido(autor: str) -> str:
    if autor.startswith("{"):
        return limpiar_latex(autor)
    ap = autor.split(",")[0] if "," in autor else autor.split()[-1]
    return limpiar_latex(ap)


def cita_corta(e: dict) -> str:
    au = _autores(e)
    nombre = _apellido(au[0]) if au else "s. a."
    if len(au) == 2:
        nombre += f" y {_apellido(au[1])}"
    elif len(au) > 2:
        nombre += " et al."
    return f"{nombre}, {e.get('year', 's. f.')}"


def referencia_completa(e: dict) -> str:
    au = _autores(e)
    partes = []
    for a in au[:6]:
        if a.startswith("{"):
            partes.append(limpiar_latex(a))
        elif "," in a:
            ap, nom = [x.strip() for x in a.split(",", 1)]
            ini = " ".join(f"{p[0]}." for p in re.split(r"[\s-]+", limpiar_latex(nom)) if p)
            partes.append(f"{limpiar_latex(ap)}, {ini}")
        else:
            partes.append(limpiar_latex(a))
    quien = "; ".join(partes) + (" et al." if len(au) > 6 else "")
    donde = e.get("journal") or e.get("booktitle") or e.get("howpublished") or e.get("publisher") or ""
    vol = e.get("volume", "")
    if vol and e.get("number"):
        vol += f"({e['number']})"
    extra = ", ".join(x for x in (limpiar_latex(donde), vol, ("pp. " + limpiar_latex(e["pages"])) if e.get("pages") else "") if x)
    doi = f" https://doi.org/{e['doi']}" if e.get("doi") else ""
    return f"{quien} ({e.get('year', 's. f.')}). {limpiar_latex(e.get('title', ''))}. {extra}.{doi}".replace("..", ".")


def claves_en_orden(texto: str) -> list[str]:
    vistas: list[str] = []
    for m in RE_CITA.finditer(RE_COMENTARIO.sub("", texto)):
        for k in re.findall(r"@([\w:.\-]+)", m.group(1)):
            if k not in vistas:
                vistas.append(k)
    return vistas


# ── Fuentes ────────────────────────────────────────────────────────────────


class Fuentes:
    """Resuelve dónde está cada archivo incluido y cuál es su carpeta raíz (para sus imágenes)."""

    def __init__(self, base: Path, modo: str):
        self.base, self.modo, self.tmp = base, modo, None
        self.raices: dict[str, Path] = {}
        self.avisos: list[str] = []
        if modo == "ramas":
            # ruta fija y fuera del repo: se regenera en cada corrida y se conserva al terminar, porque el
            # informe armado enlaza las figuras ajenas desde ahí (el verificador las abre después)
            self.tmp = Path(tempfile.gettempdir()) / "informe_e-sert_ramas"
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp.mkdir(parents=True)
            for clave, nombre in PERSONAS.items():
                if clave == "pablo":
                    continue
                self._extraer(clave, nombre)

    def _raiz_git(self) -> str | None:
        """Raíz del repositorio: `git archive` toma las rutas relativas a la carpeta desde donde se ejecuta."""
        r = subprocess.run(["git", "-C", str(self.base), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None

    def _extraer(self, clave: str, nombre: str):
        rama = f"origin/{clave}/s4"
        ruta = f"semanas/S4/{nombre}/codigo/informe/"
        raiz = self._raiz_git()
        if raiz is None:
            self.avisos.append("no es un repositorio git")
            return
        ok = subprocess.run(["git", "-C", raiz, "rev-parse", "--verify", "--quiet", rama],
                            capture_output=True).returncode == 0
        if not ok:
            self.avisos.append(f"no existe la rama {rama}")
            return
        destino = self.tmp / clave
        destino.mkdir()
        ar = subprocess.run(["git", "-C", raiz, "archive", "--format=tar", rama, ruta], capture_output=True)
        if ar.returncode != 0:
            self.avisos.append(f"{rama} no tiene {ruta}")
            return
        subprocess.run(["tar", "-x", "-C", str(destino)], input=ar.stdout, check=True)
        self.raices[clave] = destino / ruta.rstrip("/")

    def resolver(self, ruta: str) -> tuple[Path | None, Path]:
        """(archivo o None, carpeta raíz del archivo)."""
        clave = Path(ruta).stem
        if self.modo == "ramas" and ruta == f"{clave}.md" and clave in PERSONAS and clave != "pablo":
            raiz = self.raices.get(clave)
            if raiz is None:
                return None, self.base
            p = raiz / ruta
            return (p if p.is_file() else None), raiz
        p = self.base / ruta
        return (p if p.is_file() else None), self.base

    def limpiar(self):
        """No borra el temporal de `ramas` (ver `__init__`); se regenera en la siguiente corrida."""


# ── Procesamiento de una sección ───────────────────────────────────────────


class Estado:
    def __init__(self):
        self.fig = self.tab = self.sec = 0
        self.sub = 0
        self.indice: list[tuple[int, str]] = []


def procesar(texto: str, raiz: Path, salida: Path, est: Estado, numerar: bool) -> str:
    lineas = texto.splitlines()
    out: list[str] = []
    en_codigo = False
    i = 0
    while i < len(lineas):
        l = lineas[i]
        if l.lstrip().startswith("```"):
            en_codigo = not en_codigo
            out.append(l)
            i += 1
            continue
        if en_codigo:
            out.append(l)
            i += 1
            continue
        m = re.match(r"^(#{2,3})\s+(.*)$", l)
        if m:
            nivel, titulo = len(m.group(1)), m.group(2).strip()
            if numerar and nivel == 2:
                est.sec += 1
                est.sub = 0
                titulo = f"{est.sec} {titulo}"
            elif numerar and nivel == 3:
                est.sub += 1
                titulo = f"{est.sec}.{est.sub} {titulo}"
            est.indice.append((nivel, titulo))
            out.append(f"{m.group(1)} {titulo}")
            i += 1
            continue
        mi = RE_IMG.search(l)
        if mi and l.strip().startswith("!["):
            est.fig += 1
            try:
                destino = Path(os.path.relpath((raiz / mi.group(2)).resolve(), salida.resolve())).as_posix()
            except ValueError:  # otra unidad en Windows
                destino = (raiz / mi.group(2)).resolve().as_posix()
            out.append(l.replace(f"]({mi.group(2)})", f"]({destino})", 1))
            if i + 1 < len(lineas) and RE_PIE.match(lineas[i + 1].strip()):
                out.append(f"*Figura {est.fig}. {lineas[i + 1].strip()[1:]}")
                i += 2
            else:
                out.append(f"*Figura {est.fig}.*")
                i += 1
            continue
        if RE_PIE.match(l.strip()):
            j = i + 1
            if j < len(lineas) and not lineas[j].strip():
                j += 1
            if j < len(lineas) and lineas[j].lstrip().startswith("|"):
                est.tab += 1
                out.append(f"*Tabla {est.tab}. {l.strip()[1:]}")
                i += 1
                continue
        out.append(l)
        i += 1
    return "\n".join(out)


def caja_pendiente(ruta: str) -> str:
    stem = Path(ruta).stem
    nombre = PERSONAS.get(stem)
    if nombre:
        return f"> **[SECCIÓN PENDIENTE: {nombre}]**"
    return f"> **[SECCIÓN PENDIENTE: {ruta}]**"


# ── Armado ─────────────────────────────────────────────────────────────────


def armar(base: Path, fuentes: Fuentes, salida: Path) -> tuple[str, list[str], list[tuple[str, int]]]:
    maestro = (base / "informe.md").read_text(encoding="utf-8")
    est = Estado()
    pendientes: list[str] = []
    incluidos: list[tuple[str, int]] = []
    trozos: list[str] = []
    for linea in maestro.splitlines():
        m = RE_INCLUIR.search(linea)
        if not m:
            trozos.append(linea)
            continue
        ruta, sin = m.group(1), bool(m.group(2))
        archivo, raiz = fuentes.resolver(ruta)
        if archivo is None:
            pendientes.append(ruta)
            trozos += [f"<!-- inicio-seccion: {ruta} -->", "", caja_pendiente(ruta), "", f"<!-- fin-seccion: {ruta} -->"]
            continue
        cuerpo = procesar(archivo.read_text(encoding="utf-8"), raiz, salida, est, numerar=not sin)
        incluidos.append((ruta, len(re.findall(r"\w+", RE_COMENTARIO.sub("", cuerpo)))))
        trozos += [f"<!-- inicio-seccion: {ruta} -->", "", cuerpo.strip(), "", f"<!-- fin-seccion: {ruta} -->"]
    texto = "\n".join(trozos)
    if "<!-- indice -->" in texto:
        idx = ["## Índice", ""]
        for nivel, t in est.indice:
            idx.append(f"{'  ' * (nivel - 2)}- {t}")
        texto = texto.replace("<!-- indice -->", "\n".join(idx))
    return texto, pendientes, incluidos


def lista_referencias(texto: str, bib: dict[str, dict]) -> str:
    claves = [k for k in claves_en_orden(texto) if k in bib]
    ordenadas = sorted(claves, key=lambda k: (_apellido((_autores(bib[k]) or ["~"])[0]).lower(), bib[k].get("year", "")))
    filas = ["## Referencias", ""] + [f"- {referencia_completa(bib[k])}" for k in ordenadas]
    return "\n".join(filas)


def resolver_citas(texto: str, bib: dict[str, dict]) -> str:
    def cambia(m):
        cortas = []
        for k in re.findall(r"@([\w:.\-]+)", m.group(1)):
            cortas.append(cita_corta(bib[k]) if k in bib else f"?{k}")
        return "[" + "; ".join(cortas) + "]"

    return RE_CITA.sub(cambia, texto)


# ── Salidas ────────────────────────────────────────────────────────────────

_GRIEGAS = {"σ": "sigma", "ρ": "rho", "Δ": "Delta", "μ": "mu", "−": "-", "≠": "!=", "∞": "inf", "ł": "l"}


def _para_render(texto: str) -> str:
    t = re.sub(r"<!--\s*salto\s*-->", "\n\n@@SALTO@@\n\n", texto)
    t = RE_COMENTARIO.sub("", t)
    for a, b in _GRIEGAS.items():
        t = t.replace(a, b)
    return t


def generar_pdf_fpdf(texto: str, salida_md: Path) -> Path:
    spec = importlib.util.spec_from_file_location("explicacion_pdf", RAIZ_REPO / "herramientas" / "explicacion_pdf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pdf = mod.PDF("e-sert · Informe final", mod.COLORES["Pablo"])
    pdf.add_page()
    pdf.set_text_color(0x0B, 0x25, 0x40)
    from fpdf.fonts import FontFace

    estilos = {"h1": FontFace(color=mod.COLORES["Pablo"], size_pt=20, emphasis="B"),
               "h2": FontFace(color=(0x0B, 0x25, 0x40), size_pt=15, emphasis="B"),
               "h3": FontFace(color=(0x1C, 0x3A, 0x58), size_pt=12.5, emphasis="B")}
    primero = True
    for parte in _para_render(texto).split("@@SALTO@@"):
        if not primero:
            pdf.add_page()
        primero = False
        pdf.write_html(mod._a_html(parte, salida_md.parent), tag_styles=estilos, font_family="Helvetica")
    destino = salida_md.with_suffix(".pdf")
    pdf.output(str(destino))
    return destino


def generar_html(texto: str, salida_md: Path) -> Path:
    import markdown

    cuerpo = markdown.markdown(_para_render(texto).replace("@@SALTO@@", '<div style="page-break-after:always"></div>'),
                               extensions=["tables", "fenced_code", "sane_lists"])

    def incrusta(m):
        p = (salida_md.parent / m.group(1)).resolve()
        if not p.is_file():
            return m.group(0)
        return f'<img src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}"'

    cuerpo = re.sub(r'<img[^>]*?src="([^"]+)"', incrusta, cuerpo)
    destino = salida_md.with_suffix(".html")
    destino.write_text("<!doctype html><meta charset='utf-8'><title>Informe e-sert</title>"
                       "<style>body{font-family:sans-serif;max-width:46em;margin:2em auto;line-height:1.45}"
                       "img{max-width:100%}table{border-collapse:collapse}td,th{border:1px solid #999;padding:3px 6px}"
                       "</style>" + cuerpo, encoding="utf-8")
    return destino


def generar_pdf(texto_md: str, salida_md: Path, bib_ruta: Path, bib: dict) -> tuple[Path, str]:
    """(archivo, descripción del backend usado)."""
    if shutil.which("pandoc"):
        for motor in ("xelatex", "wkhtmltopdf"):
            if shutil.which(motor):
                cmd = ["pandoc", str(salida_md), "-o", str(salida_md.with_suffix(".pdf")), "--citeproc", "--toc",
                       "--bibliography", str(bib_ruta), "--metadata", "suppress-bibliography=true",
                       f"--pdf-engine={motor}", "--resource-path", str(salida_md.parent)]
                if subprocess.run(cmd, capture_output=True).returncode == 0:
                    return salida_md.with_suffix(".pdf"), f"pandoc + {motor}"
    resuelto = resolver_citas(texto_md, bib)
    try:
        return generar_pdf_fpdf(resuelto, salida_md), "fpdf2 (no hay pandoc; mismo mecanismo que herramientas/explicacion_pdf.py)"
    except Exception as e:  # noqa: BLE001
        print(f"AVISO: no se pudo generar el PDF con fpdf2 ({type(e).__name__}: {e}); se genera HTML.", file=sys.stderr)
        return generar_html(resuelto, salida_md), "HTML autocontenido (sin pandoc y fpdf2 falló)"


def construir(base: Path | None = None, modo: str = "proyecto", pdf: bool = True, salida_dir: Path | None = None) -> int:
    base = Path(base) if base else AQUI
    salida_dir = Path(salida_dir) if salida_dir else base / "salida"
    salida_dir.mkdir(parents=True, exist_ok=True)
    salida_md = salida_dir / "informe_e-sert.md"
    fuentes = Fuentes(base, modo)
    try:
        texto, pendientes, incluidos = armar(base, fuentes, salida_dir)
        bib_ruta = base / "referencias.bib"
        bib = leer_bib(bib_ruta)
        if "<!-- referencias -->" in texto:
            texto = texto.replace("<!-- referencias -->", lista_referencias(texto, bib))
        salida_md.write_text(texto, encoding="utf-8")
        print(f"Fuentes: {modo}. Escrito {salida_md}")
        for aviso in fuentes.avisos:
            print(f"  AVISO: {aviso}")
        for ruta, palabras in incluidos:
            print(f"  incluido {ruta}: {palabras} palabras")
        for ruta in pendientes:
            print(f"  [SECCIÓN PENDIENTE] {ruta}")
        if pdf:
            destino, backend = generar_pdf(texto, salida_md, bib_ruta, bib)
            kind = "PDF" if destino.suffix == ".pdf" else "HTML (NO es PDF)"
            print(f"{kind}: {destino}\n  backend: {backend}")
    finally:
        fuentes.limpiar()
    return 2 if pendientes else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Construye el informe e-sert")
    ap.add_argument("--fuentes", choices=["proyecto", "ramas"], default="proyecto")
    ap.add_argument("--carpeta", type=Path, default=None, help="carpeta informe/ (por defecto, la de este script)")
    ap.add_argument("--sin-pdf", action="store_true", help="solo escribe el Markdown")
    a = ap.parse_args(argv)
    return construir(a.carpeta, a.fuentes, pdf=not a.sin_pdf)


if __name__ == "__main__":
    sys.exit(main())
