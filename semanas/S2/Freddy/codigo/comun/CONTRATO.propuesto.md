# Propuesta de cambios al contrato v1 (Freddy, S2 · sesión 1)

> Lo propone Freddy como custodio, a partir de la implementación FastAPI de S2-1. Ninguno de
> estos cambios rompe a los clientes actuales: son **aditivos**. Si se aprueban en la
> unificación del 1 de noviembre, se aplican a `docs/CONTRATO.md` sin cambiar de versión (sigue `1`).
> Las secciones de `docs/CONTRATO.md` que no se mencionan aquí quedan igual.

## 1. `POST /api/v1/interno/snapshot` (🔒), alias de `POST /sim/paso` (§4.3, §4.4)

- Mismo cuerpo (`PasoSimulacion`), la misma respuesta `202 {"aceptado": true}` y el mismo límite
  de 1 paso por segundo de simulación.
- **Por qué:** `docs/DESPLIEGUE.md` y el prompt de S2-1 nombran esta ruta para el controlador
  que publica al VPS (`--publicar https://demo...`). Con el alias valen las dos rutas y nadie
  tiene que cambiar nada.

## 2. Token de simulación: dos headers y un nombre de variable (§4.1)

- Las rutas 🔒 aceptan **`X-Sim-Token: <token>`** (lo que ya dice el contrato) **o**
  **`Authorization: Bearer <token>`** (lo que dice `DESPLIEGUE.md`).
- La variable de entorno se llama **`ESERT_TOKEN_SIM`**, como en `DESPLIEGUE.md`. Se acepta
  también `SIM_TOKEN` como alias.
- Si no hay token configurado, las rutas 🔒 quedan abiertas (uso local, como ya dice §4.1). En
  el VPS el token es obligatorio.

## 3. `GET /salud` también en la raíz (§4.3)

- `GET /salud` responde además fuera del prefijo, con el mismo modelo `Salud`
  (`{ok, contrato, t_sim}`). Lo usa el healthcheck de Dokploy.
- `DESPLIEGUE.md` pide también un campo `version`. **Propuesta:** añadir a `Salud` el campo
  opcional `version: str | null` (versión de la app, no del contrato). Hoy no se envía, porque
  `Salud` tiene `extra="forbid"` y el contrato aún no incluye ese campo.

## 4. `WS /ws/estado`: parámetro `verdad` (§6)

- Se mantiene `?rol=visor` (por defecto, recibe `verdad`) y `?rol=publico` (nunca la recibe).
- Nuevo parámetro opcional `?verdad=0|1`, que solo tiene efecto con `rol=visor`. `verdad=0`
  sirve para un visor proyectado en público sin la ocupación real.
- **Nota:** el prompt de S2-1 decía "no difundas `verdad` salvo con `?verdad=1`". Se siguió el
  contrato v1, que ya estaba congelado (el visor la recibe por defecto). Tyrone decide si
  invierte el valor por defecto.

## 5. Semántica de `GET /guia` (§4.3)

- `distancia_m` es la distancia en línea recta (haversine) **del puesto al destino**, no del
  auto al puesto. Se elige el puesto libre más cercano al destino. Hay que dejarlo escrito
  porque el contrato no lo dice.

## 6. Errores fuera del contrato (§4.2)

- Una ruta inexistente o un método no permitido devuelven `404` o `405` con el formato del
  contrato. Como no hay un código propio para ese caso, por ahora usan `codigo: "VALIDACION"`
  y `detalle: {"http": 404|405}`.
- **Propuesta:** añadir `RUTA_NO_EXISTE` (404) y usarlo en lugar de `VALIDACION`.
