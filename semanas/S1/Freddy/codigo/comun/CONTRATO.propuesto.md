# Contrato de interfaces (v1)

> Estado: **v1, propuesta de Freddy (custodio) en S1 · Sesión 1, 2026-10-22.** La unificación
> del domingo la copia a `docs/CONTRATO.md`. Desde ese momento, cualquier cambio entra solo
> como `CONTRATO.propuesto.md` y se aprueba en la unificación siguiente.
>
> **Versión del contrato: `1`.** El código compartido que lo implementa vive en
> `proyecto/comun/`: `esquemas.py` (Pydantic v2), `esquemas.ts` (TypeScript),
> `tarifa.json` + `tarifa.py` y `ejemplos/` (un JSON válido por mensaje). Si este texto y
> `esquemas.py` no coinciden, se considera un error del contrato y se corrige en la siguiente
> unificación; mientras tanto **manda `esquemas.py`**, que está cubierto por tests.

Este documento es lo que permite que las cuatro piezas encajen. Si tu código produce o
consume algo de aquí, debe respetarlo al pie de la letra.

## 0. Componentes y quién habla con quién

```
SUMO 1.12 ──TraCI──▶ Controlador TraCI (Freddy) ──clasificar()──▶ IA (Pablo)
                          │  POST /sim/paso, /eventos/*, /sesiones/*, GET /guia
                          ▼
                    Backend FastAPI (Freddy) ──WS /ws/estado?rol=visor──▶ Visor (Tyrone)
                          │                  ──WS /ws/espejo/{veh_id}──▶ App espejo (Miguel)
                          ▲
                          └── App: GET /espejo/candidatos, /puestos, /tarifa, /billetera…
```

- **Todo es simulado.** El teléfono no envía su GPS: sigue a un vehículo de SUMO (§7).
- La **máquina de estados** (§3) corre en el **controlador TraCI**, que es quien tiene a mano
  las posiciones, el emulador GPS y el clasificador. El backend **guarda** el estado de cada
  sesión, **valida** que las transiciones sean legales y **cobra**.
- El controlador TraCI corre en el contenedor `van3twin`, junto a SUMO; el backend puede estar
  en la computadora o en el VPS (`docs/DESPLIEGUE.md`).

## 1. Identificadores y formatos básicos

| Entidad | Formato | Ejemplo | Regex de validación |
|---|---|---|---|
| Puesto (`parkingArea` de SUMO, con capacidad N) | `pa_<edgeId>_<n>` | `pa_-106945247#0_0` | `^pa_.+_\d+$` |
| Vehículo simulado / usuario simulado | `sim_<vehId>` | `sim_veh42` | `^sim_.+$` |
| Usuario real (app) | `app_<uuid4>` | `app_7f1c…` | `^app_<uuid>$` |
| Peatón simulado | `ped_<vehId>` | `ped_veh42` | `^ped_.+$` |
| Sesión de parqueo | `ses_<uuid4>` | `ses_91ab…` | `^ses_<uuid>$` |
| Movimiento de billetera | `mov_<uuid4>` | `mov_02cd…` | `^mov_<uuid>$` |

- `<uuid>` es un UUID en minúsculas con guiones (36 caracteres).
- Un **puesto** es una `parkingArea` completa (un tramo de calle con `capacidad` plazas), no
  una plaza individual. `ocupados` va de 0 a `capacidad`.
- Los `puesto_id` contienen `#` y `-`: **nunca van en la ruta de una URL**, solo en el cuerpo
  JSON o en *query strings* codificadas.
- Para un auto simulado, `usuario_id` y el `id` del vehículo coinciden (`sim_veh42`).
- **Horas:** ISO 8601 en UTC con zona explícita (`2026-10-20T14:03:05Z`; se aceptan
  milisegundos). Una hora sin zona es inválida. En la simulación se usa además `t_sim`
  (segundos de simulación, ≥ 0).
- **Coordenadas:** WGS84 en grados decimales; `lat ∈ [-90, 90]`, `lon ∈ [-180, 180]`. La zona
  SERT queda aproximadamente en `lat ∈ [-2.906, -2.889]`, `lon ∈ [-79.014, -78.994]`.
- **Dinero:** dólares (USD) como número con 2 decimales como máximo (lo garantiza quien
  emite el valor, redondeando con `tarifa.py`; el esquema no lo rechaza). El backend calcula
  internamente en centavos enteros y redondea al centavo (mitad hacia arriba).
