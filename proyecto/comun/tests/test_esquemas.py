"""Tests del contrato v1: ejemplos, casos inválidos, tarifa y paridad Python ↔ TypeScript.

Ejecutar desde la carpeta que contiene `comun/`:  pytest comun/tests
"""

from __future__ import annotations

import csv
import json
import re
import typing
from enum import Enum
from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from comun import esquemas as e
from comun import tarifa as t

COMUN = Path(__file__).resolve().parents[1]
EJEMPLOS = COMUN / "ejemplos"
# En semanas/ se lee la propuesta; en proyecto/ (tras la unificación) el contrato congelado.
CONTRATO = COMUN / "CONTRATO.propuesto.md"
if not CONTRATO.exists():
    CONTRATO = COMUN.parents[1] / "docs" / "CONTRATO.md"

# Archivo de ejemplo → modelo (o tipo) contra el que debe validar.
MODELO_POR_EJEMPLO = {
    "punto_gps.json": e.PuntoGPS,
    "ventana_gps.json": typing.List[e.PuntoGPS],
    "resultado_modo.json": e.ResultadoModo,
    "ubicacion.json": e.EventoUbicacion,
    "modo.json": e.EventoModo,
    "salud.json": e.Salud,
    "aceptado.json": e.Aceptado,
    "error.json": e.CuerpoError,
    "puestos.json": typing.List[e.Puesto],
    "guia_consulta.json": e.ConsultaGuia,
    "guia.json": e.Guia,
    "sesion_crear.json": e.NuevaSesion,
    "sesion_creada.json": e.SesionCreada,
    "sesion_transicion.json": e.TransicionSesion,
    "sesion_estado.json": e.EstadoActualSesion,
    "sesion_cerrar.json": e.CierreSesion,
    "sesion_cerrada.json": e.SesionCerrada,
    "sesion.json": e.Sesion,
    "billetera.json": e.Billetera,
    "recarga.json": e.Recarga,
    "recarga_hecha.json": e.RecargaHecha,
    "candidatos_espejo.json": typing.List[e.CandidatoEspejo],
    "sim_paso.json": e.PasoSimulacion,
    "snapshot_ws.json": e.MensajeSnapshot,
    "kpi_ws.json": e.MensajeKpi,
    "verdad_ws.json": e.MensajeVerdad,
    "espejo_ws.json": e.MensajeEspejo,
    "espejo_recibo_ws.json": e.MensajeEspejo,
    "espejo_fin_ws.json": e.MensajeEspejoFin,
}


