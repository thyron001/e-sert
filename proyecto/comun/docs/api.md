# Referencia de la API de e-sert (generada)

Generado por `comun/docs/verificar_contrato_api.py` desde `app.openapi()` (contrato v1). No editar a mano: vuelve a correr el script.

- Prefijo: `/api/v1`. Todas las respuestas llevan `X-Contrato-Version: 1`; si la app manda otra versión, `400 CONTRATO_INCOMPATIBLE`.
- 🔒 = exige `X-Sim-Token: <ESERT_TOKEN_SIM>` (o `Authorization: Bearer …`); si falta, `401 TOKEN_SIM_INVALIDO`.
- Errores: `{"error": {"codigo", "mensaje", "detalle?"}}` (contrato §4.2).
- Esquema completo: [`openapi.json`](openapi.json). WebSockets: al final.

**Verificación contra `docs/CONTRATO.md` §4.3:** sin diferencias.

| Método | Ruta | Éxito | Cuerpo | Respuesta |
|---|---|---|---|---|
| GET | `/salud` | 200 | — | Salud |
| GET | `/tarifa` | 200 | — | Tarifa |
| GET | `/puestos` | 200 | — | Puesto |
| GET | `/guia` | 200 | — | Guia |
| POST | 🔒 `/sim/paso` | 202 | PasoSimulacion | RespuestaSnapshot |
| POST | 🔒 `/interno/snapshot` | 202 | PasoSimulacion | RespuestaSnapshot |
| POST | 🔒 `/sim/kpi` | 202 | MensajeKpi | Aceptado |
| POST | `/eventos/ubicacion` | 202 | EventoUbicacion | Aceptado |
| POST | `/eventos/modo` | 202 | EventoModo | Aceptado |
| POST | `/sesiones` | 201 | NuevaSesion | SesionCreada |
| POST | 🔒 `/sesiones/{id}/transicion` | 200 | TransicionSesion | EstadoActualSesion |
| POST | `/sesiones/{id}/cerrar` | 200 | CierreSesion | SesionCerrada |
| GET | `/sesiones/{id}` | 200 | — | Sesion |
| GET | `/billetera/{usuario_id}` | 200 | — | Billetera |
| POST | `/billetera/{usuario_id}/recarga` | 201 | Recarga | RecargaHecha |
| GET | `/espejo/candidatos` | 200 | — | CandidatoEspejo |
| POST | `/pagos/preparar` | 201 | PedidoPago | PagoPreparado |
| GET | `/pagos/{client_transaction_id}` | 200 | — | Intencion |
| POST | `/asistente/interpretar` | 200 | PedidoInterpretar | RespuestaInterpretar |

## `GET /api/v1/salud`

**Estado del backend.** `ok`, versión del contrato y `t_sim` del último paso recibido (null sin simulación).

Respuesta `200`: `Salud`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `ok` | bool | sí |
| `contrato` | entero | sí |
| `t_sim` | número \| null | no |
| `ts` | texto (date-time) \| null | no |

Ejemplo (`comun/ejemplos/salud.json`):

```json
{
  "ok": true,
  "contrato": 1,
  "t_sim": 1234.0,
  "ts": "2026-11-14T15:00:00.123Z"
}
```

## `GET /api/v1/tarifa`

**Tarifa vigente (tarifa.json).** Parámetros de cobro de `comun/tarifa.json` (contrato §5).

Respuesta `200`: `Tarifa`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `valor_hora_usd` | número | sí |
| `bloque_minimo_min` | entero | sí |
| `fraccion_min` | entero | sí |
| `cobro_minimo_min` | entero | sí |
| `saldo_negativo_max_usd` | número | sí |
| `aviso_saldo_min` | entero | sí |
| `tiempo_maximo_min` | entero | sí |
| `aviso_tiempo_min` | entero | sí |
| `recarga_minima_usd` | número | sí |
| `tarjeta_bloque_min` | entero | sí |

Ejemplo (`comun/tarifa.json`):

