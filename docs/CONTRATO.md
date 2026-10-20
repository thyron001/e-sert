# Contrato de interfaces (v0, borrador)

> Estado: **borrador v0**. Freddy lo revisa y lo congela como **v1** en S1 · Sesión 1. Desde
> ese momento, cualquier cambio entra solo como `CONTRATO.propuesto.md` y se aprueba en la
> unificación del domingo.

Este documento es lo que permite que las cuatro piezas encajen. Si tu código produce o
consume algo de aquí, debe respetarlo al pie de la letra.

## 1. Identificadores

| Entidad | Formato | Ejemplo |
|---|---|---|
| Puesto (parkingArea de SUMO) | `pa_<edgeId>_<n>` | `pa_-12345#2_0` |
| Usuario simulado | `sim_<vehId>` | `sim_veh42` |
| Usuario real (app) | `app_<uuid4>` | `app_7f1c…` |
| Sesión de parqueo | `ses_<uuid4>` | `ses_91ab…` |
| Movimiento de billetera | `mov_<uuid4>` | `mov_02cd…` |

Las horas se escriben en ISO 8601 UTC (`2026-10-20T14:03:05Z`). En la simulación se usa
además `t_sim`, en segundos de simulación.

## 2. Modos de movimiento (salida de la IA)

`"a_pie" | "quieto" | "vehiculo"`

- **Ventana:** 30 s de GPS a 1 Hz (se remuestrea si hace falta), con paso de 5 s.
- **Firma de inferencia** (Python, `proyecto/ia/inferencia.py`):
  ```python
  def clasificar(ventana: list[PuntoGPS]) -> ResultadoModo: ...
  # PuntoGPS = {t: float (s), lat: float, lon: float, precision_m: float | None}
  # ResultadoModo = {modo: str, confianza: float (0..1), fuente: "rf" | "umbral"}
  ```
- **Línea base:** con `fuente = "umbral"`, la velocidad media de la ventana mayor a 8 km/h
  es `vehiculo`; menor a 0,5 km/h es `quieto`; el resto es `a_pie`.

## 3. Máquina de estados de la sesión

```
BUSCANDO → GUIADO → ESTACIONADO → A_PIE → REGRESANDO → SALIENDO → CERRADA
              └──────────(sin app)──────────┘
```

| Transición | Disparador |
|---|---|
| `BUSCANDO → GUIADO` | El backend asigna un puesto (`/guia`). |
| `GUIADO → ESTACIONADO` | Llegada confirmada: placa + `puesto_id`. Se retiene el bloque mínimo. |
| `ESTACIONADO → A_PIE` | El modo es `a_pie` y la distancia al puesto es mayor que 15 m. **El puesto sigue ocupado.** |
| `A_PIE → REGRESANDO` | La distancia al puesto es menor que 30 m y el modo es `a_pie` o `quieto`. |
| `REGRESANDO/ESTACIONADO → SALIENDO` | El modo es `vehiculo` durante 2 ventanas seguidas y la distancia al puesto es mayor que 20 m. |
| `SALIENDO → CERRADA` | Se debita el tiempo real y se libera la retención. **El puesto queda libre.** |

Una **falsa liberación** es marcar `CERRADA` (puesto libre) mientras el vehículo sigue
físicamente estacionado. En la simulación se verifica con
`traci.vehicle.isStoppedParking(vehId)`.

## 4. API REST del backend (FastAPI, prefijo `/api/v1`)

| Método y ruta | Cuerpo / parámetros | Respuesta |
|---|---|---|
| `GET /puestos` | — | `[{puesto_id, lat, lon, calle, capacidad, ocupados}]` |
| `GET /guia` | `?lat=&lon=&destino_lat=&destino_lon=` | `{puesto_id, lat, lon, distancia_m}` o `404` |
| `POST /eventos/ubicacion` | `{usuario_id, origen: "sumo"\|"app", ts, t_sim?, lat, lon, velocidad_mps?, precision_m?}` | `202` |
| `POST /eventos/modo` | `{usuario_id, ts, t_sim?, modo, confianza, fuente}` | `202` |
| `POST /sesiones` | `{usuario_id, placa, puesto_id}` | `{sesion_id, estado: "ESTACIONADO", retenido}` |
| `POST /sesiones/{id}/cerrar` | `{ts, t_sim?, motivo: "deteccion"\|"manual"}` | `{sesion_id, minutos_cobrados, debitado}` |
| `GET /sesiones/{id}` | — | Sesión con su estado actual |
| `GET /billetera/{usuario_id}` | — | `{saldo, retenido, disponible, movimientos: [...]}` |
| `POST /billetera/{usuario_id}/recarga` | `{monto, referencia_payphone?}` | `{movimiento_id, saldo}` |

