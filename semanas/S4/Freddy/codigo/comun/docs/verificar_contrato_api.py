"""Compara la API real (FastAPI) con la tabla §4.3 de `docs/CONTRATO.md` y genera la referencia (S4-2).

    python comun/docs/verificar_contrato_api.py          # desde la carpeta con backend/ y comun/

1. Importa la app (`backend.api.main.crear_app`, SQLite en memoria) y vuelca `app.openapi()` a
   `comun/docs/openapi.json`.
2. Lee la tabla de rutas de la §4.3 del contrato y, por cada fila, comprueba:
   - que el método y la ruta existan (con el prefijo `/api/v1`);
   - el código de éxito si la fila lo dice (`201`, `202`);
   - los modelos de la columna "Modelo" (cuerpo → respuesta);
   - los campos del cuerpo y de la respuesta escritos como `{a, b, c?}` (los `?` son opcionales).
3. Avisa de las rutas de la app que el contrato no menciona.
4. Escribe `comun/docs/api.md`: una tabla por endpoint con un ejemplo de `comun/ejemplos/`.

Sale con código 1 si hay diferencias (las lista) y 0 si todo cuadra.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parents[1]  # carpeta con backend/ y comun/
if str(CODIGO) not in sys.path:
    sys.path.insert(0, str(CODIGO))

PREFIJO = "/api/v1"
EJEMPLOS = CODIGO / "comun" / "ejemplos"
# Modelo del contrato → archivo de ejemplo en comun/ejemplos/ (o comun/tarifa.json).
EJEMPLO_DE = {
    "Salud": "salud.json", "Tarifa": "../tarifa.json", "Puesto": "puestos.json", "ConsultaGuia": "guia_consulta.json",
    "Guia": "guia.json", "PasoSimulacion": "sim_paso.json", "MensajeKpi": "kpi_ws.json",
    "EventoUbicacion": "ubicacion.json", "EventoModo": "modo.json", "NuevaSesion": "sesion_crear.json",
    "SesionCreada": "sesion_creada.json", "TransicionSesion": "sesion_transicion.json",
    "EstadoActualSesion": "sesion_estado.json", "CierreSesion": "sesion_cerrar.json",
    "SesionCerrada": "sesion_cerrada.json", "Sesion": "sesion.json", "Billetera": "billetera.json",
    "Recarga": "recarga.json", "RecargaHecha": "recarga_hecha.json", "CandidatoEspejo": "candidatos_espejo.json",
    "Aceptado": "aceptado.json",
}


# --------------------------------------------------------------------------- contrato


def buscar_contrato() -> Path:
    for p in AQUI.parents:
        if (p / "docs" / "CONTRATO.md").is_file():
            return p / "docs" / "CONTRATO.md"
    raise SystemExit("No encontré docs/CONTRATO.md subiendo desde comun/docs/")


def campos(texto: str) -> Optional[Dict[str, bool]]:
    """`{a, b?, c: "x"|"y", d: [...]}` → `{"a": True, "b": False, "c": True, "d": True}` (True = obligatorio).

    None si la celda no trae un objeto entre llaves (p. ej. "Sesión completa")."""
    m = re.search(r"\{([^{}]*)\}", texto.replace("\\|", "|"))
    if not m:
        return None
    salida = {}
    for parte in re.split(r",(?![^\[]*\])", m.group(1)):
        nombre = parte.strip().split(":")[0].strip().strip("`")
        if not nombre or nombre.startswith("."):
            continue
        opcional = nombre.endswith("?")
        salida[nombre.rstrip("?")] = not opcional
    return salida


def leer_tabla_rutas(contrato: Path) -> List[dict]:
    """Filas de la tabla de §4.3: método, ruta, token, cuerpo, respuesta y modelos."""
    texto = contrato.read_text(encoding="utf-8")
    seccion = texto[texto.index("### 4.3 Rutas"):]
    seccion = seccion[:seccion.index("\n## ", 1)]
    filas = []
    for linea in seccion.splitlines():
        if not linea.startswith("| ") or linea.startswith("| Método") or set(linea) <= set("|- "):
            continue
        celdas = [c.strip() for c in re.split(r"(?<!\\)\|", linea)[1:-1]]
        if len(celdas) != 4:
            continue
        ruta_celda, cuerpo, respuesta, modelo = celdas
        m = re.search(r"`(GET|POST|PUT|PATCH|DELETE) ([^`]+)`", ruta_celda)
        if not m:
            continue
        modelos = [x.strip(" `") for x in modelo.split("→")]
        codigo = re.match(r"`?(\d{3})", respuesta)
        filas.append({
            "metodo": m.group(1), "ruta": m.group(2), "token": "🔒" in ruta_celda,
            "cuerpo_txt": cuerpo, "respuesta_txt": respuesta,
            "cuerpo": campos(cuerpo) if m.group(1) != "GET" else None,
            "respuesta": campos(respuesta), "codigo": codigo.group(1) if codigo else None,
            "modelo_cuerpo": modelos[0] if len(modelos) == 2 or m.group(1) != "GET" else None,
            "modelo_respuesta": modelos[-1] if len(modelos) == 2 or m.group(1) == "GET" else None,
        })
    return filas


# --------------------------------------------------------------------------- OpenAPI


def cargar_openapi() -> dict:
    import logging

    logging.disable(logging.INFO)
    from backend.api.main import Config, crear_app

    app = crear_app(Config(db_url="sqlite:///:memory:", visor_dir=None))
    return app.openapi()


def resolver(esquema: dict, o: dict) -> Tuple[Optional[str], dict]:
    """(nombre del modelo, esquema del objeto), siguiendo `$ref` y `items` de listas."""
    if "items" in esquema:
        esquema = esquema["items"]
    for clave in ("allOf", "anyOf"):
        if clave in esquema:
            esquema = next((x for x in esquema[clave] if "$ref" in x), esquema)
    ref = esquema.get("$ref")
    if not ref:
        return None, esquema
    nombre = ref.split("/")[-1]
    return nombre, o["components"]["schemas"][nombre]


def operacion(o: dict, metodo: str, ruta: str) -> Optional[dict]:
    plantilla = re.sub(r"\{[^}]+\}", "{}", PREFIJO + ruta)
    for p, ops in o["paths"].items():
        if re.sub(r"\{[^}]+\}", "{}", p) == plantilla and metodo.lower() in ops:
            return ops[metodo.lower()]
    return None


def exito(op: dict) -> Tuple[str, dict]:
    codigo = next(c for c in op["responses"] if c.startswith("2"))
    return codigo, op["responses"][codigo].get("content", {}).get("application/json", {}).get("schema", {})


def comparar(filas: List[dict], o: dict) -> List[str]:
    diferencias = []
    vistas: Set[Tuple[str, str]] = set()
    for f in filas:
        nombre = f"{f['metodo']} {f['ruta']}"
        op = operacion(o, f["metodo"], f["ruta"])
        if op is None:
            diferencias.append(f"{nombre}: está en el contrato pero no en la app")
            continue
        vistas.add((f["metodo"], re.sub(r"\{[^}]+\}", "{}", f["ruta"])))
        codigo, esq_resp = exito(op)
        if f["token"] != ("401" in op["responses"]):
            diferencias.append(f"{nombre}: el contrato {'marca' if f['token'] else 'no marca'} 🔒 y la app "
                               f"{'exige' if '401' in op['responses'] else 'no exige'} token")
        if f["codigo"] and f["codigo"] != codigo:
            diferencias.append(f"{nombre}: el contrato dice {f['codigo']} y la app responde {codigo}")
        # cuerpo
        esq_cuerpo = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
        if f["metodo"] != "GET":
            modelo_real, obj = resolver(esq_cuerpo or {}, o)
            if f["modelo_cuerpo"] and f["modelo_cuerpo"] != modelo_real:
                diferencias.append(f"{nombre}: cuerpo {modelo_real}, el contrato dice {f['modelo_cuerpo']}")
            if f["cuerpo"] is not None:
                diferencias += comparar_campos(nombre, "cuerpo", f["cuerpo"], obj, con_requeridos=True)
        # respuesta
        modelo_real, obj = resolver(esq_resp, o)
        if f["modelo_respuesta"] and f["modelo_respuesta"] != modelo_real:
            diferencias.append(f"{nombre}: respuesta {modelo_real}, el contrato dice {f['modelo_respuesta']}")
        if f["respuesta"] is not None:
            diferencias += comparar_campos(nombre, "respuesta", f["respuesta"], obj, con_requeridos=False)
    # rutas de la app que el contrato no menciona (la raíz /salud está en la fila de GET /salud)
    for p, ops in o["paths"].items():
        if not p.startswith(PREFIJO):
            continue
        for m in ops:
            clave = (m.upper(), re.sub(r"\{[^}]+\}", "{}", p[len(PREFIJO):]))
            if clave not in vistas:
                diferencias.append(f"{m.upper()} {p}: está en la app pero no en la tabla §4.3")
    return diferencias


def comparar_campos(nombre: str, lado: str, contrato: Dict[str, bool], esquema: dict,
                    con_requeridos: bool) -> List[str]:
    reales = set(esquema.get("properties", {}))
    requeridos = set(esquema.get("required", []))
    salida = []
    if faltan := sorted(set(contrato) - reales):
        salida.append(f"{nombre}: {lado} sin los campos del contrato {faltan}")
    if sobran := sorted(reales - set(contrato)):
        salida.append(f"{nombre}: {lado} con campos que el contrato no lista {sobran}")
    if con_requeridos:
        for campo, obligatorio in contrato.items():
            if campo in reales and obligatorio != (campo in requeridos):
                salida.append(f"{nombre}: {lado}.{campo} es {'obligatorio' if campo in requeridos else 'opcional'} "
                              f"en la app y {'obligatorio' if obligatorio else 'opcional'} en el contrato")
    return salida


# --------------------------------------------------------------------------- api.md


def tipo(prop: dict, o: dict) -> str:
    if "$ref" in prop:
        return prop["$ref"].split("/")[-1]
    if "anyOf" in prop:
        return " \\| ".join(tipo(x, o) for x in prop["anyOf"])
    if prop.get("type") == "array":
        return f"[{tipo(prop.get('items', {}), o)}]"
    if "enum" in prop:
        return " \\| ".join(f'"{v}"' for v in prop["enum"])
    t = prop.get("type", "objeto")
    return {"string": "texto", "number": "número", "integer": "entero", "boolean": "bool", "null": "null"}.get(t, t) + (
        f" ({prop['format']})" if "format" in prop else "")


def tabla_campos(esquema: dict, o: dict) -> List[str]:
    props = esquema.get("properties", {})
    if not props:
        return ["_Sin cuerpo JSON._", ""]
    req = set(esquema.get("required", []))
    lineas = ["| Campo | Tipo | Obligatorio |", "|---|---|---|"]
    lineas += [f"| `{k}` | {tipo(v, o)} | {'sí' if k in req else 'no'} |" for k, v in props.items()]
    return lineas + [""]


def ejemplo(modelo: Optional[str]) -> List[str]:
    archivo = EJEMPLO_DE.get(modelo or "")
    if not archivo:
        return []
    ruta = (EJEMPLOS / archivo).resolve()
    if not ruta.is_file():
        return []
    texto = json.dumps(json.loads(ruta.read_text(encoding="utf-8")), ensure_ascii=False, indent=2)
    lineas = texto.splitlines()
    if len(lineas) > 30:
        lineas = lineas[:30] + ["  …"]
    return [f"Ejemplo (`comun/{ruta.relative_to(CODIGO / 'comun').as_posix()}`):", "", "```json", *lineas, "```", ""]


def escribir_api_md(filas: List[dict], o: dict, diferencias: List[str], destino: Path) -> None:
    lineas = [
        "# Referencia de la API de e-sert (generada)",
        "",
        "Generado por `comun/docs/verificar_contrato_api.py` desde `app.openapi()` (contrato "
        f"v{o['info']['version']}). No editar a mano: vuelve a correr el script.",
        "",
        "- Prefijo: `/api/v1`. Todas las respuestas llevan `X-Contrato-Version: 1`; si la app manda otra "
        "versión, `400 CONTRATO_INCOMPATIBLE`.",
        "- 🔒 = exige `X-Sim-Token: <ESERT_TOKEN_SIM>` (o `Authorization: Bearer …`); si falta, "
        "`401 TOKEN_SIM_INVALIDO`.",
        "- Errores: `{\"error\": {\"codigo\", \"mensaje\", \"detalle?\"}}` (contrato §4.2).",
        "- Esquema completo: [`openapi.json`](openapi.json). WebSockets: al final.",
        "",
        f"**Verificación contra `docs/CONTRATO.md` §4.3:** "
        + ("sin diferencias." if not diferencias else f"{len(diferencias)} diferencias (ver la salida del script)."),
        "",
        "| Método | Ruta | Éxito | Cuerpo | Respuesta |",
        "|---|---|---|---|---|",
    ]
    for f in filas:
        op = operacion(o, f["metodo"], f["ruta"])
        if op is None:
            continue
        codigo, esq = exito(op)
        cuerpo = resolver(op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}), o)[0]
        lineas.append(f"| {f['metodo']} | {'🔒 ' if f['token'] else ''}`{f['ruta']}` | {codigo} | "
                      f"{cuerpo or '—'} | {resolver(esq, o)[0] or '—'} |")
    lineas.append("")
    for f in filas:
        op = operacion(o, f["metodo"], f["ruta"])
        if op is None:
            continue
        codigo, esq = exito(op)
        lineas += [f"## {'🔒 ' if f['token'] else ''}`{f['metodo']} {PREFIJO}{f['ruta']}`", ""]
        if op.get("summary"):
            lineas += [f"**{op['summary']}.** " + (op.get("description", "").split("\n")[0]), ""]
        params = [p for p in op.get("parameters", []) if p.get("in") in ("path", "query")]
        if params:
            lineas += ["Parámetros:", "", "| Nombre | En | Tipo | Obligatorio |", "|---|---|---|---|"]
            lineas += [f"| `{p['name']}` | {p['in']} | {tipo(p.get('schema', {}), o)} | "
                       f"{'sí' if p.get('required') else 'no'} |" for p in params]
            lineas.append("")
        esq_cuerpo = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
        if esq_cuerpo:
            nombre, obj = resolver(esq_cuerpo, o)
            lineas += [f"Cuerpo: `{nombre}`", ""] + tabla_campos(obj, o) + ejemplo(nombre)
        nombre, obj = resolver(esq, o)
        lista = "items" in esq
        lineas += [f"Respuesta `{codigo}`: {'lista de ' if lista else ''}`{nombre or 'objeto'}`", ""]
        lineas += tabla_campos(obj, o) + ejemplo(nombre)
        errores = sorted(c for c in op["responses"] if not c.startswith("2"))
        if errores:
            lineas += ["Otros códigos: " + ", ".join(f"`{c}`" for c in errores), ""]
    lineas += [
        "## WebSockets (fuera de OpenAPI)",
        "",
        "| Ruta | Quién se conecta | Mensajes (`tipo`) | Ejemplo |",
        "|---|---|---|---|",
        "| `/ws/estado?rol=visor` | visor (proyector) | `snapshot`, `kpi`, `verdad` | `snapshot_ws.json`, `kpi_ws.json`, `verdad_ws.json` |",
        "| `/ws/estado?rol=publico` | app | `snapshot`, `kpi` (nunca `verdad`) | `snapshot_ws.json` |",
        "| `/ws/espejo/{veh_id}` | app espejo | `espejo` (≤ 1 Hz, `recibo` una vez), `espejo_fin` | `espejo_ws.json`, `espejo_recibo_ws.json`, `espejo_fin_ws.json` |",
        "",
        "Todos los mensajes se validan con la unión discriminada `MensajeWS` de `comun/esquemas.py` "
        "(`leer_mensaje_ws`). Como máximo un `snapshot` por segundo simulado (contrato §6).",
        "",
    ]
    destino.write_text("\n".join(lineas), encoding="utf-8")


# --------------------------------------------------------------------------- main


def main() -> int:
    o = cargar_openapi()
    (AQUI / "openapi.json").write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    contrato = buscar_contrato()
    filas = leer_tabla_rutas(contrato)
    if not filas:
        print(f"No pude leer la tabla §4.3 de {contrato}")
        return 1
    diferencias = comparar(filas, o)
    escribir_api_md(filas, o, diferencias, AQUI / "api.md")
    print(f"{len(filas)} rutas del contrato comparadas con {sum(len(v) for v in o['paths'].values())} "
          f"operaciones de la app → openapi.json y api.md escritos en {AQUI.relative_to(CODIGO)}/")
    if not diferencias:
        print("Sin diferencias con docs/CONTRATO.md §4.3.")
        return 0
    print(f"\n{len(diferencias)} diferencias con docs/CONTRATO.md:")
    for d in diferencias:
        print(f"  - {d}")
    # ¿Las cubre la propuesta del custodio? (se aplica a docs/CONTRATO.md en la unificación)
    propuesta = CODIGO / "comun" / "CONTRATO.propuesto.md"
    if propuesta.is_file():
        pendientes = comparar(leer_tabla_rutas(propuesta), o)
        if not pendientes:
            print(f"\nTodas están propuestas en comun/CONTRATO.propuesto.md: OK hasta la unificación.")
            return 0
        print(f"\n{len(pendientes)} siguen sin resolver ni proponer en comun/CONTRATO.propuesto.md:")
        for d in pendientes:
            print(f"  - {d}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