```json
{
  "valor_hora_usd": 0.5,
  "bloque_minimo_min": 30,
  "fraccion_min": 5,
  "cobro_minimo_min": 10,
  "saldo_negativo_max_usd": 0.5,
  "aviso_saldo_min": 10,
  "tiempo_maximo_min": 120,
  "aviso_tiempo_min": 10,
  "recarga_minima_usd": 5.0,
  "tarjeta_bloque_min": 30
}
```

## `GET /api/v1/puestos`

**Puestos y ocupación estimada.** Cada `parkingArea` con su capacidad y las plazas ocupadas según las sesiones abiertas.

Respuesta `200`: lista de `Puesto`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `puesto_id` | texto | sí |
| `lat` | número | sí |
| `lon` | número | sí |
| `calle` | texto | sí |
| `capacidad` | entero | sí |
| `ocupados` | entero | sí |

Ejemplo (`comun/ejemplos/puestos.json`):

```json
[
  {
    "puesto_id": "pa_-106945247#0_0",
    "lat": -2.8898155,
    "lon": -78.9956309,
    "calle": "Del Chorro",
    "capacidad": 17,
    "ocupados": 3
  },
  {
    "puesto_id": "pa_-118367899_0",
    "lat": -2.8900644,
    "lon": -78.9980747,
    "calle": "Del Chorro",
    "capacidad": 7,
    "ocupados": 7
  }
]
```

## `GET /api/v1/guia`

**Asignar un puesto libre.** Nunca devuelve un puesto lleno. `distancia_m` es la distancia del puesto al destino.

Parámetros:

| Nombre | En | Tipo | Obligatorio |
|---|---|---|---|
| `lat` | query | número | sí |
| `lon` | query | número | sí |
| `destino_lat` | query | número | sí |
| `destino_lon` | query | número | sí |

Respuesta `200`: `Guia`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `puesto_id` | texto | sí |
| `lat` | número | sí |
| `lon` | número | sí |
| `distancia_m` | número | sí |

Ejemplo (`comun/ejemplos/guia.json`):

```json
{
  "puesto_id": "pa_-106945247#0_0",
  "lat": -2.8898155,
  "lon": -78.9956309,
  "distancia_m": 180.0
}
```

Otros códigos: `404`, `422`

## 🔒 `POST /api/v1/sim/paso`

**[sim] Paso de simulación.** Actualiza el mundo y difunde `snapshot` y `verdad` por `/ws/estado`. El bloque interno

Cuerpo: `PasoSimulacion`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `t_sim` | número | sí |
| `ts` | texto (date-time) | sí |
| `vehiculos` | [VehiculoSim] | sí |
| `peatones` | [Peaton] | sí |
| `verdad` | DatosVerdad | sí |
| `espejo` | BloqueEspejo \| null | no |
| `puestos` | [OcupacionPuesto] \| null | no |

Ejemplo (`comun/ejemplos/sim_paso.json`):

```json
{
  "t_sim": 1234.0,
  "ts": "2026-10-20T14:03:05Z",
  "vehiculos": [
    {
      "id": "sim_veh42",
      "lat": -2.8973,
      "lon": -79.0045,
      "estado": "GUIADO",
      "con_app": true,
      "modo": "vehiculo",
      "destino": {
        "nombre": "Parque Calderón",
        "lat": -2.897308,
        "lon": -79.004488
      },
      "puesto_id": "pa_-106945247#0_0",
      "ruta": [
        [
          -2.8973,
          -79.0045
        ],
        [
          -2.8975,
          -79.005
        ]
      ]
    },
    {
      "id": "sim_veh7",
  …
```

Respuesta `202`: `RespuestaSnapshot`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `aceptado` | bool | no |
| `espejos` | [texto] | no |

Otros códigos: `401`, `422`

## 🔒 `POST /api/v1/interno/snapshot`

**[sim] Paso de simulación (alias para el VPS).** Igual que `/sim/paso` (ver `comun/CONTRATO.propuesto.md`). Acepta `Authorization: Bearer`.

