"""
Verifica la trazabilidad de las cifras de `pablo.md`.

    python3 informe/verificar_cifras.py [informe/pablo.md]

Reglas:
* Un comentario `<!-- fuente: ruta1; ruta2 -->` cubre el bloque (párrafo o tabla, líneas contiguas) donde
  está; el comentario del pie `**Tabla N.**` cubre también a la tabla que le sigue. Cada cifra del bloque debe aparecer en alguna de las fuentes (JSON, CSV o MD). Las rutas son
  relativas a la carpeta `codigo/` o a la raíz del repo.
* Una cifra coincide con un número `t` de la fuente si, redondeado a los decimales con que se escribió,
  vale lo mismo (`t`, `100·t` o `t/100`, para porcentajes y puntos). Los enteros deben coincidir exacto.
* No se comprueban: años, enteros menores que 10, texto entre comillas invertidas, enlaces, imágenes,
  citas `[@clave]`, referencias como "Figura 3" o "S3-2", ni la numeración de títulos y listas.
* Se listan aparte: bloques con cifras de aspecto de dato pero sin `fuente`, los `[PENDIENTE]`, las
  imágenes inexistentes y las claves de cita que no están en `referencias_ia.bib`.

Sale con código 1 si hay cifras huérfanas, imágenes rotas o claves inexistentes (los PENDIENTE no fallan).
"""
import json
import re
import sys
from pathlib import Path

CODIGO = Path(__file__).resolve().parents[1]
RAIZ = CODIGO.parents[3]

RE_COMENTARIO = re.compile(r"<!--\s*fuente:\s*(.*?)\s*-->", re.S)
RE_NUM = re.compile(r"(?<![\w.])(?:\d{1,3}(?: \d{3})+|\d+)(?:,\d+)?(?![\w])")
RE_NUM_MD = re.compile(r"-?\d{1,3}(?: \d{3})+(?!\d)|-?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?")
RE_NUM_DATOS = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def numeros_fuente(ruta: Path) -> list[float]:
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    if ruta.suffix == ".json":
        texto = json.dumps(json.loads(texto))
    vals = []
    regex = RE_NUM_MD if ruta.suffix == ".md" else RE_NUM_DATOS  # en CSV/JSON la coma separa columnas
    for m in regex.finditer(texto):
        s = m.group(0)
        try:
            vals.append(float(s.replace(" ", "").replace(",", ".")))
            if "," in s and " " not in s:  # en prosa "52,0" puede ser lista: tambien el entero previo
                vals.append(float(s.split(",")[0]))
        except ValueError:
            pass
    return vals


def limpiar_bloque(texto: str) -> str:
    texto = RE_COMENTARIO.sub(" ", texto)
    texto = re.sub(r"<!--.*?-->", " ", texto, flags=re.S)
    texto = re.sub(r"`[^`]*`", " ", texto)
    texto = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", texto)
    texto = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", texto)
    texto = re.sub(r"\[@[^\]]*\]", " ", texto)
    texto = re.sub(r"\[PENDIENTE[^\]]*\]", " ", texto)
    texto = re.sub(r"\b(Figura|Tabla|Sección|Secciones|§)\s*\d+[.\d]*", " ", texto)
    texto = re.sub(r"\bS\d-\d\b|\bS\d\b", " ", texto)
    texto = re.sub(r"^\s*#+\s*\d+[.\d]*", " ", texto, flags=re.M)
    texto = re.sub(r"^\s*\d+\.\s", " ", texto, flags=re.M)
    texto = re.sub(r"^\|[\s\-|:]+\|$", " ", texto, flags=re.M)
    texto = re.sub(r"\*\*Tabla \d+\.\*\*|\*\*Figura \d+\.\*\*", " ", texto)
    return texto


def cifras(texto: str) -> list[tuple[str, float, int]]:
    """(texto, valor, decimales) de las cifras comprobables."""
    out = []
    for m in RE_NUM.finditer(limpiar_bloque(texto)):
        s = m.group(0)
        limpio = s.replace(" ", "")
        dec = len(limpio.split(",")[1]) if "," in limpio else 0
        v = float(limpio.replace(",", "."))
        if dec == 0 and (v < 10 or 1900 <= v <= 2100):
            continue
        out.append((s, v, dec))
    return out


def coincide(v: float, dec: int, fuentes: list[float]) -> bool:
    tol = 1e-9 if dec == 0 else 0.5 * 10 ** (-dec) + 1e-9
    for t in fuentes:
        for escala in (1.0, 100.0, 0.01):
            if abs(t * escala - v) <= tol or abs(abs(t) * escala - v) <= tol:
                return True
    return False


