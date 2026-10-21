---
semana: S3
persona: Freddy
sesion: 3
titulo: Modo espejo en el backend y demo en el VPS
horas: 3-4
modulo: backend
depende: [S2-Freddy-1, S2-Freddy-3, S2-Miguel-3, S3-Freddy-1, S3-Freddy-2]
entrega: [backend/espejo/registro.py, backend/espejo/rutas.py, backend/espejo/ws_espejo.py, traci/espejo_publicador.py, traci/ruta_geo.py, backend/tests/test_espejo.py, traci/tests/test_espejo_publicador.py, comun/esquemas.py, comun/esquemas.ts, comun/CONTRATO.propuesto.md]
evidencias: [s3_espejo-en-vivo.png]
---
# S3 · Sesión 3 · Freddy 🍅: Modo espejo en el backend y demo en el VPS

## Contexto
Lee `CLAUDE.md`, `docs/CONTRATO.md` (secciones 3, 4, 6 y **6b**), `docs/DESPLIEGUE.md` y tus
bitácoras de S3-1 y S3-2. **Todo el proyecto es simulado**: el teléfono de la demo no envía GPS,
es la **pantalla de un conductor simulado**. Miguel ya tiene el modo espejo en la app contra un
mock (S2-Miguel-3, en `proyecto/app/` o `origin/miguel/s3`, solo lectura) y espera hoy el backend
real. El controlador TraCI ya publica snapshots con `--publicar <url> --token $ESERT_TOKEN_SIM`
(S2-3); esta sesión amplía lo que publica y lo sirve por vehículo.

## SUMO en el contenedor
Esta sesión usa SUMO. Sigue la sección **"SUMO en el contenedor `van3twin`"** de `CLAUDE.md`:
- Antes de empezar, comprueba que el repo está clonado en `van3twin-docker/results/e-sert` y
  que `docker ps` muestra `van3twin`. Si no, avisa al usuario y no sigas con la parte de SUMO.
- `git` y la edición de archivos van en la computadora. `sumo`, `netconvert`, `randomTrips.py`
  y los scripts que importan `traci` o `sumolib` van dentro del contenedor:
  `docker exec -w /home/vanet/results/e-sert/<carpeta> van3twin bash -lc "<comando>"`.
- Es SUMO 1.12 con Python 3.10. Si algo de este prompt no existe en esa versión, adáptalo y
  anótalo en la bitácora.
- El controlador TraCI corre en el contenedor, junto a SUMO, y el backend en la computadora
  (`--host 0.0.0.0`). Desde el contenedor, la URL del backend usa `host.docker.internal` o la
  puerta de enlace, como explica `CLAUDE.md`.

## Objetivo
Implementar la sección 6b del contrato de punta a punta: candidatos, WS por vehículo alimentado
desde los snapshots del controlador, recibo al cerrar y el campo `espejos` del snapshot, y
dejarlo funcionando en `https://demo.e-sert.tesisucuenca.com`.

## Pasos
1. **Ampliar lo que publica el controlador** (`traci/espejo_publicador.py`, llamado en cada
   publicación, máximo 1 por segundo de simulación). El cuerpo de `POST /interno/snapshot` suma
   un bloque interno `espejo` que **nunca** se difunde por `/ws/estado`:
   - `candidatos`: vehículos con app en `BUSCANDO` o `GUIADO`, con `id`, `destino_nombre` (del
     `param destino` y `proyecto/sumo/demanda/destinos.csv`), `estado` y `t_sim`;
   - `detalle[veh_id]`, solo para los vehículos seguidos: `estado`, `lat/lon`, `modo` (último
     `ResultadoModo` del conductor o su peatón), `destino`, `puesto` (`puesto_id`, lat/lon,
     distancia restante con `traci.vehicle.getDrivingDistance`), `sesion` (`sesion_id`,
     minutos, `tarifa.costo` en vivo, retenido), `billetera` (`saldo`, `disponible`) y `avisos`;
   - `ruta` (`traci/ruta_geo.py`): `traci.vehicle.getRoute(veh)` desde
     `getRouteIndex(veh)`, forma de cada *edge* con `sumolib` (`net.getEdge(e).getShape()`),
     `net.convertXY2LonLat` → `[[lat, lon], ...]`, simplificada con Douglas-Peucker (≤ 200
     puntos) y en caché por `(tupla_ruta, índice)`; se recalcula solo si cambia la ruta.
   - La respuesta de `/interno/snapshot` devuelve `{"espejos": [...]}` (los IDs que algún teléfono
     sigue): el controlador calcula `detalle` solo para esos. Regístralo en `CONTRATO.propuesto.md`.
2. **Registro en el backend** (`backend/espejo/registro.py`, `RegistroEspejo`):
   - guarda el último `candidatos` y el último `detalle` por vehículo, con `t_sim` y `ts` de
     recepción; descarta el bloque `espejo` del snapshot antes de difundirlo;
   - cuenta suscriptores por `veh_id`; esa lista es el campo **`espejos`** que se añade a cada
     snapshot de `/ws/estado` (el visor de Tyrone lo resalta);
   - detecta los vehículos que salieron de la simulación (ya no están en `vehiculos`).
