# Propuesta de cambios al contrato v1.1 (Freddy, S3 · sesión 1)

> La propone Freddy como custodio, a partir de los KPIs de sistema de S3-1. El cambio es
> **aditivo**: no rompe a ningún cliente. Si se aprueba en la unificación del 8 de noviembre, se
> aplica a `docs/CONTRATO.md` como v1.2. Las secciones que no se mencionan aquí quedan igual.

## 1. `POST /api/v1/sim/kpi` (🔒): entrada de los KPIs en vivo (§4.4 y §6)

- Cuerpo: el mismo mensaje `MensajeKpi` de §6
  (`{"tipo": "kpi", "t_sim": 1234.0, "ts": "...", "valores": {"nombre": número}}`).
- Respuesta `202 {"aceptado": true}`. Exige el token de simulación, igual que `/sim/paso`
  (`X-Sim-Token` o `Authorization: Bearer`). Sin token devuelve `401 TOKEN_SIM_INVALIDO`.
- El backend lo difunde tal cual por `/ws/estado` a `rol=visor` y `rol=publico`.
- `KPIsSistema` (controlador TraCI) lo envía cada 10 s simulados con los nombres reservados
  `falsas_liberaciones_100`, `retardo_cierre_medio_s`, `error_facturacion_medio_usd` y
  `precision_mapa`, más `precision_mapa_app` y `libres_fantasma`. Los valores aún indefinidos (por ejemplo,
  sin sesiones cerradas) **se omiten**: `NaN` no es JSON válido.
- **Por qué:** §6 define el mensaje `kpi`, pero ninguna ruta permitía a un controlador en otro
  proceso (el contenedor o el VPS) publicarlo. Hasta ahora solo se podía hacer en proceso
  (`Servicios.publicar_snapshot`).

## 2. `verdad` lleno desde el controlador (§4.4): aclaración, sin cambio de esquema

- `verdad.puestos[].ocupados` es `parkingarea.getVehicleCount` (todos los autos, con o sin app),
  limitado a la capacidad.
- `verdad.estacionados` son los `sim_<veh>` **con app** cuyo bit de parking de `VAR_STOPSTATE`
  está encendido.
- `verdad.falsas_liberaciones` son los `sesion_id` cerrados desde el paso anterior mientras
  `isStoppedParking` seguía en verdadero.