- **Distancias** en metros (`_m`), **velocidades** en m/s (`_mps`), **minutos** con sufijo
  `_min` o en campos `minutos*`.

## 2. Modos de movimiento (salida de la IA)

`Modo = "a_pie" | "quieto" | "vehiculo"` · `FuenteModo = "rf" | "umbral"`

- **Ventana:** 30 s de GPS a 1 Hz (se remuestrea si hace falta), con paso de 5 s.
- **Firma de inferencia** (Python, `proyecto/ia/inferencia.py`), con los modelos de
  `comun/esquemas.py`:
  ```python
  from comun.esquemas import PuntoGPS, ResultadoModo
  def clasificar(ventana: list[PuntoGPS]) -> ResultadoModo: ...
  ```
  - `PuntoGPS = {t: float (s, ≥ 0), lat, lon, precision_m: float ≥ 0 | null}`
  - `ResultadoModo = {modo: Modo, confianza: float 0..1, fuente: FuenteModo}`
- **Línea base** (`fuente = "umbral"`): la velocidad media de la ventana mayor a 8 km/h es
  `vehiculo`; menor a 0,5 km/h es `quieto`; el resto es `a_pie`.
- El controlador TraCI llama a `clasificar` **en proceso** (importando el módulo de Pablo) y
  publica el resultado con `POST /eventos/modo` para que quede registrado y llegue al espejo.

## 3. Máquina de estados de la sesión

`EstadoSesion = "BUSCANDO" | "GUIADO" | "ESTACIONADO" | "A_PIE" | "REGRESANDO" | "SALIENDO" | "CERRADA"`

```
BUSCANDO → GUIADO → ESTACIONADO → A_PIE → REGRESANDO → SALIENDO → CERRADA
              └──────────(sin app)──────────┘          ▲
                         ESTACIONADO ───────────────────┘
```

| Transición | Disparador | Quién la comunica |
|---|---|---|
| `BUSCANDO → GUIADO` | El backend asigna un puesto (`GET /guia`). | El controlador, en `vehiculos[].estado` de `/sim/paso` |
| `GUIADO → ESTACIONADO` (o `BUSCANDO → ESTACIONADO` sin guía) | Llegada confirmada: placa + `puesto_id`. Se retiene el bloque mínimo. | `POST /sesiones` (crea la sesión ya en `ESTACIONADO`) |
| `ESTACIONADO → A_PIE` | Modo `a_pie` y distancia al puesto > 15 m. **El puesto sigue ocupado.** | `POST /sesiones/{id}/transicion` |
| `A_PIE → REGRESANDO` | Distancia al puesto < 30 m y modo `a_pie` o `quieto`. | `POST /sesiones/{id}/transicion` |
| `REGRESANDO/ESTACIONADO → SALIENDO` | Modo `vehiculo` durante 2 ventanas seguidas y distancia al puesto > 20 m. | `POST /sesiones/{id}/transicion` |
| `SALIENDO → CERRADA` | Se debita el tiempo real y se libera la retención. **El puesto queda libre.** | `POST /sesiones/{id}/cerrar` con `motivo: "deteccion"` |

- **La sesión existe desde `ESTACIONADO`.** `BUSCANDO` y `GUIADO` son estados del
  *vehículo* (aparecen en `/sim/paso`, `snapshot` y `espejo`), todavía sin `sesion_id`.
- **Cómo sabe el backend que un vehículo simulado salió del puesto:** el controlador TraCI,
  que es quien decide `SALIENDO → CERRADA`, llama a `POST /sesiones/{id}/cerrar`. El backend
  no deduce la salida por su cuenta.
- Transiciones legales en el backend (cualquier otra responde `409 TRANSICION_INVALIDA`):
  `ESTACIONADO→A_PIE`, `ESTACIONADO→SALIENDO`, `A_PIE→REGRESANDO`, `REGRESANDO→SALIENDO`,
  `REGRESANDO→A_PIE` (se volvió a alejar) y cualquier estado abierto `→ CERRADA` (solo por
  `/cerrar`).
- Un cierre `motivo: "deteccion"` solo se acepta desde `SALIENDO`. Un cierre
  `motivo: "manual"` (por ejemplo, el operador de la demo) se acepta desde cualquier estado
  abierto.