3. **Rutas** (`backend/espejo/rutas.py` y `ws_espejo.py`):
   - `GET /api/v1/espejo/candidatos` → `[{id, destino_nombre, estado, t_sim}]` (vacío si el
     controlador no publica; `Cache-Control: no-store`);
   - `WS /ws/espejo/{veh_id}`: `404`/cierre `4404` si el vehículo no existe; al conectar envía
     el último estado conocido y luego `{"tipo": "espejo", ...}` a 1 Hz como máximo, **solo de
     ese vehículo**, con los campos exactos de 6b (valida con `comun/esquemas.py`);
   - si el vehículo sale de la simulación, envía `{"tipo": "espejo_fin", "veh_id"}` y cierra;
   - varias pantallas pueden seguir al mismo vehículo; al desconectarse se libera el contador.
4. **Recibo al cerrar**: en `SALIENDO → CERRADA` el controlador incluye en `detalle` el
   `recibo` `{minutos_reales, minutos_cobrados, cobrado_usd, tarjeta_sert_usd, ahorro_usd}` con
   `tarifa.costo` y `tarifa.costo_tarjeta_sert` de S1-2. El backend lo envía **una sola vez**
   por sesión (idempotente por `sesion_id`, aunque lleguen snapshots repetidos) y lo conserva
   60 s para pantallas que se reconecten. Añade `saldo_bajo` y `tiempo_maximo` a `avisos`.
5. **Esquemas**: `MensajeEspejo`, `Recibo`, `Candidato` y `espejos` en `comun/esquemas.py`
   y `esquemas.ts`, con un ejemplo en `comun/ejemplos/espejo.json`.
6. **Tests** (`backend/tests/test_espejo.py`, `TestClient`; `traci/tests/test_espejo_publicador.py`):
   - un snapshot sintético con 3 candidatos → `GET /espejo/candidatos` los devuelve;
   - el WS de `sim_veh42` recibe solo mensajes de `sim_veh42` y a ≤ 1 Hz con 10 snapshots/s;
   - `espejos` del snapshot incluye `sim_veh42` mientras hay suscriptor y lo quita al cerrar;
   - el recibo llega una vez aunque se repita el snapshot; `espejo_fin` al salir el vehículo;
   - `/ws/estado` nunca contiene el bloque interno `espejo`; snapshot sin token → `401`;
   - `ruta_geo` devuelve lat/lon dentro del Centro y ≤ 200 puntos (con SUMO, `-m sumo`).
   Delega en un subagente los tests del publicador mientras tú haces el registro y el WS.
7. **Prueba local completa**: `uvicorn` en segundo plano, `app50_s1` con `--publicar
   http://localhost:8000`, un cliente `websockets` siguiendo un candidato hasta el recibo, y
   latencia snapshot → mensaje espejo (p50 y p95).
8. **Evidencia** `evidencias/s3_espejo-en-vivo.png`: línea de tiempo del vehículo seguido
   (estado, distancia al puesto, costo en vivo y el instante del recibo), más una captura del
   visor con el vehículo resaltado.

## VPS (demo en línea)
Lee `docs/DESPLIEGUE.md`. Tras la unificación, `esert-demo` se construye desde `main`. **Solo
Tyrone toca Dokploy**: lo que necesites va en "Pedidos a otros" como `@Tyrone [VPS]` con el
campo exacto (por ejemplo, confirmar `ESERT_TOKEN_SIM` y el volumen `/data`, un redeploy, los
logs del contenedor y su CPU/RAM). Prueba en línea, desde tu laptop y sin acceso al VPS: el
controlador publica en `https://demo.e-sert.tesisucuenca.com`, un cliente sigue un candidato por
`wss://demo.e-sert.tesisucuenca.com/ws/espejo/<veh_id>` y el visor público lo resalta. Mide la
latencia de punta a punta y comprueba con datos móviles que el WS no se corta en 10 min.

## Dónde escribir
`semanas/S3/Freddy/codigo/backend/`, `semanas/S3/Freddy/codigo/traci/`,
`semanas/S3/Freddy/codigo/comun/` y `evidencias/`. No edites `app/` (es de Miguel).

## Hecho cuando
- [ ] `pytest backend/tests/test_espejo.py traci/tests` pasa y los tests anteriores siguen en verde.
- [ ] En local, un cliente sigue un candidato desde `GUIADO` hasta el recibo, con p95 < 1,5 s.
- [ ] `espejos` aparece en el snapshot y el bloque interno nunca sale por `/ws/estado`.
- [ ] Esquemas Python y TS, ejemplo y `CONTRATO.propuesto.md` actualizados.
- [ ] La prueba en línea en el VPS está documentada (latencia, estabilidad 10 min); si el VPS no
  estaba listo, estado `parcial` con el pedido `@Tyrone [VPS]` anotado.
- [ ] Existen `s3_espejo-en-vivo.png` y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 3, Freddy), **incluido el PDF
semanal**. En "Pedidos a otros": @Miguel, la URL real de candidatos y del WS espejo y el formato
del recibo; @Tyrone, `espejos` ya viene en el snapshot y los pedidos `@Tyrone [VPS]`; @Pablo, la
confianza del modo que ve el espejo.