Cuerpo: `PasoSimulacion`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `t_sim` | número | sí |
| `ts` | texto (date-time) | sí |
| `vehiculos` | [VehiculoSim] | sí |
| `peatones` | [Peaton] | sí |
| `verdad` | DatosVerdad | sí |
| `espejo` | BloqueEspejo \| null | no |
| `puestos` | [OcupacionPuesto] \| null | no |

Ejemplo (`comun/ejemplos/sim_paso.json`):

```json
{
  "t_sim": 1234.0,
  "ts": "2026-10-20T14:03:05Z",
  "vehiculos": [
    {
      "id": "sim_veh42",
      "lat": -2.8973,
      "lon": -79.0045,
      "estado": "GUIADO",
      "con_app": true,
      "modo": "vehiculo",
      "destino": {
        "nombre": "Parque Calderón",
        "lat": -2.897308,
        "lon": -79.004488
      },
      "puesto_id": "pa_-106945247#0_0",
      "ruta": [
        [
          -2.8973,
          -79.0045
        ],
        [
          -2.8975,
          -79.005
        ]
      ]
    },
    {
      "id": "sim_veh7",
  …
```

Respuesta `202`: `RespuestaSnapshot`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `aceptado` | bool | no |
| `espejos` | [texto] | no |

Otros códigos: `401`, `422`

## 🔒 `POST /api/v1/sim/kpi`

**[sim] KPIs en vivo.** Difunde `{"tipo": "kpi"}` por `/ws/estado` (S3-1: `KPIsSistema`, cada 10 s simulados).

Cuerpo: `MensajeKpi`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `tipo` | texto | no |
| `t_sim` | número | sí |
| `ts` | texto (date-time) | sí |
| `valores` | object | sí |

Ejemplo (`comun/ejemplos/kpi_ws.json`):

```json
{
  "tipo": "kpi",
  "t_sim": 1234.0,
  "ts": "2026-10-20T14:03:05Z",
  "valores": {
    "busqueda_media_s": 210.5,
    "falsas_liberaciones_100": 1.2,
    "precision_mapa": 0.91
  }
}
```

Respuesta `202`: `Aceptado`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `aceptado` | bool | no |

Ejemplo (`comun/ejemplos/aceptado.json`):

```json
{
  "aceptado": true
}
```

Otros códigos: `401`, `422`

## `POST /api/v1/eventos/ubicacion`

**Registrar una posición GPS.** Guarda la última ubicación del usuario. La ocupación del mapa la deciden las sesiones.

Cuerpo: `EventoUbicacion`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `usuario_id` | texto | sí |
| `origen` | OrigenUbicacion | sí |
| `ts` | texto (date-time) | sí |
| `t_sim` | número \| null | no |
| `lat` | número | sí |
| `lon` | número | sí |
| `velocidad_mps` | número \| null | no |
| `precision_m` | número \| null | no |

Ejemplo (`comun/ejemplos/ubicacion.json`):

```json
{
  "usuario_id": "sim_veh42",
  "origen": "sumo",
  "ts": "2026-10-20T14:03:05Z",
  "t_sim": 1234.0,
  "lat": -2.89731,
  "lon": -79.00452,
  "velocidad_mps": 6.2,
  "precision_m": 8.0
}
```

Respuesta `202`: `Aceptado`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `aceptado` | bool | no |

Ejemplo (`comun/ejemplos/aceptado.json`):

```json
{
  "aceptado": true
}
```

Otros códigos: `422`

## `POST /api/v1/eventos/modo`

**Registrar el modo que clasificó la IA.** Guarda el último modo (`a_pie`, `quieto`, `vehiculo`) del usuario.

Cuerpo: `EventoModo`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `usuario_id` | texto | sí |
| `ts` | texto (date-time) | sí |
| `t_sim` | número \| null | no |
| `modo` | Modo | sí |
| `confianza` | número | sí |
| `fuente` | FuenteModo | sí |