- **Falsa liberación:** marcar `CERRADA` (puesto libre) mientras el vehículo sigue físicamente
  estacionado. En la simulación se verifica con `traci.vehicle.isStoppedParking(vehId)` en el
  momento del cierre; el controlador lo registra y lo publica en `verdad` (§6).

## 4. API REST del backend (FastAPI, prefijo `/api/v1`)

### 4.1 Reglas generales

- **Versionado:** toda petición HTTP lleva el header `X-Contrato-Version: 1` y toda respuesta
  lo devuelve. Si llega otro valor, el backend responde `400 CONTRATO_INCOMPATIBLE`. Si falta,
  se acepta (para poder probar con `curl`), pero los clientes del proyecto siempre lo envían.
- `Content-Type: application/json` en cuerpos y respuestas.
- **Token de simulación:** las rutas marcadas con 🔒 son solo del controlador TraCI. Si el
  backend define la variable `SIM_TOKEN` (en `.env`, obligatorio en el VPS), exigen el header
  `X-Sim-Token: <SIM_TOKEN>`; si falta o no coincide, `401 TOKEN_SIM_INVALIDO`.
- Las respuestas `202` devuelven `{"aceptado": true}`.

### 4.2 Errores

Todo error HTTP (4xx/5xx) tiene este cuerpo:

```json
{"error": {"codigo": "SALDO_INSUFICIENTE", "mensaje": "Texto legible en español", "detalle": null}}
```

`detalle` es opcional (objeto libre, por ejemplo los campos inválidos). Códigos:

| Código | HTTP | Cuándo |
|---|---|---|
| `VALIDACION` | 422 | El cuerpo o los parámetros no cumplen el esquema. |
| `CONTRATO_INCOMPATIBLE` | 400 | `X-Contrato-Version` distinto de `1`. |
| `TOKEN_SIM_INVALIDO` | 401 | Falta o no coincide `X-Sim-Token` en una ruta 🔒. |
| `SALDO_INSUFICIENTE` | 402 | `disponible` < retención del bloque mínimo al crear la sesión. |
| `SESIONES_BLOQUEADAS` | 403 | El saldo es negativo: no se permiten sesiones nuevas hasta recargar. |
| `PUESTO_NO_EXISTE` | 404 | `puesto_id` desconocido. |
| `SESION_NO_EXISTE` | 404 | `sesion_id` desconocido. |
| `VEHICULO_NO_EXISTE` | 404 | El vehículo del espejo no está (o ya salió de) la simulación. |
| `SIN_PUESTOS_LIBRES` | 404 | `GET /guia` no encontró un puesto con plazas libres. |
| `PUESTO_LLENO` | 409 | `ocupados == capacidad` al crear la sesión. |
| `SESION_ACTIVA` | 409 | El usuario ya tiene una sesión abierta. |
| `SESION_YA_CERRADA` | 409 | Transición o cierre sobre una sesión `CERRADA`. |
| `TRANSICION_INVALIDA` | 409 | La transición pedida no es legal (§3). |
| `RECARGA_MINIMA` | 422 | `monto` < `recarga_minima_usd`. |
| `ERROR_INTERNO` | 500 | Cualquier otro fallo del servidor. |

Reservados **solo para el cliente** (nunca los envía el backend): `SIN_CONEXION` y
`TIEMPO_AGOTADO`.

### 4.3 Rutas

