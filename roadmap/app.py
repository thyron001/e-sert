"""
==========================================================================================
 e-sert — Roadmap del proyecto (Flask)
==========================================================================================
 Sitio del equipo (e-sert.tesisucuenca.com). Lee el propio repositorio y muestra:

   · /                      Línea de progreso, estado de cada persona y las 4 semanas con
                            sus 48 sesiones; cada sesión abre su prompt listo para copiar.
   · /persona/<nombre>      Bitácora, evidencias y PDFs de una persona.
   · /doc/<nombre>          Documentos del proyecto (contexto, contrato, equipo, plan).
   · /archivo/<ruta>        Evidencias y PDFs (solo dentro de semanas/ y bitacoras/).
   · /api/progreso          El mismo estado en JSON.

 No hay base de datos: la verdad son los archivos del repo (sesion-K.md, estado.json,
 bitácoras). Cada push a main redepliega el sitio y el progreso se actualiza solo.
==========================================================================================
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import markdown as md
import yaml
from flask import Flask, abort, jsonify, render_template, send_from_directory
from markupsafe import Markup

# --------------------------------------------------------------------------------------
# [0] Configuración
# --------------------------------------------------------------------------------------
RAIZ = Path(os.environ.get("ESERT_RAIZ", Path(__file__).resolve().parent.parent))
TZ_EC = timezone(timedelta(hours=-5))

PERSONAS = {
    "Tyrone": {"color": "#1E63D6", "tinte": "#E8F0FC", "emoji": "🔵", "color_nombre": "Azul",
               "rol": "Escenario SUMO, experimentos, KPIs y visor web"},
    "Freddy": {"color": "#FF7043", "tinte": "#FFF0EA", "emoji": "🍅", "color_nombre": "Tomate",
               "rol": "Controlador TraCI, emulador GPS, guiado y backend"},
    "Pablo": {"color": "#2E9E4F", "tinte": "#E8F6ED", "emoji": "🟢", "color_nombre": "Verde",
              "rol": "IA: dataset, clasificador de movimiento e inferencia"},
    "Miguel": {"color": "#C62828", "tinte": "#FBEAEA", "emoji": "🔴", "color_nombre": "Rojo",
               "rol": "App Expo: sensores, sesión de parqueo, billetera y Payphone"},
}

SEMANAS = {
    "S1": {"titulo": "Cimientos y contrato", "inicio": date(2026, 10, 19), "fin": date(2026, 10, 25)},
    "S2": {"titulo": "Piezas funcionando por separado", "inicio": date(2026, 10, 26), "fin": date(2026, 11, 1)},
    "S3": {"titulo": "Integración y experimentos", "inicio": date(2026, 11, 2), "fin": date(2026, 11, 8)},
    "S4": {"titulo": "Cierre, demo e informe", "inicio": date(2026, 11, 9), "fin": date(2026, 11, 15)},
}
INICIO, ENTREGA = date(2026, 10, 19), date(2026, 11, 16)
SESIONES_POR_SEMANA = 3

DOCS = {
    "contexto": ("CONTEXTO.md", "Contexto y alcance"),
    "plan": ("PLAN.md", "Plan de 4 semanas"),
    "equipo": ("EQUIPO.md", "Equipo y calendario"),
    "contrato": ("CONTRATO.md", "Contrato de interfaces"),
    "despliegue": ("DESPLIEGUE.md", "Demo en el VPS"),
}

ESTADOS = {
    "hecha": ("Hecha", "ok"),
    "parcial": ("Parcial", "parcial"),
    "bloqueada": ("Bloqueada", "bloq"),
    "pendiente": ("Pendiente", "pend"),
}

app = Flask(__name__)


# --------------------------------------------------------------------------------------
# [1] Lectura del repositorio
# --------------------------------------------------------------------------------------
def _frontmatter(texto: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", texto, flags=re.S)
    if not m:
        return {}, texto
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, m.group(2)


def _md(texto: str) -> Markup:
    return Markup(md.markdown(texto, extensions=["fenced_code", "tables", "sane_lists"]))


def hoy() -> date:
    forzada = os.environ.get("ESERT_HOY")  # para pruebas: ESERT_HOY=2026-10-28
    return date.fromisoformat(forzada) if forzada else datetime.now(TZ_EC).date()


def semana_actual(d: date) -> str | None:
    for k, s in SEMANAS.items():
        if s["inicio"] <= d <= s["fin"]:
            return k
    return "S4" if d > SEMANAS["S4"]["fin"] else None


def _leer_estado(semana: str, persona: str) -> dict:
    p = RAIZ / "semanas" / semana / persona / "estado.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("sesiones", {})
    except (OSError, ValueError):
        return {}


def cargar() -> dict:
    """Arma todo el estado del proyecto a partir de los archivos."""
    d = hoy()
    actual = semana_actual(d)
    semanas = []
    for sk, sinfo in SEMANAS.items():
        carriles = []
        for persona in PERSONAS:
            estado = _leer_estado(sk, persona)
            sesiones = []
            for k in range(1, SESIONES_POR_SEMANA + 1):
                ruta = RAIZ / "semanas" / sk / persona / f"sesion-{k}.md"
                meta, cuerpo = ({}, "")
                if ruta.exists():
                    meta, cuerpo = _frontmatter(ruta.read_text(encoding="utf-8"))
                e = estado.get(f"sesion-{k}", {})
                est = e.get("estado", "pendiente")
                if est not in ESTADOS:
                    est = "pendiente"
                base = f"semanas/{sk}/{persona}/"
                sesiones.append({
                    "id": f"{sk}-{persona}-{k}",
                    "k": k,
                    "existe": ruta.exists(),
                    "titulo": meta.get("titulo", f"Sesión {k}"),
                    "horas": meta.get("horas", ""),
                    "modulo": meta.get("modulo", ""),
                    "depende": meta.get("depende") or [],
                    "entrega": meta.get("entrega") or [],
                    "evid_previstas": meta.get("evidencias") or [],
                    "prompt": cuerpo.strip(),
                    "prompt_html": _md(cuerpo),
                    "comando": f"Soy {persona}. Ejecuta la sesión {k} de la semana {sk}.",
                    "estado": est,
                    "estado_txt": ESTADOS[est][0],
                    "estado_css": ESTADOS[est][1],
                    "fecha": e.get("fecha", ""),
                    "resumen": e.get("resumen", ""),
                    "criterios": e.get("criterios", {}),
                    "pendientes": e.get("pendientes", []),
                    "evidencias": [base + x for x in e.get("evidencias", [])
                                   if (RAIZ / base / x).exists()],
                    "explicacion": (base + e["explicacion"]) if e.get("explicacion")
                                   and (RAIZ / base / e["explicacion"]).exists() else "",
                })
            hechas = sum(s["estado"] == "hecha" for s in sesiones)
            pdf_sem = f"semanas/{sk}/{persona}/evidencias/resumen_{sk}_{persona}.pdf"
            carriles.append({
                "persona": persona, **PERSONAS[persona], "sesiones": sesiones, "hechas": hechas,
                "pdf_semanal": pdf_sem if (RAIZ / pdf_sem).exists() else "",
            })
        unif = RAIZ / "semanas" / sk / "unificacion-resultado.md"
        semanas.append({
            "clave": sk, **sinfo,
            "larga": f"{sinfo['inicio'].day} {_mes(sinfo['inicio'])} – {sinfo['fin'].day} {_mes(sinfo['fin'])}",
            "carriles": carriles,
            "hechas": sum(c["hechas"] for c in carriles),
            "total": SESIONES_POR_SEMANA * len(PERSONAS),
            "es_actual": sk == actual,
            "pasada": sinfo["fin"] < d,
            "unificada": unif.exists(),
            "unificacion_html": _md(unif.read_text(encoding="utf-8")) if unif.exists() else "",
            "unificacion_prompt": _frontmatter((RAIZ / "semanas" / sk / "unificacion.md").read_text(encoding="utf-8"))[1]
                                  if (RAIZ / "semanas" / sk / "unificacion.md").exists() else "",
        })

    total = len(SEMANAS) * len(PERSONAS) * SESIONES_POR_SEMANA
    hechas = sum(s["hechas"] for s in semanas)
    return {
        "hoy": d, "semana_actual": actual, "semanas": semanas,
        "hechas": hechas, "total": total, "pct": round(100 * hechas / total),
        "personas": [estado_persona(p, semanas, actual, d) for p in PERSONAS],
        "linea": linea_tiempo(d, semanas),
        "dias_entrega": (ENTREGA - d).days,
    }


def _mes(d: date) -> str:
    return ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"][d.month - 1]


def estado_persona(persona: str, semanas: list, actual: str | None, d: date) -> dict:
    """Frase de estado de una persona: en qué sesión va y si está al día."""
    info = {"persona": persona, **PERSONAS[persona]}
    todas = [(s["clave"], ses) for s in semanas for c in s["carriles"] if c["persona"] == persona
             for ses in c["sesiones"]]
    hechas = sum(ses["estado"] == "hecha" for _, ses in todas)
    info["hechas"], info["total"] = hechas, len(todas)
    info["pct"] = round(100 * hechas / len(todas))
    info["puntos"] = [{"id": ses["id"], "estado": ses["estado_css"], "sem": sk,
                       "titulo": ses["titulo"]} for sk, ses in todas]

    atrasadas = [ses for sk, ses in todas
                 if SEMANAS[sk]["fin"] < d and ses["estado"] != "hecha"]
    if actual is None:
        info["frase"], info["tono"] = "El proyecto empieza el lunes 19 de octubre", "neutro"
        return info
    de_semana = [ses for sk, ses in todas if sk == actual]
    siguiente = next((ses for ses in de_semana if ses["estado"] != "hecha"), None)
    hechas_sem = sum(ses["estado"] == "hecha" for ses in de_semana)
    if hechas == len(todas):
        info["frase"], info["tono"] = "Proyecto completado", "ok"
    elif siguiente is None:
        info["frase"], info["tono"] = f"{actual} · semana completada ✓", "ok"
    elif siguiente["estado"] == "bloqueada":
        info["frase"], info["tono"] = f"{actual} · sesión {siguiente['k']} bloqueada", "mal"
    else:
        verbo = "en curso" if hechas_sem else "por empezar"
        info["frase"] = f"{actual} · sesión {siguiente['k']} de {SESIONES_POR_SEMANA} {verbo}"
        info["tono"] = "curso"
    info["siguiente"] = siguiente
    info["hechas_semana"] = hechas_sem
    if atrasadas:
        info["atraso"] = f"{len(atrasadas)} sesión(es) atrasada(s) de semanas anteriores"
        if info["tono"] != "mal":
            info["tono"] = "atraso"
    return info


def linea_tiempo(d: date, semanas: list) -> dict:
    """Posiciones (en %) de la línea de progreso: semanas, unificaciones, hoy y entrega."""
    largo = (ENTREGA - INICIO).days
    pos = lambda x: max(0.0, min(100.0, 100 * (x - INICIO).days / largo))
    tramos = [{"clave": s["clave"], "titulo": s["titulo"], "izq": pos(s["inicio"]),
               "ancho": pos(s["fin"] + timedelta(days=1)) - pos(s["inicio"]),
               "pct": round(100 * s["hechas"] / s["total"]), "es_actual": s["es_actual"],
               "pasada": s["pasada"]} for s in semanas]
    hitos = [{"pos": pos(s["fin"]), "txt": f"Unificación {s['clave']}", "fecha": f"dom {s['fin'].day} {_mes(s['fin'])} 09:00",
              "hecho": s["unificada"]} for s in semanas]
    hitos.append({"pos": 100.0, "txt": "Entrega", "fecha": "lun 16 nov", "hecho": False, "final": True})
    return {"tramos": tramos, "hitos": hitos, "hoy": pos(d) if INICIO <= d <= ENTREGA else None,
            "tiempo_pct": round(pos(d))}


# --------------------------------------------------------------------------------------
# [2] Páginas
# --------------------------------------------------------------------------------------
app.add_template_filter(_md, "markdown")


@app.context_processor
def _globales():
    return {"PERSONAS": PERSONAS, "DOCS": DOCS}


@app.route("/")
def inicio():
    return render_template("inicio.html", p=cargar())


@app.route("/persona/<nombre>")
def persona(nombre):
    nombre = nombre.capitalize()
    if nombre not in PERSONAS:
        abort(404)
    p = cargar()
    bit = RAIZ / "bitacoras" / f"{nombre.lower()}.md"
    texto = bit.read_text(encoding="utf-8") if bit.exists() else ""
    # Las imágenes de la bitácora apuntan a ../semanas/...: se sirven por /archivo/
    texto = texto.replace("](../semanas/", "](/archivo/semanas/")
    info = next(x for x in p["personas"] if x["persona"] == nombre)
    return render_template("persona.html", p=p, info=info, bitacora=_md(texto), nombre=nombre)


@app.route("/doc/<clave>")
def doc(clave):
    if clave not in DOCS:
        abort(404)
    archivo, titulo = DOCS[clave]
    ruta = RAIZ / "docs" / archivo
    if not ruta.exists():
        abort(404)
    return render_template("doc.html", titulo=titulo, clave=clave,
                           cuerpo=_md(ruta.read_text(encoding="utf-8")))


@app.route("/archivo/<path:ruta>")
def archivo(ruta):
    if not (ruta.startswith("semanas/") or ruta.startswith("bitacoras/")) or ".." in ruta:
        abort(404)
    return send_from_directory(RAIZ, ruta)


@app.route("/api/progreso")
def api_progreso():
    p = cargar()
    return jsonify({
        "hoy": p["hoy"].isoformat(), "semana_actual": p["semana_actual"],
        "hechas": p["hechas"], "total": p["total"], "pct": p["pct"],
        "personas": [{k: v for k, v in x.items() if k in ("persona", "frase", "hechas", "total", "pct", "atraso")}
                     for x in p["personas"]],
        "semanas": [{"clave": s["clave"], "hechas": s["hechas"], "total": s["total"],
                     "sesiones": {c["persona"]: [x["estado"] for x in c["sesiones"]] for c in s["carriles"]}}
                    for s in p["semanas"]],
    })


if __name__ == "__main__":
    app.run(debug=True, port=5050)
