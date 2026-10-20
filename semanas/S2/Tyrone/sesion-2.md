---
semana: S2
persona: Tyrone
sesion: 2
titulo: Visor web Leaflet y servidor WS de prueba
horas: 3-4
modulo: visor
depende: [S1-Tyrone-2, S1-Freddy-1]
entrega: [visor/index.html, visor/visor.js, visor/estilos.css, visor/grabar_snapshots.py, visor/servidor_prueba.py, visor/tests/]
evidencias: [s2_visor-leaflet.png]
---
# S2 · Sesión 2 · Tyrone 🔵: Visor web Leaflet y servidor WS de prueba

## Contexto
Lee `CLAUDE.md` y `docs/CONTRATO.md` (secciones 4 y 6, `GET /puestos` y `/ws/estado`). El
backend real de Freddy se construye esta misma semana (S2-1): léelo desde `proyecto/backend/`
o, si aún no está, de `origin/freddy/s2` sin editar. **El visor no debe depender de él para
avanzar**: trabajarás contra un servidor de prueba que reproduce snapshots grabados con el
mismo formato del contrato. Valida los mensajes con `proyecto/comun/esquemas.py`.

## Objetivo
Un visor web estático (sin *build*) que muestre en vivo autos, peatones, teléfonos y puestos
(verde con lugar, rojo lleno) sobre el Centro Histórico, alimentado por `/ws/estado`.

## Pasos
1. Crea `visor/grabar_snapshots.py`: corre `proyecto/sumo/centro_base.sumocfg` con TraCI
   durante 15 min simulados y cada 1 s escribe una línea de `visor/datos/snapshots.jsonl` con
   el mensaje `snapshot` del contrato. Usa `traci.simulation.convertGeo(x, y)` para lat/lon,
   suscripciones de vehículos y personas, y
   `traci.simulation.getParameter(pa, "parkingArea.occupancy")` /
   `"parkingArea.capacity"` para los puestos. Los IDs van como `sim_<vehId>`. Si el
   controlador de Freddy no está, el campo `estado` sale de una regla simple marcada
   `# MOCK` (estacionado si `isStoppedParking`, si no `BUSCANDO`).
   Lánzalo **en segundo plano** mientras construyes el visor.
2. Crea `visor/servidor_prueba.py` (FastAPI + `uvicorn`, o `websockets`):
   - `GET /api/v1/puestos` a partir de `proyecto/sumo/parqueos/puestos.csv`;
   - `WS /ws/estado` que reproduce `snapshots.jsonl` en bucle, con `--velocidad 1|5|10` y
     un mensaje `kpi` cada 30 snapshots (valores de `kpis_base.json` de S2-1);
   - sirve también la carpeta `visor/` como estáticos en `/`.
   - CLI: `python -m visor.servidor_prueba --puerto 8001 --velocidad 5`.
3. Crea `visor/index.html` + `visor.js` + `estilos.css` con Leaflet 1.9 desde CDN:
   - mapa centrado en el Parque Calderón (-2.8974, -79.0045), zoom 16, teselas OSM con
     atribución;
   - `L.canvas()` como *renderer* (`preferCanvas: true`) para aguantar más de 1000
     marcadores a 1 Hz; actualiza marcadores existentes por `id` (`setLatLng`), no los
     recrees; elimina los que desaparecen del snapshot;
   - puestos como `circleMarker` en `#2E9E4F` si `ocupados < capacidad` y `#C62828` si
     están llenos, con *popup* `calle · ocupados/capacidad`;
   - autos coloreados por `estado` (paleta fija en `visor.js`), con borde grueso si
     `con_app`; peatones como puntos pequeños; teléfonos con un ícono distinto y su `modo`;
   - panel lateral: `t_sim`, conteos, últimos KPIs y estado de la conexión;
   - URL del WS configurable: `index.html?ws=ws://localhost:8000/ws/estado`; por defecto el
     servidor de prueba. Reconexión con espera exponencial (1, 2, 4… hasta 30 s).
   - Ignora mensajes `tipo: "verdad"` salvo con `?verdad=1` (capa opcional de depuración).
4. **Tests** (`visor/tests/`, pytest): cada línea de `snapshots.jsonl` valida contra el
   modelo de snapshot de `comun/esquemas.py`; el servidor de prueba entrega al menos 5
   mensajes por WS con `TestClient.websocket_connect`. Un subagente puede escribir estos
   tests en paralelo mientras tú haces el front.
5. Prueba el visor contra el backend real si ya existe (`?ws=ws://localhost:8000/ws/estado`)
   y anota en la bitácora cualquier diferencia de formato.
6. **Evidencia** `evidencias/s2_visor-leaflet.png`: captura del visor con datos en hora pico,
   tomada con Playwright (`page.screenshot`, 1600×1000) desde un script
   `visor/captura.py`; si no hay Playwright, captura manual del navegador.

## Dónde escribir
`semanas/S2/Tyrone/codigo/visor/` y `semanas/S2/Tyrone/evidencias/`. `snapshots.jsonl` grande
va en `.gitignore`; publica una muestra de 60 snapshots.

## Hecho cuando
- [ ] `python -m visor.servidor_prueba` levanta y el visor muestra autos moviéndose y
  puestos que cambian de verde a rojo.
- [ ] El visor mantiene más de 20 FPS con el snapshot de hora pico (mídelo en DevTools).
- [ ] `pytest visor/tests` pasa y todos los snapshots validan contra el contrato.
- [ ] La reconexión funciona: parar y relanzar el servidor no obliga a recargar la página.
- [ ] Existe la evidencia `s2_visor-leaflet.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 2, Tyrone). En "Pedidos a
otros": @Freddy, el visor espera `telefonos` y `con_app` en cada snapshot; @Miguel, la URL
del visor para ver tu teléfono en S2-3.