| Método y ruta | Cuerpo / parámetros | Respuesta | Modelo (`esquemas.py`) |
|---|---|---|---|
| `GET /salud` | — | `{ok, contrato: 1, t_sim}` | `Salud` |
| `GET /tarifa` | — | El contenido de `tarifa.json` | `Tarifa` |
| `GET /puestos` | — | `[{puesto_id, lat, lon, calle, capacidad, ocupados}]` | `Puesto` |
| `GET /guia` | `?lat=&lon=&destino_lat=&destino_lon=` | `{puesto_id, lat, lon, distancia_m}` o `404 SIN_PUESTOS_LIBRES` | `ConsultaGuia` → `Guia` |
| 🔒 `POST /sim/paso` | Paso de simulación (§4.4) | `202` | `PasoSimulacion` |
| `POST /eventos/ubicacion` | `{usuario_id, origen, ts, t_sim?, lat, lon, velocidad_mps?, precision_m?}` | `202` | `EventoUbicacion` |
| `POST /eventos/modo` | `{usuario_id, ts, t_sim?, modo, confianza, fuente}` | `202` | `EventoModo` |
| `POST /sesiones` | `{usuario_id, placa, puesto_id, ts?, t_sim?}` | `201 {sesion_id, estado: "ESTACIONADO", retenido}` | `NuevaSesion` → `SesionCreada` |
| 🔒 `POST /sesiones/{id}/transicion` | `{estado, ts, t_sim?}` | `{sesion_id, estado}` | `TransicionSesion` → `EstadoActualSesion` |
| `POST /sesiones/{id}/cerrar` | `{ts, t_sim?, motivo: "deteccion"\|"manual"}` | `{sesion_id, minutos_reales, minutos_cobrados, debitado, saldo}` | `CierreSesion` → `SesionCerrada` |
| `GET /sesiones/{id}` | — | Sesión completa | `Sesion` |
| `GET /billetera/{usuario_id}` | — | `{saldo, retenido, disponible, bloqueada, movimientos: [...]}` | `Billetera` |
| `POST /billetera/{usuario_id}/recarga` | `{monto, referencia_payphone?}` | `201 {movimiento_id, saldo}` | `Recarga` → `RecargaHecha` |
| `GET /espejo/candidatos` | — | `[{id, destino_nombre, estado, t_sim}]` | `CandidatoEspejo` |

Detalles:

- **`POST /sesiones`:** `ts` (opcional; si falta, la hora del servidor) y `t_sim` (opcional)
  marcan el inicio. **Si la sesión tiene `t_sim` al inicio y al cierre, la duración se calcula
  con `t_sim`**; si no, con `ts`. Así el cobro de los autos simulados sigue el reloj de SUMO.
- **`POST /sesiones/{id}/cerrar`:** `minutos_reales` es la duración real; `minutos_cobrados`
  y `debitado` siguen §5; `saldo` es el saldo tras el débito (puede ser negativo).
- **`Sesion`** (respuesta de `GET /sesiones/{id}`):
  `{sesion_id, usuario_id, placa, puesto_id, estado, inicio, fin, t_sim_inicio, t_sim_fin, retenido, minutos_reales, minutos_cobrados, debitado}`;
  `fin`, `t_sim_*`, `minutos_*` y `debitado` son `null` mientras no se cierre.
- **`Movimiento`:** `{movimiento_id, tipo, monto, ts, sesion_id, referencia_payphone}`;
  `monto` siempre es positivo (el `tipo` dice el sentido); `sesion_id` va en
  `retencion`/`debito`/`liberacion` y es `null` en `recarga`; `referencia_payphone` solo en
  recargas pagadas con Payphone.
- **Billetera implícita:** un `usuario_id` sin movimientos tiene saldo 0 (no hay 404). El
  controlador dota de saldo a cada auto simulado con una `recarga` **sin**
  `referencia_payphone` (los autos simulados nunca llaman a Payphone).
- **Placa:** 3 letras, guion opcional y 3 o 4 dígitos (`ABC-1234`); los autos simulados usan
  `SIM-<n>` con 3 o 4 dígitos, que cumple el mismo patrón (`SIM-0042`).

### 4.4 Paso de simulación (`POST /sim/paso`, 🔒)

El controlador TraCI envía **un paso por segundo de simulación como máximo** con todo lo que
el backend necesita para el `snapshot`, el `espejo` y la `verdad`:

```json
{"t_sim": 1234.0, "ts": "2026-10-20T14:03:05Z",
 "vehiculos": [{"id": "sim_veh42", "lat": -2.8973, "lon": -79.0045, "estado": "GUIADO", "con_app": true,
                "modo": "vehiculo", "destino": {"nombre": "Parque Calderón", "lat": -2.897308, "lon": -79.004488},
                "puesto_id": "pa_-106945247#0_0", "ruta": [[-2.8973, -79.0045], [-2.8975, -79.0050]]}],
 "peatones":  [{"id": "ped_veh7", "lat": -2.8968, "lon": -79.0039}],
 "verdad":    {"puestos": [{"puesto_id": "pa_-106945247#0_0", "ocupados": 9, "capacidad": 17}],
               "estacionados": ["sim_veh7"], "falsas_liberaciones": []}}
```