Ejemplo (`comun/ejemplos/modo.json`):

```json
{
  "usuario_id": "sim_veh42",
  "ts": "2026-10-20T14:03:05Z",
  "t_sim": 1234.0,
  "modo": "vehiculo",
  "confianza": 0.93,
  "fuente": "rf"
}
```

Respuesta `202`: `Aceptado`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `aceptado` | bool | no |

Ejemplo (`comun/ejemplos/aceptado.json`):

```json
{
  "aceptado": true
}
```

Otros códigos: `422`

## `POST /api/v1/sesiones`

**Iniciar sesión (llegada confirmada).** Crea la sesión en `ESTACIONADO` y retiene el bloque mínimo.

Cuerpo: `NuevaSesion`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `usuario_id` | texto | sí |
| `placa` | texto | sí |
| `puesto_id` | texto | sí |
| `ts` | texto (date-time) \| null | no |
| `t_sim` | número \| null | no |

Ejemplo (`comun/ejemplos/sesion_crear.json`):

```json
{
  "usuario_id": "sim_veh42",
  "placa": "SIM-0042",
  "puesto_id": "pa_-106945247#0_0",
  "ts": "2026-10-20T14:03:05Z",
  "t_sim": 1234.0
}
```

Respuesta `201`: `SesionCreada`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `sesion_id` | texto | sí |
| `estado` | texto | sí |
| `retenido` | número | sí |

Ejemplo (`comun/ejemplos/sesion_creada.json`):

```json
{
  "sesion_id": "ses_91ab3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d",
  "estado": "ESTACIONADO",
  "retenido": 0.25
}
```

Otros códigos: `402`, `403`, `404`, `409`, `422`

## 🔒 `POST /api/v1/sesiones/{id}/transicion`

**[sim] Cambiar de estado (controlador TraCI).** Solo transiciones legales (§3); `CERRADA` va por `/cerrar`.

Parámetros:

| Nombre | En | Tipo | Obligatorio |
|---|---|---|---|
| `sesion_id` | path | texto | sí |

Cuerpo: `TransicionSesion`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `estado` | EstadoSesion | sí |
| `ts` | texto (date-time) | sí |
| `t_sim` | número \| null | no |

Ejemplo (`comun/ejemplos/sesion_transicion.json`):

```json
{
  "estado": "A_PIE",
  "ts": "2026-10-20T14:04:10Z",
  "t_sim": 1299.0
}
```

Respuesta `200`: `EstadoActualSesion`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `sesion_id` | texto | sí |
| `estado` | EstadoSesion | sí |

Ejemplo (`comun/ejemplos/sesion_estado.json`):

```json
{
  "sesion_id": "ses_91ab3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d",
  "estado": "A_PIE"
}
```

Otros códigos: `401`, `404`, `409`, `422`

## `POST /api/v1/sesiones/{id}/cerrar`

**Cerrar y cobrar.** Debita el tiempo real (fracciones y mínimo), libera la retención y el puesto.

Parámetros:

| Nombre | En | Tipo | Obligatorio |
|---|---|---|---|
| `sesion_id` | path | texto | sí |

Cuerpo: `CierreSesion`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `ts` | texto (date-time) | sí |
| `t_sim` | número \| null | no |
| `motivo` | MotivoCierre | sí |

Ejemplo (`comun/ejemplos/sesion_cerrar.json`):

```json
{
  "ts": "2026-10-20T14:50:05Z",
  "t_sim": 4054.0,
  "motivo": "deteccion"
}
```

Respuesta `200`: `SesionCerrada`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `sesion_id` | texto | sí |
| `minutos_reales` | número | sí |
| `minutos_cobrados` | entero | sí |
| `debitado` | número | sí |
| `saldo` | número | sí |

Ejemplo (`comun/ejemplos/sesion_cerrada.json`):

```json
{
  "sesion_id": "ses_91ab3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d",
  "minutos_reales": 47.0,
  "minutos_cobrados": 50,
  "debitado": 0.42,
  "saldo": 4.58
}
```