def _leer(nombre: str):
    return json.loads((EJEMPLOS / nombre).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Cada ejemplo valida contra su modelo
# ---------------------------------------------------------------------------


def test_todo_ejemplo_tiene_modelo():
    """No puede haber un JSON en ejemplos/ sin modelo asignado (ni al revés)."""
    en_disco = {p.name for p in EJEMPLOS.glob("*.json")}
    assert en_disco == set(MODELO_POR_EJEMPLO)


@pytest.mark.parametrize("nombre", sorted(MODELO_POR_EJEMPLO))
def test_ejemplo_valida(nombre):
    TypeAdapter(MODELO_POR_EJEMPLO[nombre]).validate_python(_leer(nombre))


@pytest.mark.parametrize("nombre", sorted(MODELO_POR_EJEMPLO))
def test_ejemplo_ida_y_vuelta(nombre):
    """Validar y volver a serializar no pierde ni inventa campos."""
    adaptador = TypeAdapter(MODELO_POR_EJEMPLO[nombre])
    datos = _leer(nombre)
    vuelta = adaptador.dump_python(adaptador.validate_python(datos), mode="json")
    assert adaptador.validate_python(vuelta) == adaptador.validate_python(datos)
    if isinstance(datos, dict):
        assert set(vuelta) >= set(datos)


@pytest.mark.parametrize("nombre", sorted(n for n in MODELO_POR_EJEMPLO if n.endswith("_ws.json")))
def test_mensajes_ws_discriminados(nombre):
    """La unión MensajeWS elige el modelo correcto por `tipo`, desde dict y desde texto."""
    esperado = MODELO_POR_EJEMPLO[nombre]
    assert type(e.leer_mensaje_ws(_leer(nombre))) is esperado
    texto = (EJEMPLOS / nombre).read_text(encoding="utf-8")
    assert type(e.leer_mensaje_ws(texto)) is esperado


def test_traza_csv():
    with (EJEMPLOS / "traza.csv").open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        assert lector.fieldnames[:7] == e.COLUMNAS_TRAZA
        filas = [e.FilaTraza.desde_csv(fila) for fila in lector]
    assert len(filas) == 4
    assert filas[2].precision_m is None and filas[3].modo_real is None
    assert filas[0].modo_real is e.Modo.vehiculo


# ---------------------------------------------------------------------------
# 2. Ejemplos malos fallan
# ---------------------------------------------------------------------------


def _con(nombre: str, **cambios):
    datos = _leer(nombre)
    datos.update(cambios)
    return datos


CASOS_MALOS = [
    ("modo inventado", e.EventoModo, _con("modo.json", modo="bicicleta")),
    ("modo inventado en IA", e.ResultadoModo, _con("resultado_modo.json", modo="volando")),
    ("latitud fuera de rango", e.EventoUbicacion, _con("ubicacion.json", lat=-95.0)),
    ("longitud fuera de rango", e.PuntoGPS, _con("punto_gps.json", lon=200.0)),
    ("confianza > 1", e.EventoModo, _con("modo.json", confianza=1.3)),
    ("fuente desconocida", e.ResultadoModo, _con("resultado_modo.json", fuente="lstm")),
    ("hora sin zona", e.EventoUbicacion, _con("ubicacion.json", ts="2026-10-20T14:03:05")),
    ("origen desconocido", e.EventoUbicacion, _con("ubicacion.json", origen="gps")),
    ("usuario sin prefijo", e.EventoUbicacion, _con("ubicacion.json", usuario_id="veh42")),
    ("app con uuid malo", e.EventoUbicacion, _con("ubicacion.json", usuario_id="app_123")),
    ("puesto mal formado", e.NuevaSesion, _con("sesion_crear.json", puesto_id="-106945247#0")),
    ("placa mal formada", e.NuevaSesion, _con("sesion_crear.json", placa="abc 12")),
    ("campo desconocido", e.NuevaSesion, _con("sesion_crear.json", color="rojo")),
    ("estado inventado", e.TransicionSesion, _con("sesion_transicion.json", estado="DORMIDO")),
    ("sesión creada no ESTACIONADO", e.SesionCreada, _con("sesion_creada.json", estado="A_PIE")),
    ("motivo inventado", e.CierreSesion, _con("sesion_cerrar.json", motivo="aburrido")),
    ("sesion_id sin uuid", e.SesionCerrada, _con("sesion_cerrada.json", sesion_id="ses_1")),
    ("t_sim negativo", e.CierreSesion, _con("sesion_cerrar.json", t_sim=-1.0)),
    ("recarga en cero", e.Recarga, _con("recarga.json", monto=0)),
    ("código de error inventado", e.CuerpoError, {"error": {"codigo": "UPS", "mensaje": "x"}}),
    ("capacidad cero", e.Puesto, {**_leer("puestos.json")[0], "capacidad": 0}),
    ("aviso inventado", e.MensajeEspejo, _con("espejo_ws.json", avisos=["lluvia"])),
    ("ruta con 3 números", e.MensajeEspejo, _con("espejo_ws.json", ruta=[[1.0, 2.0, 3.0]])),
    ("peatón con prefijo de vehículo", e.Peaton, {"id": "sim_veh7", "lat": 0, "lon": 0}),
    ("motivo de fin inventado", e.MensajeEspejoFin, _con("espejo_fin_ws.json", motivo="x")),
]


@pytest.mark.parametrize("desc,modelo,datos", CASOS_MALOS, ids=[c[0] for c in CASOS_MALOS])
def test_ejemplo_malo_falla(desc, modelo, datos):
    with pytest.raises(ValidationError):
        modelo.model_validate(datos)


def test_ws_tipo_desconocido_falla():
    with pytest.raises(ValidationError):
        e.leer_mensaje_ws({"tipo": "chisme", "t_sim": 0, "ts": "2026-10-20T14:03:05Z"})


def test_ws_verdad_con_modo_inventado_en_espejo_falla():
    with pytest.raises(ValidationError):
        e.leer_mensaje_ws(_con("espejo_ws.json", modo="trotando"))


def test_traza_modo_inventado_falla():
    fila = {"usuario_id": "u", "t": "1", "lat": "0", "lon": "0", "precision_m": "",
            "velocidad_mps": "", "modo_real": "bus"}
    with pytest.raises(ValidationError):
        e.FilaTraza.desde_csv(fila)


# ---------------------------------------------------------------------------
# 3. Tarifa
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tarifa():
    return t.cargar_tarifa()


def test_tarifa_carga_y_coincide_con_contrato(tarifa):
    """tarifa.json, el modelo Tarifa y el bloque JSON de CONTRATO.propuesto.md coinciden."""
    datos = json.loads(t.RUTA_TARIFA.read_text(encoding="utf-8"))
    assert set(datos) == set(e.Tarifa.model_fields)
    texto = CONTRATO.read_text(encoding="utf-8")
    bloque = re.search(r"## 5\. Tarifa.*?```json\n(.*?)```", texto, re.S).group(1)
    assert json.loads(bloque) == datos
    assert tarifa.valor_hora_usd == 0.50 and tarifa.bloque_minimo_min == 30


@pytest.mark.parametrize(
    "reales,cobrados",
    [(0, 10), (3, 10), (10, 10), (10.01, 15), (12, 15), (15, 15), (47, 50), (120, 120)],
)
def test_minutos_cobrados(tarifa, reales, cobrados):
    assert t.minutos_cobrados(reales, tarifa) == cobrados


def test_montos(tarifa):
    assert t.monto_retencion(tarifa) == 0.25
    assert t.monto_debito(47, tarifa) == 0.42  # 50 min → 0.4166… → 0.42
    assert t.costo_usd(12.5, tarifa) == 0.10
    assert t.tarjeta_sert_usd(47, tarifa) == 0.50
    assert t.tarjeta_sert_usd(61, tarifa) == 0.75
    assert t.tarjeta_sert_usd(0, tarifa) == 0.25
    assert t.a_centavos(0.425) == 43


def test_recibo_de_ejemplo_es_coherente(tarifa):
    """El recibo y el cierre de ejemplo salen de las funciones de tarifa.py."""
    r = e.MensajeEspejo.model_validate(_leer("espejo_recibo_ws.json")).recibo
    assert r.minutos_cobrados == t.minutos_cobrados(r.minutos_reales, tarifa)
    assert r.cobrado_usd == t.monto_debito(r.minutos_reales, tarifa)
    assert r.tarjeta_sert_usd == t.tarjeta_sert_usd(r.minutos_reales, tarifa)
    assert round(r.tarjeta_sert_usd - r.cobrado_usd, 2) == r.ahorro_usd
    c = e.SesionCerrada.model_validate(_leer("sesion_cerrada.json"))
    assert c.debitado == t.monto_debito(c.minutos_reales, tarifa)


def test_billetera_de_ejemplo_cuadra():
    """saldo = recargas − débitos; retenido = retenciones − liberaciones; disponible = saldo − retenido."""
    b = e.Billetera.model_validate(_leer("billetera.json"))
    suma = {tipo: 0 for tipo in e.TipoMovimiento}
    for m in b.movimientos:
        suma[m.tipo] += t.a_centavos(m.monto)
    saldo = suma[e.TipoMovimiento.recarga] - suma[e.TipoMovimiento.debito]
    retenido = suma[e.TipoMovimiento.retencion] - suma[e.TipoMovimiento.liberacion]
    assert t.a_centavos(b.saldo) == saldo
    assert t.a_centavos(b.retenido) == retenido
    assert t.a_centavos(b.disponible) == saldo - retenido
    assert b.bloqueada == (saldo < 0)


def test_tarifa_incoherente_falla(tmp_path):
    datos = json.loads(t.RUTA_TARIFA.read_text(encoding="utf-8"))
    for cambio in ({"cobro_minimo_min": 45}, {"aviso_tiempo_min": 200}, {"valor_hora_usd": -1},
                   {"bloque_minimo_min": 33}):
        malo = tmp_path / "tarifa.json"
        malo.write_text(json.dumps({**datos, **cambio}), encoding="utf-8")
        with pytest.raises(ValueError):
            t.cargar_tarifa(malo)


# ---------------------------------------------------------------------------
# 4. Paridad Python ↔ TypeScript
# ---------------------------------------------------------------------------

TS = (COMUN / "esquemas.ts").read_text(encoding="utf-8")


def _interfaces_ts(texto: str) -> dict:
    """Parser simple: `export interface X [extends Y] { campo?: tipo; ... }` → {X: {campos}}."""
    crudas = {}
    patron = re.compile(r"export interface (\w+)(?:\s+extends\s+([\w\s,]+?))?\s*\{(.*?)\n\}", re.S)
    for nombre, padres, cuerpo in patron.findall(texto):
        campos = set(re.findall(r"^\s*(\w+)\??\s*:", cuerpo, re.M))
        crudas[nombre] = (campos, [p.strip() for p in padres.split(",") if p.strip()])

    def resolver(nombre):
        campos, padres = crudas[nombre]
        todos = set(campos)
        for p in padres:
            todos |= resolver(p)
        return todos

    return {n: resolver(n) for n in crudas}


def _uniones_ts(texto: str) -> dict:
    """`export type X = 'a' | 'b';` → {X: {'a', 'b'}} (solo uniones de literales de texto)."""
    salida = {}
    for nombre, cuerpo in re.findall(r"export type (\w+)\s*=\s*([^;]+);", texto):
        valores = re.findall(r"'([^']*)'", cuerpo)
        if valores and re.fullmatch(r"[\s|'\w]+", cuerpo):
            salida[nombre] = set(valores)
    return salida


MODELOS_PY = {
    n: c for n, c in vars(e).items()
    if isinstance(c, type) and issubclass(c, BaseModel) and c is not e.Modelo and c.__module__ == e.__name__
}
ENUMS_PY = {
    n: c for n, c in vars(e).items()
    if isinstance(c, type) and issubclass(c, Enum) and c.__module__ == e.__name__
}
INTERFACES_TS = _interfaces_ts(TS)
UNIONES_TS = _uniones_ts(TS)


def test_parser_ts_funciona():
    assert INTERFACES_TS["PuntoGPS"] == {"t", "lat", "lon", "precision_m"}
    assert "modo" in INTERFACES_TS["VehiculoSim"] and "con_app" in INTERFACES_TS["VehiculoSim"]
    assert UNIONES_TS["Modo"] == {"a_pie", "quieto", "vehiculo"}


def test_mismos_modelos_en_ts_y_py():
    assert set(MODELOS_PY) == set(INTERFACES_TS)


@pytest.mark.parametrize("nombre", sorted(MODELOS_PY))
def test_mismos_campos(nombre):
    assert set(MODELOS_PY[nombre].model_fields) == INTERFACES_TS[nombre], nombre


def test_mismos_enums_en_ts_y_py():
    assert set(ENUMS_PY) == set(UNIONES_TS)


@pytest.mark.parametrize("nombre", sorted(ENUMS_PY))
def test_mismos_valores_de_enum(nombre):
    assert {m.value for m in ENUMS_PY[nombre]} == UNIONES_TS[nombre]


def test_campos_opcionales_coinciden():
    """Un campo con valor por defecto en Python es `campo?:` en TS, y al revés."""
    patron = re.compile(r"export interface (\w+)(?:\s+extends\s+[\w\s,]+?)?\s*\{(.*?)\n\}", re.S)
    opcionales_ts = {}
    for nombre, cuerpo in patron.findall(TS):
        opcionales_ts[nombre] = set(re.findall(r"^\s*(\w+)\?\s*:", cuerpo, re.M))
    for nombre, modelo in MODELOS_PY.items():
        propios = set(modelo.model_fields) - {
            c for base in modelo.__mro__[1:] if hasattr(base, "model_fields") for c in base.model_fields
        }
        opc_py = {c for c in propios if not modelo.model_fields[c].is_required()}
        # `tipo` y `aceptado` tienen default en Python (literales) pero son obligatorios en TS.
        opc_py -= {"tipo", "aceptado"}
        assert opc_py == opcionales_ts[nombre], nombre


def test_constantes_compartidas():
    assert f"CONTRATO_VERSION = '{e.CONTRATO_VERSION}'" in TS
    columnas = re.search(r"COLUMNAS_TRAZA = \[(.*?)\]", TS, re.S).group(1)
    assert re.findall(r"'(\w+)'", columnas) == e.COLUMNAS_TRAZA
    assert set(e.HTTP_POR_CODIGO) == set(e.CodigoError)


def test_contrato_documenta_todos_los_codigos():
    texto = CONTRATO.read_text(encoding="utf-8")
    for codigo in e.CodigoError:
        assert f"`{codigo.value}` | {e.HTTP_POR_CODIGO[codigo]} |" in texto, codigo
    assert "## Cambios respecto a v0" in texto
    assert "ver v0" not in texto.lower()