- `vehiculos[].lat/lon` son la posición **verdadera** (para el visor). El GPS con ruido de los
  autos con app se publica aparte con `POST /eventos/ubicacion` (`origen: "sumo"`).
- `estado` es `null` para autos que no buscan parqueo o no tienen app y no se siguen.
- `modo`, `destino`, `puesto_id` y `ruta` son opcionales y solo se envían para autos con app.
- `verdad` es la ocupación real de SUMO. El backend **no la usa** para su mapa de ocupación
  (que se estima con las sesiones) y solo la reenvía al visor como mensaje `verdad` (§6).

## 5. Tarifa (`proyecto/comun/tarifa.json`)

```json
{
  "valor_hora_usd": 0.50,
  "bloque_minimo_min": 30,
  "fraccion_min": 5,
  "cobro_minimo_min": 10,
  "saldo_negativo_max_usd": 0.50,
  "aviso_saldo_min": 10,
  "tiempo_maximo_min": 120,
  "aviso_tiempo_min": 10,
  "recarga_minima_usd": 5.00,
  "tarjeta_bloque_min": 30
}
```

Valores provisionales hasta que Miguel confirme la tarifa SERT vigente. `comun/tarifa.py`
carga y valida el archivo (`cargar_tarifa()`) y ofrece las funciones de cálculo, que son las
**únicas** que deben usar el backend y la app (la app las replica en TS):

- `minutos_cobrados = max(cobro_minimo_min, ⌈minutos_reales / fraccion_min⌉ · fraccion_min)`.
- `costo_usd(m) = redondeo_centavo(m · valor_hora_usd / 60)`.
- **Retención** al crear la sesión: `costo_usd(bloque_minimo_min)` ($0,25).
- **Débito** al cerrar: `costo_usd(minutos_cobrados)`; se libera toda la retención.
- **Tarjeta SERT equivalente** (para el recibo): tarjetas de `tarjeta_bloque_min` (30 min)
  pagadas por adelantado, `⌈minutos_reales / tarjeta_bloque_min⌉ · costo_usd(tarjeta_bloque_min)`,
  con al menos un bloque. `ahorro_usd = tarjeta − cobrado`.
- **Saldo negativo:** el débito se aplica completo aunque deje el saldo negativo (el auto ya
  estuvo estacionado). Mientras `saldo < 0` la billetera queda `bloqueada` y `POST /sesiones`
  responde `403 SESIONES_BLOQUEADAS`. `saldo_negativo_max_usd` es el margen tolerado: cuando
  el costo en curso alcanza `saldo + saldo_negativo_max_usd`, el espejo muestra el aviso
  `saldo_agotado` (el conductor debería salir o recargar).
- **Avisos** (`Aviso`):
  - `saldo_bajo`: lo que queda (`saldo − costo en curso` durante una sesión, `disponible`
    fuera de ella) cubre menos de `aviso_saldo_min` minutos, es decir, es menor que
    `costo_usd(aviso_saldo_min)`;
  - `saldo_agotado`: el costo en curso alcanzó `saldo + saldo_negativo_max_usd`;
  - `tiempo_maximo_cerca`: faltan `aviso_tiempo_min` minutos o menos para `tiempo_maximo_min`;
  - `tiempo_maximo_superado`: la sesión superó `tiempo_maximo_min`;
  - `sesiones_bloqueadas`: saldo negativo.

### Billetera: libro de movimientos

Tipos: `recarga`, `retencion`, `debito`, `liberacion`.

- `saldo` = Σ recargas − Σ débitos.
- `retenido` = Σ retenciones − Σ liberaciones.
- `disponible = saldo − retenido`.
- `bloqueada = saldo < 0`.

## 6. WebSocket `/ws/estado` (backend → visor)

Cada mensaje es JSON con un campo `tipo` (unión discriminada `MensajeWS` en `esquemas.py`).

- `?rol=visor` (por defecto) recibe `snapshot`, `kpi` y `verdad`.
- `?rol=publico` recibe solo `snapshot` y `kpi`. **`verdad` nunca se envía a la app**, que
  además usa `/ws/espejo` y no este canal.