def _es_pie(bloque: str) -> bool:
    """Pie de tabla: una sola linea en cursiva (`*Pie.*`) o `**Tabla N.**` (estilo del borrador de S3)."""
    b = bloque.strip()
    return "\n" not in b and (b.startswith("**Tabla") or (b.startswith("*") and not b.startswith("**")))


def resolver(ruta: str) -> Path | None:
    ruta = ruta.split(":", 1)[0]  # `ruta:clave` apunta a una metrica concreta del archivo
    for base in (CODIGO, RAIZ):
        p = base / ruta
        if p.is_file():
            return p
    return None


def bloques(lineas: list[str]):
    actual, ini = [], 0
    for i, l in enumerate(lineas + [""]):
        if l.strip():
            if not actual:
                ini = i + 1
            actual.append(l)
        elif actual:
            yield ini, "\n".join(actual)
            actual = []


def main():
    md = Path(sys.argv[1]) if len(sys.argv) > 1 else CODIGO / "informe/pablo.md"
    texto = md.read_text(encoding="utf-8")
    lineas = texto.splitlines()
    cache: dict[str, list[float]] = {}
    huerfanas, sin_fuente, fuentes_faltan = [], [], []
    n_comprobadas = n_bloques = 0

    previo = ("", [])  # (texto, rutas) del bloque anterior: el pie "**Tabla N.**" cubre a su tabla
    for ini, bloque in bloques(lineas):
        if bloque.lstrip().startswith("```"):
            continue
        rutas = [r.strip() for c in RE_COMENTARIO.findall(bloque) for r in c.split(";") if r.strip()]
        if not rutas and bloque.lstrip().startswith("|") and _es_pie(previo[0]):
            rutas = previo[1]
        previo = (bloque, rutas)
        nums = cifras(bloque)
        if not rutas:
            datos = [s for s, v, d in nums if d > 0 or "%" in bloque and v >= 10 and v < 100 or v >= 1000]
            if datos and not bloque.lstrip().startswith(("|", "#")) or (datos and "PENDIENTE" not in bloque):
                sin_fuente.append((ini, datos[:6]))
            continue
        n_bloques += 1
        vals: list[float] = []
        for r in rutas:
            p = resolver(r)
            if p is None:
                fuentes_faltan.append((ini, r))
                continue
            if r not in cache:
                cache[r] = numeros_fuente(p)
            vals += cache[r]
        for s, v, dec in nums:
            n_comprobadas += 1
            if not coincide(v, dec, vals):
                huerfanas.append((ini, s, rutas))

    imagenes_rotas = []
    for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", texto):
        if not (md.parent / m.group(1)).is_file():
            imagenes_rotas.append(m.group(1))

    claves_faltan = []
    bib = md.parent / "referencias.bib"
    if not bib.is_file():
        bib = md.parent / "referencias_ia.bib"
    claves_bib = set(re.findall(r"@\w+\{([^,\s]+),", bib.read_text(encoding="utf-8"))) if bib.is_file() else set()
    for m in re.finditer(r"\[(@[^\]]+)\]", texto):
        for k in re.findall(r"@([\w:.\-]+)", m.group(1)):
            if k not in claves_bib:
                claves_faltan.append(k)

    pendientes = [i + 1 for i, l in enumerate(lineas) if "[PENDIENTE" in l]

    print(f"Bloques con fuente: {n_bloques} · cifras comprobadas: {n_comprobadas}")
    print(f"Cifras huérfanas: {len(huerfanas)}")
    for ini, s, rutas in huerfanas:
        print(f"  línea {ini}: '{s}' no está en {', '.join(rutas)}")
    for ini, r in fuentes_faltan:
        print(f"  línea {ini}: fuente inexistente: {r}")
    print(f"Bloques con cifras de dato y sin fuente (revisar): {len(sin_fuente)}")
    for ini, d in sin_fuente:
        print(f"  línea {ini}: {', '.join(d)}")
    print(f"Imágenes rotas: {len(imagenes_rotas)} {imagenes_rotas if imagenes_rotas else ''}")
    print(f"Claves de cita inexistentes en el .bib: {sorted(set(claves_faltan)) if claves_faltan else 0}")
    print(f"[PENDIENTE] (marcadores, no fallan): {len(pendientes)} en las líneas {pendientes}")
    ok = not (huerfanas or fuentes_faltan or imagenes_rotas or claves_faltan)
    print("RESULTADO:", "OK" if ok else "FALLA")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
