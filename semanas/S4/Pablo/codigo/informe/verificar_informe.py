"""
Verifica el informe armado (`informe/salida/informe_e-sert.md`).

    python3 informe/verificar_informe.py [--md RUTA] [--bib RUTA]

Sale con código 1 si encuentra:
  1. una sección de persona (tyrone, freddy, pablo, miguel) ausente (con recuadro de pendiente) o con menos de
     800 palabras;
  2. una imagen enlazada que no existe;
  3. `TODO`, `PENDIENTE` o `MOCK` en el texto visible del documento final (los comentarios HTML no cuentan);
  4. una cita `[@clave]` que no está en `referencias.bib`;
  5. la misma métrica con valores distintos en dos secciones.

Cómo se compara la misma métrica: un bloque (párrafo o tabla, líneas contiguas; el pie `*Tabla N. ...*` cubre a
la tabla siguiente) con exactamente UN comentario `<!-- fuente: X -->` aporta sus cifras (las "comprobables" de
`verificar_cifras.cifras`: se ignoran años, enteros menores que 10, código entre comillas, enlaces y citas). Dos
bloques de secciones distintas con la misma fuente `X` son coherentes si comparten al menos un valor (igualdad con el
redondeo del menos preciso). Si la fuente trae clave (`ruta:clave`, una métrica concreta) y no comparten ninguno, es
una discrepancia y falla; si es una ruta sin clave (varias métricas posibles del mismo archivo), solo se avisa.
Los bloques con varias fuentes no se comparan.

Imprime una tabla de palabras por sección. Los `[PENDIENTE]` se listan aparte pero también hacen fallar.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PERSONAS = ["tyrone.md", "freddy.md", "pablo.md", "miguel.md"]
MIN_PALABRAS = 800
RE_COMENTARIO = re.compile(r"<!--.*?-->", re.S)
RE_FUENTE = re.compile(r"<!--\s*fuente:\s*(.*?)\s*-->", re.S)
RE_MARCA = re.compile(r"<!--\s*(inicio|fin)-seccion:\s*(\S+)\s*-->")
RE_PROHIBIDO = re.compile(r"\bTODO\b|PENDIENTE|\bMOCK\b")


def _cargar_cifras():
    spec = importlib.util.spec_from_file_location("verificar_cifras", AQUI / "verificar_cifras.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VC = _cargar_cifras()


def secciones(texto: str) -> dict[str, tuple[int, int]]:
    """ruta -> (línea de inicio, línea de fin) (1-based) según los marcadores que deja el armador."""
    ini: dict[str, int] = {}
    out: dict[str, tuple[int, int]] = {}
    for n, l in enumerate(texto.splitlines(), 1):
        m = RE_MARCA.search(l)
        if m:
            if m.group(1) == "inicio":
                ini[m.group(2)] = n
            elif m.group(2) in ini:
                out[m.group(2)] = (ini[m.group(2)], n)
    return out


def palabras(texto: str) -> int:
    return len(re.findall(r"\w+", RE_COMENTARIO.sub("", texto)))


def texto_visible(lineas: list[str]) -> list[tuple[int, str]]:
    """Líneas con su número, sin comentarios HTML (también los de varias líneas)."""
    crudo = "\n".join(lineas)
    sin = RE_COMENTARIO.sub(lambda m: "\n" * m.group(0).count("\n"), crudo)
    return list(enumerate(sin.splitlines(), 1))


def bloques(lineas: list[str]):
    actual, ini = [], 0
    for i, l in enumerate(lineas + [""], 1):
        if l.strip():
            if not actual:
                ini = i
            actual.append(l)
        elif actual:
            yield ini, "\n".join(actual)
            actual = []


def seccion_de(n: int, rangos: dict[str, tuple[int, int]]) -> str:
    for ruta, (a, b) in rangos.items():
        if a <= n <= b:
            return ruta
    return "(fuera de secciones)"


def valores_coinciden(a: list[tuple[str, float, int]], b: list[tuple[str, float, int]]) -> bool:
    if not a or not b:
        return True
    for _, va, da in a:
        for _, vb, db in b:
            dec = min(da, db)
            tol = 1e-9 if dec == 0 else 0.5 * 10 ** (-dec) + 1e-9
            if abs(va - vb) <= tol:
                return True
    return False


def verificar(md: Path, bib: Path) -> dict:
    texto = md.read_text(encoding="utf-8")
    lineas = texto.splitlines()
    rangos = secciones(texto)
    res: dict = {"palabras": [], "personas": [], "imagenes": [], "prohibidos": [], "citas": [],
                 "discrepancias": [], "avisos": []}

    # 1. palabras por sección y secciones de persona
    for ruta, (a, b) in rangos.items():
        cuerpo = "\n".join(lineas[a:b - 1])
        res["palabras"].append((ruta, palabras(cuerpo)))
    palabras_de = dict(res["palabras"])
    for p in PERSONAS:
        cuerpo = "\n".join(lineas[rangos[p][0]:rangos[p][1] - 1]) if p in rangos else ""
        if p not in rangos or "[SECCIÓN PENDIENTE" in cuerpo:
            res["personas"].append((p, "ausente"))
        elif palabras_de[p] < MIN_PALABRAS:
            res["personas"].append((p, f"solo {palabras_de[p]} palabras (mínimo {MIN_PALABRAS})"))

    # 2. imágenes
    en_codigo = False
    for n, l in enumerate(lineas, 1):
        if l.lstrip().startswith("```"):
            en_codigo = not en_codigo
        if en_codigo:
            continue
        for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)\)", l):
            ruta = m.group(1)
            if not re.match(r"^(https?:|data:)", ruta) and not (md.parent / ruta).is_file():
                res["imagenes"].append((n, ruta))

    # 3. TODO / PENDIENTE / MOCK en el texto visible
    for n, l in texto_visible(lineas):
        for m in RE_PROHIBIDO.finditer(l):
            res["prohibidos"].append((n, m.group(0), seccion_de(n, rangos)))

    # 4. citas
    claves_bib = set(re.findall(r"@\w+\{([^,\s]+),", bib.read_text(encoding="utf-8"))) if bib.is_file() else set()
    for n, l in texto_visible(lineas):
        for m in re.finditer(r"\[(@[^\]]+)\]", l):
            for k in re.findall(r"@([\w:.\-]+)", m.group(1)):
                if k not in claves_bib:
                    res["citas"].append((n, k))

    # 5. misma métrica en dos secciones
    por_fuente: dict[str, list[tuple[str, int, list]]] = {}
    previo_pie = None
    for ini, bloque in bloques(lineas):
        fuentes = [f.strip() for c in RE_FUENTE.findall(bloque) for f in c.split(";") if f.strip()]
        if not fuentes and bloque.lstrip().startswith("|") and previo_pie:
            fuentes = previo_pie
        previo_pie = fuentes if VC._es_pie(bloque) else None
        if len(fuentes) != 1:
            continue
        sec = seccion_de(ini, rangos)
        por_fuente.setdefault(fuentes[0], []).append((sec, ini, VC.cifras(bloque)))
    for fuente, items in por_fuente.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                (sa, la, na), (sb, lb, nb) = items[i], items[j]
                if sa == sb or valores_coinciden(na, nb):
                    continue
                det = (fuente, sa, la, [t for t, _, _ in na][:5], sb, lb, [t for t, _, _ in nb][:5])
                (res["discrepancias"] if ":" in fuente else res["avisos"]).append(det)
    return res


def imprimir(res: dict) -> int:
    print("Palabras por sección:")
    print(f"  {'sección':<36}{'palabras':>9}")
    for ruta, n in res["palabras"]:
        marca = "  <-- menos de 800" if ruta in PERSONAS and n < MIN_PALABRAS else ""
        print(f"  {ruta:<36}{n:>9}{marca}")
    fallas = 0
    for p, motivo in res["personas"]:
        print(f"FALLA sección de persona {p}: {motivo}")
        fallas += 1
    for n, ruta in res["imagenes"]:
        print(f"FALLA línea {n}: la imagen no existe: {ruta}")
        fallas += 1
    pend = [x for x in res["prohibidos"] if x[1] == "PENDIENTE"]
    otros = [x for x in res["prohibidos"] if x[1] != "PENDIENTE"]
    for n, palabra, sec in otros:
        print(f"FALLA línea {n} ({sec}): aparece {palabra}")
        fallas += 1
    for n, k in res["citas"]:
        print(f"FALLA línea {n}: la cita [@{k}] no está en referencias.bib")
        fallas += 1
    for fuente, sa, la, na, sb, lb, nb in res["discrepancias"]:
        print(f"FALLA misma fuente '{fuente}' con valores distintos: {sa} (línea {la}) {na} frente a {sb} (línea {lb}) {nb}")
        fallas += 1
    for fuente, sa, la, na, sb, lb, nb in res["avisos"]:
        print(f"AVISO misma ruta '{fuente}' sin valores en común ({sa}:{la} {na} / {sb}:{lb} {nb}); si es la misma "
              f"métrica, usa 'ruta:clave'")
    if pend:
        print(f"PENDIENTE: {len(pend)} marcadores en el texto final (también hacen fallar):")
        for n, _, sec in pend[:30]:
            print(f"  línea {n} ({sec})")
        fallas += len(pend)
    print("RESULTADO:", "OK" if fallas == 0 else f"FALLA ({fallas} problemas)")
    return 0 if fallas == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", type=Path, default=AQUI / "salida" / "informe_e-sert.md")
    ap.add_argument("--bib", type=Path, default=None)
    a = ap.parse_args(argv)
    if not a.md.is_file():
        print(f"No existe {a.md}: corre primero construir_informe.py")
        return 1
    return imprimir(verificar(a.md, a.bib or a.md.parent.parent / "referencias.bib"))


if __name__ == "__main__":
    sys.exit(main())