```json
{"tipo": "snapshot", "t_sim": 1234.0, "ts": "2026-10-20T14:03:05Z",
 "vehiculos": [{"id": "sim_veh42", "lat": -2.897, "lon": -79.004, "estado": "BUSCANDO", "con_app": true}],
 "peatones":  [{"id": "ped_veh42", "lat": -2.8968, "lon": -79.0039}],
 "puestos":   [{"puesto_id": "pa_-106945247#0_0", "ocupados": 3, "capacidad": 17}],
 "espejos":   ["sim_veh42"]}
{"tipo": "kpi", "t_sim": 1234.0, "ts": "2026-10-20T14:03:05Z",
 "valores": {"busqueda_media_s": 210.5, "falsas_liberaciones_100": 1.2}}
{"tipo": "verdad", "t_sim": 1234.0, "ts": "2026-10-20T14:03:05Z",
 "puestos": [{"puesto_id": "pa_-106945247#0_0", "ocupados": 9, "capacidad": 17}],
 "estacionados": ["sim_veh7"], "falsas_liberaciones": []}
```

- `snapshot` se envía 1 vez por segundo de simulación como máximo. `snapshot.puestos` es la
  ocupación que **estima el sistema**; `verdad.puestos` es la real de SUMO. La diferencia es el
  KPI de precisión del mapa.
- `espejos` lista los vehículos que algún teléfono está siguiendo; el visor los resalta.
- `kpi.valores` es un diccionario `nombre → número`. Nombres reservados:
  `busqueda_media_s`, `distancia_busqueda_media_m`, `co2_busqueda_g`,
  `falsas_liberaciones_100`, `retardo_cierre_medio_s`, `error_facturacion_medio_usd`,
  `precision_mapa`. Se pueden añadir otros sin cambiar de versión.
- `verdad.falsas_liberaciones` lista los `sesion_id` cerrados en ese paso mientras
  `isStoppedParking` seguía siendo verdadero.

## 7. Modo espejo (teléfono = pantalla de un conductor simulado)

| Método y ruta | Respuesta |
|---|---|
| `GET /api/v1/espejo/candidatos` | Vehículos con app que aún no estacionan: `[{id, destino_nombre, estado, t_sim}]` |
| `WS /ws/espejo/{veh_id}` | Mensajes `espejo` a 1 Hz, solo de ese vehículo; al final, `espejo_fin` |

```json
{"tipo": "espejo", "veh_id": "sim_veh42", "t_sim": 1234.0, "ts": "2026-11-05T15:04:05.120Z",
 "estado": "GUIADO", "lat": -2.897, "lon": -79.004, "modo": "vehiculo",
 "destino": {"nombre": "Parque Calderón", "lat": -2.897308, "lon": -79.004488},
 "puesto": {"puesto_id": "pa_-106945247#0_0", "lat": -2.8898155, "lon": -78.9956309, "distancia_m": 180},
 "ruta": [[-2.897, -79.004], [-2.8975, -79.005]],
 "sesion": {"sesion_id": "ses_91ab3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d", "minutos": 12.5, "costo_usd": 0.10, "retenido_usd": 0.25},
 "billetera": {"saldo": 4.85, "disponible": 4.60},
 "avisos": ["saldo_bajo"],
 "recibo": null}
{"tipo": "espejo_fin", "veh_id": "sim_veh42", "t_sim": 2400.0, "ts": "2026-11-05T15:55:11Z", "motivo": "salio_simulacion"}
```

- `estado` puede ser `null` mientras el auto aún no busca parqueo; `modo`, `destino`, `puesto`,
  `sesion`, `billetera` y `recibo` pueden ser `null`; `ruta` y `avisos` pueden ser listas
  vacías.
- `sesion.minutos` son los minutos reales transcurridos y `sesion.costo_usd = costo_usd(minutos)`
  (costo en curso **sin** redondear a fracciones; el cobro final usa `minutos_cobrados`, §5).
- Al pasar a `CERRADA`, `recibo` trae
  `{minutos_reales, minutos_cobrados, cobrado_usd, tarjeta_sert_usd, ahorro_usd}` (§5).
- `ts` es la hora UTC en que el backend emitió el mensaje (para medir la latencia hasta la
  pantalla).
- `espejo_fin.motivo`: `"salio_simulacion"` (el vehículo salió de SUMO) o
  `"fin_simulacion"` (terminó la corrida). Tras `espejo_fin` el backend cierra el socket.
- Si `veh_id` no existe al conectar, el backend envía `espejo_fin` con
  `motivo: "no_existe"` y cierra.

## 8. Trazas GPS (archivos CSV)