Otros códigos: `404`, `409`, `422`

## `GET /api/v1/sesiones/{id}`

**Consultar una sesión.** Sesión completa; los campos de cierre son null hasta cerrarla.

Parámetros:

| Nombre | En | Tipo | Obligatorio |
|---|---|---|---|
| `sesion_id` | path | texto | sí |

Respuesta `200`: `Sesion`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `sesion_id` | texto | sí |
| `usuario_id` | texto | sí |
| `placa` | texto | sí |
| `puesto_id` | texto | sí |
| `estado` | EstadoSesion | sí |
| `inicio` | texto (date-time) | sí |
| `fin` | texto (date-time) \| null | no |
| `t_sim_inicio` | número \| null | no |
| `t_sim_fin` | número \| null | no |
| `retenido` | número | sí |
| `minutos_reales` | número \| null | no |
| `minutos_cobrados` | entero \| null | no |
| `debitado` | número \| null | no |

Ejemplo (`comun/ejemplos/sesion.json`):

```json
{
  "sesion_id": "ses_91ab3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d",
  "usuario_id": "sim_veh42",
  "placa": "SIM-0042",
  "puesto_id": "pa_-106945247#0_0",
  "estado": "CERRADA",
  "inicio": "2026-10-20T14:03:05Z",
  "fin": "2026-10-20T14:50:05Z",
  "t_sim_inicio": 1234.0,
  "t_sim_fin": 4054.0,
  "retenido": 0.25,
  "minutos_reales": 47.0,
  "minutos_cobrados": 50,
  "debitado": 0.42
}
```

Otros códigos: `404`, `422`

## `GET /api/v1/billetera/{usuario_id}`

**Saldo y movimientos.** Un usuario sin movimientos tiene saldo 0 (billetera implícita, sin 404).

Parámetros:

| Nombre | En | Tipo | Obligatorio |
|---|---|---|---|
| `usuario_id` | path | texto | sí |

Respuesta `200`: `Billetera`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `saldo` | número | sí |
| `retenido` | número | sí |
| `disponible` | número | sí |
| `bloqueada` | bool | sí |
| `movimientos` | [Movimiento] | sí |

Ejemplo (`comun/ejemplos/billetera.json`):

```json
{
  "saldo": 4.58,
  "retenido": 0.0,
  "disponible": 4.58,
  "bloqueada": false,
  "movimientos": [
    {
      "movimiento_id": "mov_02cd4e5f-6a7b-4c8d-9e0f-1a2b3c4d5e6f",
      "tipo": "recarga",
      "monto": 5.0,
      "ts": "2026-10-20T14:00:00Z",
      "sesion_id": null,
      "referencia_payphone": null
    },
    {
      "movimiento_id": "mov_13de5f60-7b8c-4d9e-8f10-2b3c4d5e6f70",
      "tipo": "retencion",
      "monto": 0.25,
      "ts": "2026-10-20T14:03:05Z",
      "sesion_id": "ses_91ab3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d",
      "referencia_payphone": null
    },
    {
      "movimiento_id": "mov_24ef6071-8c9d-4eaf-9021-3c4d5e6f7081",
      "tipo": "debito",
      "monto": 0.42,
      "ts": "2026-10-20T14:50:05Z",
      "sesion_id": "ses_91ab3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d",
      "referencia_payphone": null
    },
  …
```

Otros códigos: `422`

## `POST /api/v1/billetera/{usuario_id}/recarga`

**Recargar saldo.** Asienta una recarga (los autos simulados no envían `referencia_payphone`).

Parámetros:

| Nombre | En | Tipo | Obligatorio |
|---|---|---|---|
| `usuario_id` | path | texto | sí |

Cuerpo: `Recarga`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `monto` | número | sí |
| `referencia_payphone` | texto \| null | no |

Ejemplo (`comun/ejemplos/recarga.json`):

```json
{
  "monto": 5.0,
  "referencia_payphone": "PP-TEST-000123"
}
```

