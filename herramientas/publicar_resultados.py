"""Publica en main los resultados de las ramas <nombre>/sN para que el roadmap los muestre.

El roadmap (e-sert.tesisucuenca.com) se redepliega con cada push a main, pero el trabajo de
cada sesión vive en la rama <nombre>/sN hasta la unificación del domingo. Este script copia a
main, sin código, solo lo que el roadmap muestra:

    semanas/SN/<Nombre>/estado.json, RESUMEN.md, evidencias/ y explicaciones/
    bitacoras/<nombre>.md   (de la rama de la semana más reciente de esa persona)

Reglas:
- Solo semanas sin unificar: si main ya tiene semanas/SN/unificacion-resultado.md, manda main.
- Cada ruta queda igual a la de la punta de la rama (incluidos archivos borrados), así que en
  la unificación ambos lados coinciden y la fusión no choca.
- Trabaja en un worktree temporal: no toca la rama ni el árbol de trabajo actuales.
- Nunca usa push --force: si main avanzó, vuelve a empezar desde el main nuevo (3 intentos).

Lo ejecuta la GitHub Action .github/workflows/publicar-resultados.yml en cada push a una rama
<nombre>/sN y cada hora. A mano:
    python herramientas/publicar_resultados.py            # muestra qué cambiaría
    python herramientas/publicar_resultados.py --push     # además hace commit y push a main
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PERSONAS = ["Tyrone", "Freddy", "Pablo", "Miguel"]
RAMA = re.compile(r"^origin/(tyrone|freddy|pablo|miguel)/s([1-4])$")
RESULTADOS = ["estado.json", "RESUMEN.md", "evidencias", "explicaciones"]
INTENTOS = 3


def git(*args, cwd=None, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r


def existe(ref, ruta, cwd):
    return git("cat-file", "-e", f"{ref}:{ruta}", cwd=cwd, check=False).returncode == 0


def ramas_pendientes(cwd):
    """{persona: [(N, rama)]} de las semanas que todavía no se unificaron en main."""
    salida = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin", cwd=cwd).stdout
    por_persona = {}
    for linea in salida.split():
        m = RAMA.match(linea)
        if not m:
            continue
        persona, n = m.group(1).capitalize(), int(m.group(2))
        if existe("origin/main", f"semanas/S{n}/unificacion-resultado.md", cwd):
            continue
        por_persona.setdefault(persona, []).append((n, linea))
    return {p: sorted(v) for p, v in por_persona.items()}


def secciones(texto):
    """Divide una bitácora en (preámbulo, [(semana o None, texto de la entrada)])."""
    partes = re.split(r"(?m)^(?=## )", texto)
    preambulo = partes[0] if partes and not partes[0].startswith("## ") else ""
    entradas = []
    for p in partes:
        if p.startswith("## "):
            m = re.match(r"## S(\d) ", p)
            entradas.append((int(m.group(1)) if m else None, p))
    return preambulo, entradas


def fusionar_bitacora(en_main, por_semana):
    """Bitácora de main con las entradas de las semanas pendientes tomadas de su rama.

    Se fusiona por entradas y no se copia el archivo entero porque una rama creada antes de la
    unificación anterior no tiene las entradas de esa semana, y copiarla las borraría de main.
    """
    preambulo, entradas = secciones(en_main)
    cuerpo = [t for s, t in entradas if s not in por_semana]
    for n in sorted(por_semana):
        cuerpo += [t for s, t in secciones(por_semana[n])[1] if s == n]
    cuerpo = [t.rstrip("\n") + "\n" for t in cuerpo]
    return preambulo + "\n".join(cuerpo)


def sincronizar(arbol, pendientes):
    """Deja en el worktree `arbol` las rutas de resultados igual que en cada rama."""
    for persona, ramas in pendientes.items():
        for n, rama in ramas:
            for x in RESULTADOS:
                ruta = f"semanas/S{n}/{persona}/{x}"
                git("rm", "-r", "-q", "--ignore-unmatch", "--", ruta, cwd=arbol)
                if existe(rama, ruta, arbol):
                    git("checkout", rama, "--", ruta, cwd=arbol)
        ruta = f"bitacoras/{persona.lower()}.md"
        por_semana = {n: git("show", f"{rama}:{ruta}", cwd=arbol).stdout
                      for n, rama in ramas if existe(rama, ruta, arbol)}
        archivo = arbol / ruta
        en_main = archivo.read_text(encoding="utf-8") if archivo.exists() else ""
        nuevo = fusionar_bitacora(en_main, por_semana)
        if nuevo != en_main:
            archivo.write_text(nuevo, encoding="utf-8", newline="\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--push", action="store_true", help="hace commit y push a main")
    args = ap.parse_args()

    raiz = Path(git("rev-parse", "--show-toplevel").stdout.strip())
    for intento in range(1, INTENTOS + 1):
        git("fetch", "-q", "--prune", "origin", cwd=raiz)
        pendientes = ramas_pendientes(raiz)
        if not pendientes:
            print("No hay ramas de semanas sin unificar.")
            return 0
        with tempfile.TemporaryDirectory(prefix="esert-publicar-") as tmp:
            arbol = Path(tmp) / "main"
            git("worktree", "add", "-q", "--detach", str(arbol), "origin/main", cwd=raiz)
            try:
                sincronizar(arbol, pendientes)
                git("add", "-A", cwd=arbol)
                cambios = git("diff", "--cached", "--stat", cwd=arbol).stdout.strip()
                if not cambios:
                    print("main ya tiene los resultados de:",
                          ", ".join(r for v in pendientes.values() for _, r in v))
                    return 0
                print(cambios)
                if not args.push:
                    print("\n(sin --push: no se hizo commit)")
                    return 0
                tocados = git("diff", "--cached", "--name-only", cwd=arbol).stdout.split()
                carpetas = sorted({"/".join(x.split("/")[:3]) if x.startswith("semanas/") else x
                                   for x in tocados})
                git("commit", "-q", "-m", "[Roadmap] Publica resultados de las ramas sin unificar",
                    "-m", "\n".join(f"- {c}" for c in carpetas), cwd=arbol)
                if git("push", "-q", "origin", "HEAD:main", cwd=arbol, check=False).returncode == 0:
                    print("Publicado en main.")
                    return 0
                print(f"main avanzó; reintento {intento}/{INTENTOS}", file=sys.stderr)
            finally:
                git("worktree", "remove", "--force", str(arbol), cwd=raiz, check=False)
    print("No se pudo publicar tras varios intentos.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