El emulador GPS de SUMO, GeoLife ya procesado y las grabaciones caseras opcionales usan el
mismo CSV (`FilaTraza` en `esquemas.py`), UTF-8, separador coma, punto decimal, con
encabezado y **estas 7 columnas primero y en este orden**:

```
usuario_id,t,lat,lon,precision_m,velocidad_mps,modo_real
```

- `usuario_id`: texto libre sin comas. Convención: `sim_<vehId>` (SUMO), `geolife_<nnn>`
  (GeoLife, con el número de usuario original) y `casa_<persona>_<n>` (grabaciones caseras).
- `t`: segundos (`float`), crecientes dentro de cada `usuario_id`. En SUMO es `t_sim`; en
  GeoLife, segundos Unix UTC.
- `precision_m`, `velocidad_mps` y `modo_real` pueden quedar vacías (desconocidas).
- `modo_real` es la etiqueta verdadera (`a_pie`, `quieto` o `vehiculo`).
- Se permiten columnas extra **después** de las 7 (por ejemplo `segmento_id` de Pablo); quien
  no las conozca las ignora.

## Cambios respecto a v0

1. **§0 nuevo:** diagrama de componentes y regla de que la máquina de estados corre en el
   controlador TraCI y el backend la valida, la guarda y cobra.
2. **§1:** regex de validación por identificador; nuevo prefijo `ped_` para peatones; un
   puesto es una `parkingArea` con capacidad; los `puesto_id` nunca van en la URL; formato de
   horas (zona obligatoria), coordenadas, dinero (2 decimales, centavos internos) y unidades.
3. **§3:** la sesión nace en `ESTACIONADO` (`BUSCANDO`/`GUIADO` son del vehículo); columna
   "quién la comunica"; nueva ruta `POST /sesiones/{id}/transicion`; **el cierre de un auto
   simulado lo pide el controlador con `POST /sesiones/{id}/cerrar`**; lista de transiciones
   legales, incluida `REGRESANDO → A_PIE`.
4. **§4.1 nuevo:** header `X-Contrato-Version: 1`, token `X-Sim-Token` para rutas del
   controlador y `202 {"aceptado": true}`.
5. **§4.2 nuevo:** formato de error `{"error": {"codigo", "mensaje", "detalle"}}` y tabla de
   códigos con su HTTP (`SALDO_INSUFICIENTE`, `PUESTO_LLENO`, `SESION_NO_EXISTE`,
   `SESIONES_BLOQUEADAS`, `TRANSICION_INVALIDA`…).
6. **§4.3:** rutas nuevas `GET /salud`, `GET /tarifa`, `POST /sim/paso`,
   `POST /sesiones/{id}/transicion`; `POST /sesiones` acepta `ts` y `t_sim` y responde `201`;
   `cerrar` devuelve además `minutos_reales` y `saldo`; `Billetera` añade `bloqueada`; se
   definen los campos de `Sesion` y `Movimiento` (tomando la propuesta de Miguel); billetera
   implícita con saldo 0; formato de placa.
7. **§4.4 nuevo:** `POST /sim/paso`, la vía por la que el backend recibe posiciones, estados y
   la ocupación real (v0 no decía de dónde salía el `snapshot`).
8. **§5:** fórmulas exactas de cobro, retención, tarjeta SERT y avisos; nuevos parámetros
   `aviso_tiempo_min` y `tarjeta_bloque_min`; reglas de saldo negativo y bloqueo; el libro
   define también `retenido`.
9. **§6:** mensaje nuevo **`verdad`** (ocupación real de SUMO para el KPI de precisión del
   mapa, solo en simulación, solo con `?rol=visor`, nunca visible para la app); `kpi` lleva
   `ts`; nombres de KPI reservados; `snapshot.puestos` es la estimación del sistema.
10. **§7:** qué campos del espejo pueden ser `null`; `espejo_fin` con `t_sim`, `ts` y `motivo`;
    qué pasa si el vehículo no existe.
11. **§8:** codificación del CSV, significado de `t`, columnas vacías y columnas extra.
12. **Código compartido:** `comun/esquemas.py`, `comun/esquemas.ts`, `comun/tarifa.json`,
    `comun/tarifa.py` y `comun/ejemplos/`, con tests que verifican que los ejemplos validan y
    que el `.ts` tiene los mismos campos que el `.py`.