### Billetera: libro de movimientos

Tipos: `recarga`, `retencion`, `debito`, `liberacion`.

- `disponible = saldo − retenido`.
- **Saldo** = suma de recargas − suma de débitos. Las retenciones y liberaciones solo mueven
  `retenido`.

## 5. Tarifa (parámetros en `proyecto/comun/tarifa.json`)

```json
{
  "valor_hora_usd": 0.50,
  "bloque_minimo_min": 30,
  "fraccion_min": 5,
  "cobro_minimo_min": 10,
  "saldo_negativo_max_usd": 0.50,
  "aviso_saldo_min": 10,
  "tiempo_maximo_min": 120,
  "recarga_minima_usd": 5.00
}
```

Los valores son provisionales: Miguel verifica la tarifa SERT vigente en S1.

## 6. WebSocket `/ws/estado` (backend → visor y app)

Cada mensaje es JSON con `tipo`:

```json
{"tipo": "snapshot", "t_sim": 1234.0, "ts": "...",
 "vehiculos": [{"id": "sim_veh42", "lat": -2.897, "lon": -79.004, "estado": "BUSCANDO", "con_app": true}],
 "peatones":  [{"id": "ped_veh42", "lat": ..., "lon": ...}],
 "puestos":   [{"puesto_id": "pa_...", "ocupados": 3, "capacidad": 5}],
 "espejos":  ["sim_veh42"]}
{"tipo": "kpi", "t_sim": 1234.0, "valores": {"busqueda_media_s": 210.5, "falsas_liberaciones_100": 1.2}}
```

El snapshot se envía 1 vez por segundo de simulación como máximo. `espejos` lista los
vehículos que algún teléfono está siguiendo; el visor los resalta.

## 6b. Modo espejo (teléfono = pantalla de un conductor simulado)

Todo el proyecto es simulado. El teléfono no envía su GPS: **sigue a un vehículo de SUMO** y
muestra lo que vería su conductor.

| Método y ruta | Respuesta |
|---|---|
| `GET /api/v1/espejo/candidatos` | Vehículos con app que aún no estacionan: `[{id, destino_nombre, estado, t_sim}]` |
| `WS /ws/espejo/{veh_id}` | Mensajes `{"tipo": "espejo", ...}` a 1 Hz, solo de ese vehículo |

```json
{"tipo": "espejo", "veh_id": "sim_veh42", "t_sim": 1234.0, "ts": "2026-11-05T15:04:05.120Z",
 "estado": "GUIADO", "lat": -2.897, "lon": -79.004, "modo": "vehiculo",
 "destino": {"nombre": "Parque Calderón", "lat": ..., "lon": ...},
 "puesto": {"puesto_id": "pa_...", "lat": ..., "lon": ..., "distancia_m": 180},
 "ruta": [[-2.897, -79.004], ...],
 "sesion": {"sesion_id": "ses_...", "minutos": 12.5, "costo_usd": 0.15, "retenido_usd": 0.25},
 "billetera": {"saldo": 4.85, "disponible": 4.60},
 "avisos": ["saldo_bajo"],
 "recibo": null}
```

- Al pasar a `CERRADA`, `recibo` trae `{minutos_reales, minutos_cobrados, cobrado_usd, tarjeta_sert_usd, ahorro_usd}`.
- `ts` es la hora UTC en que el backend emitió el mensaje (para medir la latencia hasta la pantalla).
- Si el vehículo sale de la simulación, llega `{"tipo": "espejo_fin", "veh_id": ...}`.

## 7. Trazas GPS (archivos)

El emulador GPS de SUMO, GeoLife ya procesado y las grabaciones caseras opcionales usan el mismo CSV:

```
usuario_id,t,lat,lon,precision_m,velocidad_mps,modo_real
```

`modo_real` es la etiqueta verdadera (`a_pie`, `quieto` o `vehiculo`). Queda vacía si no se
conoce.
