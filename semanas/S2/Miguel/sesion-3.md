---
semana: S2
persona: Miguel
sesion: 3
titulo: Modo espejo conectado a la simulación
horas: 3-4
modulo: app
depende: [S1-Miguel-3, S2-Miguel-1, S2-Freddy-1]
entrega: [app/src/api/espejo.ts, app/src/espejo/socketEspejo.ts, app/src/espejo/usarEspejo.ts, app/src/espejo/notificaciones.ts, app/src/espejo/latencia.ts, app/src/espejo/__tests__/, app/mock_espejo/servidor_mock.py, app/mock_espejo/README.md]
evidencias: [s3_espejo-en-vivo.png, s3_latencia-espejo.png]
---
# S2 · Sesión 3 · Miguel 🔴: Modo espejo conectado a la simulación

## Contexto
Lee `CLAUDE.md`, `docs/CONTRATO.md` (secciones 3, 6 y **6b**) y `docs/DESPLIEGUE.md`. **Todo es
simulado**: el teléfono no se mueve ni envía su GPS; sigue a un vehículo de SUMO con app y muestra lo
que vería su conductor. Las pantallas y el recorrido mock son de S1-3 (`proyecto/app/`). Hoy se
cambia el mock interno por la red: `GET /api/v1/espejo/candidatos` y `WS /ws/espejo/{veh_id}` de
Freddy (`proyecto/backend/` o `origin/freddy/s2`, solo lectura). Si aún no existen (el espejo del
backend es de S3-Freddy-3), usa un **servidor mock local** que reproduce `recorrido_mock.json`,
marcado `# MOCK: reemplazar cuando Freddy publique el modo espejo (S3-3)`.

## SUMO en el contenedor
Esta sesión usa SUMO. Sigue la sección **"SUMO en el contenedor `van3twin`"** de `CLAUDE.md`:
- Antes de empezar, comprueba que el repo está clonado en `van3twin-docker/results/e-sert` y
  que `docker ps` muestra `van3twin`. Si no, avisa al usuario y no sigas con la parte de SUMO.
- `git` y la edición de archivos van en la computadora. `sumo`, `netconvert`, `randomTrips.py`
  y los scripts que importan `traci` o `sumolib` van dentro del contenedor:
  `docker exec -w /home/vanet/results/e-sert/<carpeta> van3twin bash -lc "<comando>"`.
- Es SUMO 1.12 con Python 3.10. Si algo de este prompt no existe en esa versión, adáptalo y
  anótalo en la bitácora.
- `sumo-gui` se abre en la pantalla virtual del contenedor y el usuario lo ve por VNC en
  `127.0.0.1:5901`. Las capturas se hacen con `traci.gui.screenshot` o `--screenshot`.
- El controlador TraCI corre en el contenedor, junto a SUMO, y el backend en la computadora
  (`--host 0.0.0.0`). Desde el contenedor, la URL del backend usa `host.docker.internal` o la
  puerta de enlace, como explica `CLAUDE.md`.

## Objetivo
Que la app elija un vehículo real de la simulación (o del mock), lo siga en vivo con un WebSocket
robusto, avise con notificaciones locales en las transiciones clave y mida la latencia
evento → pantalla, contra el VPS si está en línea o en local.

## Pasos
1. **Servidor mock** `app/mock_espejo/servidor_mock.py` (FastAPI + `uvicorn`, `# MOCK` en la
   cabecera): `GET /api/v1/espejo/candidatos` devuelve 3 vehículos; `WS /ws/espejo/{veh_id}`
   reproduce el JSON grabado a 1 Hz (`asyncio.sleep(1)`), añade `ts` ISO con milisegundos y termina
   con `espejo_fin`; `--bucle` repite el recorrido y `--cortar-en N` cierra el socket a los N s para
   probar la reconexión. Se lanza con `uvicorn ... --host 0.0.0.0 --port 8001` **en segundo plano**.
   Si el backend de Freddy ya trae el espejo, graba 2 min reales a `app/mock_espejo/grabacion.jsonl`
   y reprodúcelos en vez del mock de S1-3.
2. **Cliente REST** `app/src/api/espejo.ts`: `getCandidatos(): Promise<CandidatoEspejo[]>` con los
   tipos de `comun/esquemas.ts` (copia en `app/src/contrato/`), *timeout* de 8 s y `ErrorApi`.
   La base sale de `EXPO_PUBLIC_API_URL` o de Ajustes; la URL WS se deriva (`https` → `wss`).