Respuesta `201`: `RecargaHecha`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `movimiento_id` | texto | sí |
| `saldo` | número | sí |

Ejemplo (`comun/ejemplos/recarga_hecha.json`):

```json
{
  "movimiento_id": "mov_02cd4e5f-6a7b-4c8d-9e0f-1a2b3c4d5e6f",
  "saldo": 5.0
}
```

Otros códigos: `422`

## `GET /api/v1/espejo/candidatos`

**Autos con app que se pueden seguir.** Vehículos con app que todavía no estacionan (`BUSCANDO` o `GUIADO`).

Respuesta `200`: lista de `CandidatoEspejo`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `id` | texto | sí |
| `destino_nombre` | texto | sí |
| `estado` | EstadoSesion \| null | no |
| `t_sim` | número | sí |

Ejemplo (`comun/ejemplos/candidatos_espejo.json`):

```json
[
  {
    "id": "sim_veh42",
    "destino_nombre": "Parque Calderón",
    "estado": "BUSCANDO",
    "t_sim": 1234.0
  },
  {
    "id": "sim_veh57",
    "destino_nombre": "Mercado 10 de Agosto",
    "estado": null,
    "t_sim": 1234.0
  }
]
```

## `POST /api/v1/pagos/preparar`

**Preparar una recarga con Payphone.** 

Cuerpo: `PedidoPago`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `usuario_id` | texto | sí |
| `monto` | número | sí |
| `url_app` | texto \| null | no |

Respuesta `201`: `PagoPreparado`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `client_transaction_id` | texto | sí |
| `payment_id` | texto | sí |
| `pay_url` | texto | sí |
| `modo` | "mock" \| "pruebas" | sí |

Otros códigos: `422`

## `GET /api/v1/pagos/{client_transaction_id}`

**Estado de una recarga.** 

Parámetros:

| Nombre | En | Tipo | Obligatorio |
|---|---|---|---|
| `client_transaction_id` | path | texto | sí |

Respuesta `200`: `Intencion`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `client_transaction_id` | texto | sí |
| `usuario_id` | texto | sí |
| `monto` | número | sí |
| `estado` | "pendiente" \| "aprobado" \| "rechazado" | sí |
| `referencia_payphone` | texto \| null | no |
| `creada` | texto | sí |
| `actualizada` | texto | sí |

Otros códigos: `422`

## `POST /api/v1/asistente/interpretar`

**Destino y duración a partir de una frase.** Con LLM si hay clave; si no (o si falla), por reglas. Si falta algo, la app usa el formulario.

Cuerpo: `PedidoInterpretar`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `texto` | texto | sí |

Respuesta `200`: `RespuestaInterpretar`

| Campo | Tipo | Obligatorio |
|---|---|---|
| `destino` | DestinoSalida \| null | sí |
| `duracion_min` | entero \| null | sí |
| `fuente` | "llm" \| "reglas" | sí |
| `confianza` | número | sí |
| `avisos` | [texto] | no |

Otros códigos: `422`

## WebSockets (fuera de OpenAPI)

| Ruta | Quién se conecta | Mensajes (`tipo`) | Ejemplo |
|---|---|---|---|
| `/ws/estado?rol=visor` | visor (proyector) | `snapshot`, `kpi`, `verdad` | `snapshot_ws.json`, `kpi_ws.json`, `verdad_ws.json` |
| `/ws/estado?rol=publico` | app | `snapshot`, `kpi` (nunca `verdad`) | `snapshot_ws.json` |
| `/ws/espejo/{veh_id}` | app espejo | `espejo` (≤ 1 Hz, `recibo` una vez), `espejo_fin` | `espejo_ws.json`, `espejo_recibo_ws.json`, `espejo_fin_ws.json` |

Todos los mensajes se validan con la unión discriminada `MensajeWS` de `comun/esquemas.py` (`leer_mensaje_ws`). Como máximo un `snapshot` por segundo simulado (contrato §6).
