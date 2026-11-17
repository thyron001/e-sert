"""Esquemas del contrato v1 de e-sert (Pydantic v2).

Fuente de verdad en código de `CONTRATO.propuesto.md` (luego `docs/CONTRATO.md`). Lo importan
el controlador TraCI, el backend y la IA:

    from comun.esquemas import PuntoGPS, ResultadoModo, EventoUbicacion, MensajeWS

Se sincroniza a mano con `esquemas.ts`: mismos nombres de clase y de campo. El test
`tests/test_esquemas.py` falla si se desalinean.

Compatible con Python 3.10 (corre también en el contenedor `van3twin`).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter

CONTRATO_VERSION = "1"
"""Valor del header `X-Contrato-Version`."""

# ---------------------------------------------------------------------------
# Identificadores y tipos básicos (§1)
# ---------------------------------------------------------------------------

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

PuestoId = Annotated[str, Field(pattern=r"^pa_.+_\d+$", description="pa_<edgeId>_<n>")]
VehiculoId = Annotated[str, Field(pattern=r"^sim_.+$", description="sim_<vehId>")]
PeatonId = Annotated[str, Field(pattern=r"^ped_.+$", description="ped_<vehId>")]
UsuarioId = Annotated[
    str, Field(pattern=rf"^(sim_.+|app_{_UUID})$", description="sim_<vehId> o app_<uuid4>")
]
SesionId = Annotated[str, Field(pattern=rf"^ses_{_UUID}$", description="ses_<uuid4>")]
MovimientoId = Annotated[str, Field(pattern=rf"^mov_{_UUID}$", description="mov_<uuid4>")]
Placa = Annotated[str, Field(pattern=r"^[A-Z]{3}-?\d{3,4}$", description="ABC-1234 o SIM-0042")]

FechaISO = AwareDatetime
"""Hora ISO 8601 con zona obligatoria (se emite en UTC con `Z`)."""

Latitud = Annotated[float, Field(ge=-90, le=90)]
Longitud = Annotated[float, Field(ge=-180, le=180)]
TSim = Annotated[float, Field(ge=0, description="Segundos de simulación")]
Metros = Annotated[float, Field(ge=0)]
Usd = Annotated[float, Field(description="Dólares, 2 decimales como máximo")]
UsdPositivo = Annotated[float, Field(ge=0, description="Dólares, 2 decimales como máximo")]
Coordenada = Annotated[List[float], Field(min_length=2, max_length=2, description="[lat, lon]")]


class Modelo(BaseModel):
    """Base de todos los modelos: rechaza campos desconocidos y emite horas en UTC con `Z`."""

    model_config = ConfigDict(extra="forbid")

    def a_json(self) -> Dict[str, Any]:
        """Serializa a un dict JSON (horas como texto ISO)."""
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Enums (§2, §3, §5, §7)
# ---------------------------------------------------------------------------


class Modo(str, Enum):
    """Modo de movimiento que decide la IA."""

    a_pie = "a_pie"
    quieto = "quieto"
    vehiculo = "vehiculo"


class FuenteModo(str, Enum):
    """Origen de la clasificación: Random Forest o la regla de umbral (línea base)."""

    rf = "rf"
    umbral = "umbral"


class EstadoSesion(str, Enum):
    """Estados de la máquina de estados (§3). BUSCANDO y GUIADO son del vehículo, sin sesión."""

    BUSCANDO = "BUSCANDO"
    GUIADO = "GUIADO"
    ESTACIONADO = "ESTACIONADO"
    A_PIE = "A_PIE"
    REGRESANDO = "REGRESANDO"
    SALIENDO = "SALIENDO"
    CERRADA = "CERRADA"


TRANSICIONES_LEGALES = {
    (EstadoSesion.ESTACIONADO, EstadoSesion.A_PIE),
    (EstadoSesion.ESTACIONADO, EstadoSesion.SALIENDO),
    (EstadoSesion.A_PIE, EstadoSesion.REGRESANDO),
    (EstadoSesion.REGRESANDO, EstadoSesion.SALIENDO),
    (EstadoSesion.REGRESANDO, EstadoSesion.A_PIE),
}
"""Transiciones aceptadas por `POST /sesiones/{id}/transicion`. CERRADA solo por `/cerrar`."""


class OrigenUbicacion(str, Enum):
    """Quién produjo la ubicación."""

    sumo = "sumo"
    app = "app"


class MotivoCierre(str, Enum):
    """Por qué se cierra la sesión."""

    deteccion = "deteccion"
    manual = "manual"
    # S3-2 (propuesto en CONTRATO.propuesto.md): sin datos GPS, la sesión llegó a `tiempo_maximo_min`.
    timeout_sin_senal = "timeout_sin_senal"


class TipoMovimiento(str, Enum):
    """Tipos de asiento del libro de la billetera."""

    recarga = "recarga"
    retencion = "retencion"
    debito = "debito"
    liberacion = "liberacion"


class Aviso(str, Enum):
    """Avisos que el backend envía al espejo (§5)."""

    saldo_bajo = "saldo_bajo"
    saldo_agotado = "saldo_agotado"
    tiempo_maximo_cerca = "tiempo_maximo_cerca"
    tiempo_maximo_superado = "tiempo_maximo_superado"
    sesiones_bloqueadas = "sesiones_bloqueadas"


class MotivoFinEspejo(str, Enum):
    """Por qué termina el seguimiento de un vehículo en el espejo."""

    salio_simulacion = "salio_simulacion"
    fin_simulacion = "fin_simulacion"
    no_existe = "no_existe"


class CodigoError(str, Enum):
    """Códigos de error del backend (§4.2)."""

    VALIDACION = "VALIDACION"
    CONTRATO_INCOMPATIBLE = "CONTRATO_INCOMPATIBLE"
    TOKEN_SIM_INVALIDO = "TOKEN_SIM_INVALIDO"
    SALDO_INSUFICIENTE = "SALDO_INSUFICIENTE"
    SESIONES_BLOQUEADAS = "SESIONES_BLOQUEADAS"
    PUESTO_NO_EXISTE = "PUESTO_NO_EXISTE"
    SESION_NO_EXISTE = "SESION_NO_EXISTE"
    VEHICULO_NO_EXISTE = "VEHICULO_NO_EXISTE"
    SIN_PUESTOS_LIBRES = "SIN_PUESTOS_LIBRES"
    PUESTO_LLENO = "PUESTO_LLENO"
    SESION_ACTIVA = "SESION_ACTIVA"
    SESION_YA_CERRADA = "SESION_YA_CERRADA"
    TRANSICION_INVALIDA = "TRANSICION_INVALIDA"
    RECARGA_MINIMA = "RECARGA_MINIMA"
    ERROR_INTERNO = "ERROR_INTERNO"


HTTP_POR_CODIGO = {
    CodigoError.VALIDACION: 422,
    CodigoError.CONTRATO_INCOMPATIBLE: 400,
    CodigoError.TOKEN_SIM_INVALIDO: 401,
    CodigoError.SALDO_INSUFICIENTE: 402,
    CodigoError.SESIONES_BLOQUEADAS: 403,
    CodigoError.PUESTO_NO_EXISTE: 404,
    CodigoError.SESION_NO_EXISTE: 404,
    CodigoError.VEHICULO_NO_EXISTE: 404,
    CodigoError.SIN_PUESTOS_LIBRES: 404,
    CodigoError.PUESTO_LLENO: 409,
    CodigoError.SESION_ACTIVA: 409,
    CodigoError.SESION_YA_CERRADA: 409,
    CodigoError.TRANSICION_INVALIDA: 409,
    CodigoError.RECARGA_MINIMA: 422,
    CodigoError.ERROR_INTERNO: 500,
}
"""Estado HTTP de cada código de error."""


# ---------------------------------------------------------------------------
# IA (§2)
# ---------------------------------------------------------------------------


class PuntoGPS(Modelo):
    """Un punto de la ventana de GPS que recibe `clasificar()`."""

    t: TSim
    lat: Latitud
    lon: Longitud
    precision_m: Optional[Metros] = None


class ResultadoModo(Modelo):
    """Salida de `clasificar()`: el modo, su confianza (0..1) y quién lo decidió."""

    modo: Modo
    confianza: float = Field(ge=0, le=1)
    fuente: FuenteModo


# ---------------------------------------------------------------------------
# API REST (§4)
# ---------------------------------------------------------------------------


class DetalleError(Modelo):
    """Contenido de un error: código estable y mensaje legible en español."""

    codigo: CodigoError
    mensaje: str
    detalle: Optional[Dict[str, Any]] = None


class CuerpoError(Modelo):
    """Cuerpo de toda respuesta 4xx/5xx: `{"error": {...}}`."""

    error: DetalleError


class Aceptado(Modelo):
    """Respuesta de las rutas que devuelven 202."""

    aceptado: Literal[True] = True


class Salud(Modelo):
    """Respuesta de `GET /salud`."""

    ok: bool
    contrato: int
    t_sim: Optional[TSim] = None
    ts: Optional[FechaISO] = None  # v1.2: hora UTC del servidor con ms (la app estima su desfase)


class Tarifa(Modelo):
    """Parámetros de cobro (`tarifa.json`, §5)."""

    valor_hora_usd: float = Field(gt=0)
    bloque_minimo_min: int = Field(gt=0)
    fraccion_min: int = Field(gt=0)
    cobro_minimo_min: int = Field(ge=0)
    saldo_negativo_max_usd: float = Field(ge=0)
    aviso_saldo_min: int = Field(ge=0)
    tiempo_maximo_min: int = Field(gt=0)
    aviso_tiempo_min: int = Field(ge=0)
    recarga_minima_usd: float = Field(gt=0)
    tarjeta_bloque_min: int = Field(gt=0)


class Puesto(Modelo):
    """Un puesto (`parkingArea`) con su capacidad y la ocupación que estima el sistema."""

    puesto_id: PuestoId
    lat: Latitud
    lon: Longitud
    calle: str
    capacidad: int = Field(ge=1)
    ocupados: int = Field(ge=0)


class ConsultaGuia(Modelo):
    """Parámetros de `GET /guia`: dónde está el auto y a dónde va."""

    lat: Latitud
    lon: Longitud
    destino_lat: Latitud
    destino_lon: Longitud


class Guia(Modelo):
    """Puesto libre asignado por `GET /guia`."""

    puesto_id: PuestoId
    lat: Latitud
    lon: Longitud
    distancia_m: Metros


class EventoUbicacion(Modelo):
    """`POST /eventos/ubicacion`: una posición GPS (con ruido si viene del emulador)."""

    usuario_id: UsuarioId
    origen: OrigenUbicacion
    ts: FechaISO
    t_sim: Optional[TSim] = None
    lat: Latitud
    lon: Longitud
    velocidad_mps: Optional[float] = Field(default=None, ge=0)
    precision_m: Optional[Metros] = None


class EventoModo(Modelo):
    """`POST /eventos/modo`: resultado de la IA para un usuario."""

    usuario_id: UsuarioId
    ts: FechaISO
    t_sim: Optional[TSim] = None
    modo: Modo
    confianza: float = Field(ge=0, le=1)
    fuente: FuenteModo


class NuevaSesion(Modelo):
    """`POST /sesiones`: llegada confirmada (placa + puesto). Crea la sesión en ESTACIONADO."""

    usuario_id: UsuarioId
    placa: Placa
    puesto_id: PuestoId
    ts: Optional[FechaISO] = None
    t_sim: Optional[TSim] = None


class SesionCreada(Modelo):
    """Respuesta de `POST /sesiones`."""

    sesion_id: SesionId
    estado: Literal[EstadoSesion.ESTACIONADO]
    retenido: UsdPositivo


class TransicionSesion(Modelo):
    """`POST /sesiones/{id}/transicion`: el controlador informa un cambio de estado."""

    estado: EstadoSesion
    ts: FechaISO
    t_sim: Optional[TSim] = None


class EstadoActualSesion(Modelo):
    """Respuesta de `POST /sesiones/{id}/transicion`."""

    sesion_id: SesionId
    estado: EstadoSesion


class CierreSesion(Modelo):
    """`POST /sesiones/{id}/cerrar`: salida detectada (o cierre manual)."""

    ts: FechaISO
    t_sim: Optional[TSim] = None
    motivo: MotivoCierre


class SesionCerrada(Modelo):
    """Respuesta de `POST /sesiones/{id}/cerrar`."""

    sesion_id: SesionId
    minutos_reales: float = Field(ge=0)
    minutos_cobrados: int = Field(ge=0)
    debitado: UsdPositivo
    saldo: Usd


class Sesion(Modelo):
    """Sesión completa (`GET /sesiones/{id}`). Los campos de cierre son null hasta cerrar."""

    sesion_id: SesionId
    usuario_id: UsuarioId
    placa: Placa
    puesto_id: PuestoId
    estado: EstadoSesion
    inicio: FechaISO
    fin: Optional[FechaISO] = None
    t_sim_inicio: Optional[TSim] = None
    t_sim_fin: Optional[TSim] = None
    retenido: UsdPositivo
    minutos_reales: Optional[float] = Field(default=None, ge=0)
    minutos_cobrados: Optional[int] = Field(default=None, ge=0)
    debitado: Optional[UsdPositivo] = None


class Movimiento(Modelo):
    """Un asiento del libro de la billetera. `monto` siempre positivo."""

    movimiento_id: MovimientoId
    tipo: TipoMovimiento
    monto: UsdPositivo
    ts: FechaISO
    sesion_id: Optional[SesionId] = None
    referencia_payphone: Optional[str] = None


class Billetera(Modelo):
    """`GET /billetera/{usuario_id}`: saldos derivados del libro y sus movimientos."""

    saldo: Usd
    retenido: UsdPositivo
    disponible: Usd
    bloqueada: bool
    movimientos: List[Movimiento]


class Recarga(Modelo):
    """`POST /billetera/{usuario_id}/recarga`. Los autos simulados no envían referencia."""

    monto: float = Field(gt=0)
    referencia_payphone: Optional[str] = None


class RecargaHecha(Modelo):
    """Respuesta de la recarga."""

    movimiento_id: MovimientoId
    saldo: Usd


class CandidatoEspejo(Modelo):
    """Un vehículo con app que el teléfono puede elegir seguir."""

    id: VehiculoId
    destino_nombre: str
    estado: Optional[EstadoSesion] = None
    t_sim: TSim


# ---------------------------------------------------------------------------
# Piezas compartidas por /sim/paso y los mensajes WS (§4.4, §6, §7)
# ---------------------------------------------------------------------------


class Destino(Modelo):
    """Lugar al que va el conductor (de `destinos.csv` de Tyrone)."""

    nombre: str
    lat: Latitud
    lon: Longitud


class VehiculoSnapshot(Modelo):
    """Vehículo tal como lo ve el visor."""

    id: VehiculoId
    lat: Latitud
    lon: Longitud
    estado: Optional[EstadoSesion] = None
    con_app: bool


class VehiculoSim(VehiculoSnapshot):
    """Vehículo en `/sim/paso`: lo del snapshot más datos para el espejo (solo con app)."""

    modo: Optional[Modo] = None
    destino: Optional[Destino] = None
    puesto_id: Optional[PuestoId] = None
    ruta: List[Coordenada] = Field(default_factory=list)


class Peaton(Modelo):
    """Peatón simulado (el conductor que se bajó)."""

    id: PeatonId
    lat: Latitud
    lon: Longitud


class OcupacionPuesto(Modelo):
    """Ocupación de un puesto (estimada en `snapshot`, real en `verdad`)."""

    puesto_id: PuestoId
    ocupados: int = Field(ge=0)
    capacidad: int = Field(ge=1)


class DatosVerdad(Modelo):
    """Ocupación real de SUMO; solo existe en simulación."""

    puestos: List[OcupacionPuesto]
    estacionados: List[VehiculoId] = Field(default_factory=list)
    falsas_liberaciones: List[SesionId] = Field(default_factory=list)


class PasoSimulacion(Modelo):
    """`POST /sim/paso`: el controlador TraCI envía el estado del mundo (≤ 1 por s simulado).

    v1.2: `espejo` es un bloque **interno** (candidatos y detalle de los vehículos seguidos) que el
    backend guarda en `RegistroEspejo` y nunca difunde por `/ws/estado`.
    """

    t_sim: TSim
    ts: FechaISO
    vehiculos: List[VehiculoSim]
    peatones: List[Peaton]
    verdad: DatosVerdad
    espejo: Optional["BloqueEspejo"] = None
    # v1.4: mapa **estimado** del controlador (sesiones de los autos simulados con app, que viven en
    # su núcleo en memoria). Solo puestos con ocupados > 0. El backend lo suma a su propio mapa
    # (sesiones creadas por HTTP) para `snapshot.puestos`; sin él, el visor marcaba 0/610.
    puestos: Optional[List[OcupacionPuesto]] = None


class RespuestaSnapshot(Modelo):
    """Respuesta 202 de `POST /interno/snapshot` y `/sim/paso` (v1.2): qué vehículos sigue algún
    teléfono; el controlador calcula `espejo.detalle` solo para esos."""

    aceptado: Literal[True] = True
    espejos: List[VehiculoId] = Field(default_factory=list)


class PuestoEspejo(Modelo):
    """Puesto asignado al vehículo seguido, con la distancia que le falta."""

    puesto_id: PuestoId
    lat: Latitud
    lon: Longitud
    distancia_m: Metros


class SesionEspejo(Modelo):
    """Sesión en curso vista desde el espejo (costo en vivo)."""

    sesion_id: SesionId
    minutos: float = Field(ge=0)
    costo_usd: UsdPositivo
    retenido_usd: UsdPositivo


class BilleteraEspejo(Modelo):
    """Resumen de la billetera para el espejo."""

    saldo: Usd
    disponible: Usd


class Recibo(Modelo):
    """Recibo al cerrar la sesión, comparado con la tarjeta SERT de papel."""

    minutos_reales: float = Field(ge=0)
    minutos_cobrados: int = Field(ge=0)
    cobrado_usd: UsdPositivo
    tarjeta_sert_usd: UsdPositivo
    ahorro_usd: Usd


class ReciboEspejo(Recibo):
    """Recibo dentro del bloque interno `espejo`: lleva el `sesion_id` para que el backend lo
    envíe una sola vez por sesión. Al teléfono le llega como `Recibo` (sin `sesion_id`)."""

    sesion_id: SesionId


class DetalleEspejo(Modelo):
    """Lo que el controlador sabe de un vehículo seguido (bloque interno `espejo.detalle`)."""

    t_sim: TSim
    estado: Optional[EstadoSesion] = None
    lat: Latitud
    lon: Longitud
    modo: Optional[Modo] = None
    confianza: Optional[float] = Field(None, ge=0, le=1, description="Del último ResultadoModo (no se difunde)")
    destino: Optional[Destino] = None
    puesto: Optional[PuestoEspejo] = None
    ruta: List[Coordenada] = Field(default_factory=list)
    sesion: Optional[SesionEspejo] = None
    billetera: Optional[BilleteraEspejo] = None
    avisos: List[Aviso] = Field(default_factory=list)
    recibo: Optional[ReciboEspejo] = None


class BloqueEspejo(Modelo):
    """Bloque interno `espejo` de `POST /interno/snapshot` (v1.2). Nunca sale por `/ws/estado`."""

    candidatos: List[CandidatoEspejo] = Field(default_factory=list)
    detalle: Dict[str, DetalleEspejo] = Field(default_factory=dict, description="veh_id → detalle")
    fin: bool = Field(False, description="La corrida terminó: los espejos reciben `fin_simulacion`")


# ---------------------------------------------------------------------------
# Mensajes WebSocket (§6, §7): unión discriminada por `tipo`
# ---------------------------------------------------------------------------


class MensajeSnapshot(Modelo):
    """`{"tipo": "snapshot"}`: estado del mundo para el visor (≤ 1 por s simulado)."""

    tipo: Literal["snapshot"] = "snapshot"
    t_sim: TSim
    ts: FechaISO
    vehiculos: List[VehiculoSnapshot]
    peatones: List[Peaton]
    puestos: List[OcupacionPuesto]
    espejos: List[VehiculoId] = Field(default_factory=list)


class MensajeKpi(Modelo):
    """`{"tipo": "kpi"}`: KPIs en vivo, `nombre → valor`."""

    tipo: Literal["kpi"] = "kpi"
    t_sim: TSim
    ts: FechaISO
    valores: Dict[str, float]


class MensajeVerdad(Modelo):
    """`{"tipo": "verdad"}`: ocupación real de SUMO. Solo simulación y solo `?rol=visor`."""

    tipo: Literal["verdad"] = "verdad"
    t_sim: TSim
    ts: FechaISO
    puestos: List[OcupacionPuesto]
    estacionados: List[VehiculoId] = Field(default_factory=list)
    falsas_liberaciones: List[SesionId] = Field(default_factory=list)


class MensajeEspejo(Modelo):
    """`{"tipo": "espejo"}`: lo que vería el conductor seguido, a 1 Hz."""

    tipo: Literal["espejo"] = "espejo"
    veh_id: VehiculoId
    t_sim: TSim
    ts: FechaISO
    estado: Optional[EstadoSesion] = None
    lat: Latitud
    lon: Longitud
    modo: Optional[Modo] = None
    destino: Optional[Destino] = None
    puesto: Optional[PuestoEspejo] = None
    ruta: List[Coordenada] = Field(default_factory=list)
    sesion: Optional[SesionEspejo] = None
    billetera: Optional[BilleteraEspejo] = None
    avisos: List[Aviso] = Field(default_factory=list)
    recibo: Optional[Recibo] = None


class MensajeEspejoFin(Modelo):
    """`{"tipo": "espejo_fin"}`: el vehículo seguido ya no está; el backend cierra el socket."""

    tipo: Literal["espejo_fin"] = "espejo_fin"
    veh_id: VehiculoId
    t_sim: Optional[TSim] = None
    ts: FechaISO
    motivo: MotivoFinEspejo


MensajeWS = Annotated[
    Union[MensajeSnapshot, MensajeKpi, MensajeVerdad, MensajeEspejo, MensajeEspejoFin],
    Field(discriminator="tipo"),
]
"""Cualquier mensaje de `/ws/estado` o `/ws/espejo/{veh_id}`."""

ADAPTADOR_WS: TypeAdapter = TypeAdapter(MensajeWS)


def leer_mensaje_ws(datos: Union[str, bytes, Dict[str, Any]]) -> Union[
    MensajeSnapshot, MensajeKpi, MensajeVerdad, MensajeEspejo, MensajeEspejoFin
]:
    """Valida un mensaje WS (texto JSON o dict) y devuelve el modelo según su `tipo`."""
    if isinstance(datos, (str, bytes)):
        return ADAPTADOR_WS.validate_json(datos)
    return ADAPTADOR_WS.validate_python(datos)


# ---------------------------------------------------------------------------
# Trazas GPS (§8)
# ---------------------------------------------------------------------------

COLUMNAS_TRAZA = ["usuario_id", "t", "lat", "lon", "precision_m", "velocidad_mps", "modo_real"]
"""Las 7 primeras columnas del CSV de trazas, en orden. Puede haber columnas extra después."""


class FilaTraza(Modelo):
    """Una fila del CSV de trazas. Las celdas vacías llegan como None."""

    model_config = ConfigDict(extra="ignore")

    usuario_id: str = Field(min_length=1)
    t: float
    lat: Latitud
    lon: Longitud
    precision_m: Optional[Metros] = None
    velocidad_mps: Optional[float] = Field(default=None, ge=0)
    modo_real: Optional[Modo] = None

    @classmethod
    def desde_csv(cls, fila: Dict[str, str]) -> "FilaTraza":
        """Construye la fila desde `csv.DictReader`, convirtiendo celdas vacías en None."""
        return cls.model_validate({k: (v if v != "" else None) for k, v in fila.items()})


__all__ = [n for n in dir() if not n.startswith("_") and n not in {"annotations", "datetime"}]


PasoSimulacion.model_rebuild()