3. **WebSocket** `app/src/espejo/socketEspejo.ts`, clase `SocketEspejo` con
   `conectar(vehId, {onMensaje, onFin, onEstado})` y `cerrar()`:
   - reconexión exponencial 1, 2, 4, 8, 16 s con tope de 30 s y *jitter* ±20 %; reinicia el
     contador al recibir el primer mensaje;
   - vigilancia: si pasan 5 s sin mensaje (se esperan 1 Hz), cierra y reconecta;
   - `AppState`: en segundo plano cierra; al volver a primer plano reconecta enseguida;
   - con `espejo_fin` o `cerrar()` manual no reconecta; mensajes inválidos (`esMensajeEspejo`) se
     descartan con `console.warn`; cada mensaje es completo, así que no hace falta reproducir huecos;
   - `onEstado("en_vivo" | "reconectando" | "sin_conexion", intento)` alimenta un indicador en la
     cabecera de la pantalla.
4. **Hook** `usarEspejo(vehId)` sustituye a `suscribirMock` en `app/espejo/[vehId].tsx` y en el
   selector; `EXPO_PUBLIC_USE_MOCK=1` conserva el mock interno de S1-3 sin red.
5. **Notificaciones** `app/src/espejo/notificaciones.ts` con `expo-notifications` (`npx expo install
   expo-notifications`; en Expo Go solo **locales**): permisos con `requestPermissionsAsync()`, canal
   Android `"espejo"` con `AndroidImportance.HIGH` y `setNotificationHandler` para verlas en primer
   plano. Dispara `scheduleNotificationAsync({content, trigger: null})` una sola vez por
   `(veh_id, estado)` en GUIADO ("Puesto asignado a N m"), ESTACIONADO ("Sesión iniciada, retenido
   $X"), SALIENDO y CERRADA ("Cobrado $X, ahorraste $Z"), y al aparecer `saldo_bajo` en `avisos`.
6. **Latencia** `app/src/espejo/latencia.ts`: al pintar (`requestAnimationFrame` tras el `setState`)
   registra `t_pintado − ts_mensaje − desfase`. El desfase de reloj se estima con el método de
   Cristian (5 peticiones a `GET /salud`, mitad del RTT; usa `ts` del servidor si existe, si no el
   header `Date`). Registra también recepción → pintado, que no depende del reloj. Exporta CSV
   (`modo,t_sim,lat_total_ms,lat_cliente_ms`) con `expo-sharing`.
7. **Tests** (`jest-expo`, `jest.useFakeTimers()` y un `WebSocket` falso): la secuencia de
   reconexión es 1, 2, 4, 8, 16, 30, 30 s (sin *jitter* en el test); el silencio de 5 s fuerza la
   reconexión; `espejo_fin` no reconecta; cada transición notifica una sola vez. Un subagente escribe
   los tests y el servidor mock mientras tú haces el socket y el hook.
8. **Pruebas**: corta el mock con `--cortar-en 20` y comprueba que la app reconecta sola en ≤ 30 s;
   pasa la app a segundo plano 30 s y vuelve. Luego sigue 3 recorridos completos y exporta las
   latencias.
9. **Evidencias**: `s3_espejo-en-vivo.png` (captura del teléfono siguiendo al auto junto a sumo-gui
   o el visor con el mismo vehículo, unidas con Pillow) y `s3_latencia-espejo.png` (histograma con
   p50 y p95 por modo, matplotlib `dpi=150`).

## VPS (demo en línea)
Antes de probar, `curl -s https://demo.e-sert.tesisucuenca.com/salud`. Si responde y existe
`/api/v1/espejo/candidatos`, apunta `EXPO_PUBLIC_API_URL=https://demo.e-sert.tesisucuenca.com` y
pide que una corrida publique en el VPS: el token `ESERT_TOKEN_SIM` lo tiene **solo Tyrone**, así que
coordínalo o deja `@Tyrone [VPS]` en la bitácora; nunca pidas el token. Si no responde, todo en
local: backend o mock en la laptop y el teléfono con la IP de la laptop en la misma red (nunca
`localhost` en el teléfono). Compara las latencias de ambos modos si puedes.

## Dónde escribir
`semanas/S2/Miguel/codigo/app/` y `semanas/S2/Miguel/evidencias/`. Ningún `.env` en el commit.

## Hecho cuando
- [ ] La app lista candidatos y sigue un vehículo de principio a fin (backend real o mock, anotado).
- [ ] Tras cortar el servidor, la app reconecta sola en ≤ 30 s y el indicador lo refleja.
- [ ] Las notificaciones de GUIADO, ESTACIONADO, SALIENDO y CERRADA llegan una sola vez cada una.
- [ ] La latencia evento → pantalla (p50 y p95) queda en la bitácora, con el modo (VPS o local).
- [ ] `npx jest app/src/espejo` y `npx tsc --noEmit` pasan.
- [ ] Existen las dos evidencias PNG y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 3, Miguel), **incluido el PDF
semanal**. En "Pedidos a otros": @Freddy, añadir `ts` a los mensajes `espejo` y las diferencias con
6b que encontraste; @Tyrone, resaltar en el visor los ids de `espejos`.
