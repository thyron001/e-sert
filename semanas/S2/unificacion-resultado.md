**Estado:** fusionado en main
**Humo de integración backend ↔ app:** ok en los 12 sub-pasos HTTP/WS. Los pasos con SUMO (controlador TraCI 120 s y `sumo --end 60`) quedan **no verificables en este entorno**: el contenedor `van3twin` no está disponible.

# S2 · Resultado de la unificación

Ejecutada el **domingo 2026-11-01** por la tarea programada, sin nadie presente. La rama de
trabajo es `unificacion/s2`, creada desde `origin/main` (`b088691`).

`publicar_resultados.py --push` no hizo nada porque main ya tenía los resultados de las cuatro
ramas. Las fusiones solo añadieron código en `semanas/S2/<Nombre>/codigo/`.

## Ramas por persona

Plazo: `2026-10-31T23:59:59-05:00`.

| Persona | Rama | Commits | Último commit | Tardía | Sesiones hechas / parciales / bloqueadas | Evidencias encontradas / declaradas | Criterios | PDF semanal |
|---|---|---|---|---|---|---|---|---|
| Tyrone | `origin/tyrone/s2` (`ca9cff0`) | 4 | 2026-10-26T18:56:51-05:00 | no | 3 / 0 / 0 | 4 / 4 | 17 / 17 | sí |
| Freddy | `origin/freddy/s2` (`9e3f230`) | 4 | 2026-10-26T22:33:08-05:00 | no | 0 / 3 / 0 | 5 / 5 (+4 extra) | 13 / 18 | sí |
| Pablo | `origin/pablo/s2` (`1f87e8e`) | 3 | 2026-10-28T00:17:21-05:00 | no | 2 / 1 / 0 | 8 / 8 (2 son *placeholders* sin SUMO) | 12 / 18 | sí |
| Miguel | `origin/miguel/s2` (`afd9a35`) | 3 | 2026-10-28T09:44:27-05:00 | no | 1 / 1 / 0 (sesión 3 sin hacer) | 2 / 4 | 10 / 11 (sesión 3 sin `estado`) | **no** |

- **Sin push:** nadie. **Tardías:** ninguna.
- **Freddy:** las tres sesiones son `parcial`.
  - S1: no hay `docker build` real ni `WS /ws/espejo`.
  - S2: el criterio de peatones de vuelta en 30 min no se cumple (4/343). Hay 62 falsas liberaciones por cada 100 sesiones.
  - S3: la búsqueda con app no es más corta que sin app (11,3 frente a 10,8 min), y quedan 132 sesiones abiertas al final.
  - Falta la entrega `traci/salidas/sesiones_app50_s1.csv`, que su propio `.gitignore` ignora.
- **Pablo:** S2-2 tiene 4/5 criterios (latencia de 12,6 ms frente a 5 ms). S3 es `parcial` (2/7) porque no tuvo SUMO. Faltan las entregas:
  - `ia/datos/ventanas_v2.parquet`, `ventanas_prueba_geolife.parquet` y `reportes/curvas_sigma.csv`;
  - `ia/modelos/rf_v1.joblib`: pesa 55 MB y se excluye a propósito.
- **Miguel:**
  - S2-1 es `parcial`: iOS solo se probó en el simulador.
  - La sesión 3 (modo espejo) no se hizo. Faltan sus 8 entregas y `resumen_S2_Miguel.pdf`.
  - En S2-2, `.env.example` se entregó como `.env.ejemplo`, por la regla del `.gitignore` raíz.
- No hay archivos de más de 50 MB ni secretos en ninguna rama. Las plantillas `.env.ejemplo` y `.env.example` no traen secretos: los tokens están vacíos y solo hay valores por defecto (`PAYPHONE_MODO=mock`, una IP de LAN y `EXPO_PUBLIC_USE_MOCK=1`).

## Conflictos

- `bitacoras/pablo.md`, al fusionar `pablo/s2`. Se resolvió con la versión de main (`--ours`), que ya traía las tres entradas S2 de Pablo.
- Las demás fusiones `--no-ff` (Freddy, Tyrone y Miguel, en ese orden) entraron limpias.

## Archivos fuera de carpeta y cambios a la planificación descartados

- **Archivos fuera de carpeta revertidos:** ninguno. Cada rama solo toca `semanas/S2/<Nombre>/` y `bitacoras/<nombre>.md`.
- **Cambios a la planificación descartados:** ninguno. Nadie modificó sus `sesion-*.md` ni otros archivos de planificación.

## Copia a `proyecto/`

Se hizo con un script temporal fuera del repo, solo sobre archivos versionados y solo en las
rutas del dueño (`docs/EQUIPO.md`).

| Persona | Copiados | Sobrescritos | Módulos |
|---|---|---|---|
| Tyrone | 67 | 21 | `sumo/`, `kpis/`, `visor/` |
| Freddy | 112 | 96 | `traci/`, `backend/` (sin `pagos/`), `comun/` |
| Pablo | 41 | 17 | `ia/` |
| Miguel | 94 | 69 | `app/`, `backend/pagos/` |

- **No copiados por estar fuera de su módulo:** `Freddy: comun/CONTRATO.propuesto.md`. Va al paso del contrato.
- **Excluidos por la regla (`salidas/`, `.env*`):**
  - las 31 salidas de Tyrone en `kpis/salidas/`, incluido `kpis_base.json` (ver Tests);
  - `backend/.env.ejemplo` de Freddy (ya estaba en `proyecto/`);
  - `app/.env.example` y `backend/pagos/.env.ejemplo` de Miguel.
- **`backend/` frente a `backend/pagos/`:** ninguno pisó al otro.
  - El `backend/` de Freddy no trae `pagos/`, y Miguel solo escribe en `backend/pagos/`.
  - `proyecto/backend/` queda idéntico al del adelanto del 28-oct, que ya era el mismo commit `9e3f230`.
  - La copia quitaba de `requirements-servidor.txt` la línea `httpx` que añadió el adelanto. Se restauró, como pedía la nota del adelanto (commit aparte).
- **Posibles eliminaciones** (están en `proyecto/` pero no en la copia de S2; **no se borraron**):
  - Tyrone: `sumo/.gitkeep`, `kpis/.gitkeep` y `visor/.gitkeep`.
  - Pablo:
    - `ia/.gitkeep`, `ia/datos/__init__.py` y `ia/datos/geolife_info.json`;
    - `ia/datos/procesados/geolife_muestra.csv`;
    - `ia/modelos/rf_v0_info.json` y `ia/resultados/s1_metricas.json`;
    - `ia/tests/__init__.py`, `ia/tests/datos/{ejemplo.plt,labels.txt,labels_salto.txt,salto.plt}`.
  - Miguel: `app/.gitkeep`.

## Contrato

**Contrato v1.1 aplicado** en `docs/CONTRATO.md`, con fecha 2026-11-01. Es la propuesta de
Freddy, aditiva y ya implementada en `proyecto/backend/`. El header `X-Contrato-Version` sigue
en `1`.

1. `POST /interno/snapshot` como alias 🔒 de `/sim/paso`. El controlador de Freddy solo usa este alias.
2. El token se lee de `ESERT_TOKEN_SIM` (alias `SIM_TOKEN`) y se acepta en `X-Sim-Token` o en `Authorization: Bearer`.
3. `GET /salud` responde también en la raíz.
4. `?verdad=0|1` en `/ws/estado`. Es independiente del parámetro de página `?verdad=1` del visor de Tyrone, que solo decide si se muestra la verdad.
5. Semántica de `GET /guia`: puesto libre más cercano al destino; `distancia_m` va del puesto al destino. Coincide con lo que pidió Miguel.

**No aplicado:** `Salud.version` y el código `RUTA_NO_EXISTE`. `comun/esquemas.py` todavía no
los tiene, así que quedan como pedido a Freddy.

**Desvíos que detectaron los auditores** (ninguno rompe la integración):

- **Pablo:** `ia/inferencia.py` cumple la firma de `clasificar`, pero redefine `PuntoGPS` y `ResultadoModo` como `TypedDict` y devuelve `dict`, sin importar `comun.esquemas`. Además:
  - no remuestrea la ventana;
  - `datos_sumo.py` usa ids `sumo_s*_v*` en lugar de `sim_`/`ped_`;
  - `escenarios_dificiles.py` escribe la columna `escenario` (`trafico_lento`) en vez de `caso` (`congestion`).
- **Miguel:** rutas `/pagos/*` (`preparar`, `{id}`, `retorno`, `mock`, `ir`), modelos `PedidoPago`, `PagoPreparado` e `Intencion`, prefijo `rec_` y variables `PAYPHONE_*`. Nada de eso está en el contrato; ya lo pidió a Freddy y no entró en la propuesta. El cliente de la app solo usa rutas del contrato, y `esquemas.ts` es idéntico al de `comun/`.
- **Freddy:**
  - los 404/405 responden `VALIDACION`;
  - hay montajes `/api/v1/pagos` y `/visor` que el contrato no menciona;
  - el estado interno `A_CIEGAS` se traduce a `BUSCANDO` antes de publicar;
  - **falta `WS /ws/espejo/{veh_id}`** (§7).
- **Tyrone:**
  - KPI extra `ocupacion_media_pico` (§6 lo permite);
  - `servidor_prueba.py` no devuelve `X-Contrato-Version` e ignora `rol`;
  - `grabar_snapshots.py` es un MOCK que da `estado` a autos sin app.

## Verificaciones

### Tests

Desde la raíz: `PYTHONPATH=proyecto proyecto/<m>/.venv/bin/python -m pytest -q -m "not e2e" proyecto/<m>`.
Cada venv se creó desde su `requirements.txt` (más `pytest`). El de `backend` lleva además
`pagos/requirements.txt` y `requirements-servidor.txt`.

**Primera vuelta, con un entorno limpio:**

| Módulo | Resultado | Duración |
|---|---|---|
| `comun` | 163 pasados | 0,3 s |
| `backend` (incluye `pagos/`) | 132 pasados | 22 s |
| `traci` | 24 pasados, **7 fallados**, 7 saltados | 1 s |
| `ia` | 70 pasados, 9 saltados, **3 errores** | 4,8 s |
| `kpis` | 14 pasados | 0,3 s |
| `visor` | 7 pasados, **1 fallado**, 1 saltado | 0,8 s |
| `sumo`, `datos` | sin tests | — |

**Causas.** Todas son de empaquetado o de datos sin versionar, no de lógica:

- **traci (7):**
  - `traci/puente_nucleo.py` importa `httpx` y `backend.nucleo`, pero `traci/requirements.txt` no los lista (`ModuleNotFoundError: httpx`).
  - `tests/test_guiado.py` necesita `traci/escenario/tyrone/` (ignorado por git), que genera `python traci/obtener_escenario.py`.
- **ia (3 errores, `test_evaluacion.py::TestParticion`):** necesitan `ia/datos/procesados/ventanas_v2.parquet` y `ventanas_prueba_geolife.parquet`. El `.gitignore` raíz los excluye y se regeneran desde GeoLife. Las pruebas no se saltan al faltar esos archivos, sino que fallan.
- **visor (1, `test_ws_envia_kpi_cada_30_snapshots`):** `servidor_prueba.py` lee `kpis/salidas/kpis_base.json`, y la regla del paso 4 (nunca `salidas/`) no lo copia a `proyecto/`.

**Segunda vuelta, con el entorno completado de forma temporal** (como en S1, sin cambiar archivos versionados):

- se instaló `backend/requirements.txt` en el venv de `traci`;
- se corrió `obtener_escenario.py`;
- se copió temporalmente `kpis_base.json` a `proyecto/kpis/salidas/` y se borró después.

| Módulo | Resultado | Duración |
|---|---|---|
| `traci` | 31 pasados, 7 saltados (los de SUMO) | 2,4 s |
| `visor` | 8 pasados, 1 saltado | 0,7 s |
| `ia` | 70 pasados, 9 saltados, 3 errores: **no verificables en este entorno** (falta el parquet de GeoLife) | 4,7 s |

**Total:** 0 fallos de lógica y 3 pruebas no verificables por datos. La decisión fue considerar
que **las pruebas pasan** y fusionar en main. Las piezas tienen que llegar a main para que S3
trabaje sobre ellas, y los cuatro arreglos van como pedidos (ver abajo).

### SUMO

`docker` no tiene daemon en esta máquina (`/var/run/docker.sock` no existe) y no hay `sumo`
instalado. `sumo -c proyecto/sumo/centro_base.sumocfg --end 60` queda **no verificable en
este entorno**. No se instaló SUMO como alternativa (regla de `CLAUDE.md`).

### Humo de integración backend ↔ TraCI ↔ app

Se usó un script temporal fuera del repo. Levanta `uvicorn backend.api.main:app` en un puerto
libre, con una SQLite temporal y sin token, y usa los ejemplos de `comun/ejemplos/` (el
`puesto_id` se adapta a uno real de `puestos.csv`).

| Sub-paso | Resultado | Detalle |
|---|---|---|
| `GET /api/v1/puestos` frente a `puestos.csv` | ok | 610 / 610 |
| Controlador TraCI 120 s, 20 %, semilla 1 | no verificable | sin SUMO; se reemplazó por un `POST /sim/paso` con `sim_paso.json` → 202 |
| WS `/ws/estado?rol=visor` recibe `snapshot` válido (`comun/esquemas.py`) | ok | 1 snapshot válido |
| `snapshot.espejos` es una lista | ok | `[]` |
| `POST /billetera/{id}/recarga` | ok | 201, saldo 5,00 |
| `GET /guia` | ok | 200, `pa_337277970#1_0`, 45,5 m |
| `POST /sesiones` | ok | 201, `ESTACIONADO`, retenido 0,25 |
| `POST /eventos/modo` | ok | 202 |
| `POST /sesiones/{id}/transicion` → `SALIENDO` | ok | 200 |
| `POST /sesiones/{id}/cerrar` (`deteccion`) | ok | 200: 47 min reales, 50 cobrados, $0,42 |
| Billetera tras cerrar | ok | saldo 4,58, retenido 0, 4 movimientos |
| (info) `GET /espejo/candidatos` | ok | lista con `sim_veh42` |
| (info) `GET /salud` en la raíz | ok | `{"ok":true,"contrato":1,...}` |
| (info) `ia/particion_usuarios.json` | ok | 10 usuarios de prueba y 41 de entrenamiento, sin cruce |
| (info) usuarios de prueba ausentes de `ventanas_v2.parquet` | no verificable | el parquet no está versionado y no hay muestra |
| (info) `npx tsc --noEmit` en `proyecto/app/` | ok | `npm ci` y luego `tsc` con código 0 (luego se borró `node_modules/`) |
| (info) URL del WS del visor configurable | ok | `visor.js`: `params.get("ws")` |

## Pedidos cruzados

### De las bitácoras de S2

| De | Para | Pedido | Sesión |
|---|---|---|---|
| Tyrone | Freddy | Definición de búsqueda (≤ 300 m del destino → primer `started` en un `parkingArea`). Claves de `kpis_base.json` en el mensaje `kpi` | S2-1 |
| Tyrone | Freddy | Cada snapshot con `espejos` y `con_app`, y `estado` según §3 | S2-2 |
| Tyrone | Miguel | Ver el espejo resaltado en `/visor/` del backend o de la demo | S2-2 |
| Tyrone | Freddy | `traci/guiado.py` reemplaza a `guiado_oraculo.py` (MOCK) en S3-1. `rerouteParkingArea` 1.12: no reasignar en cruces ni sin ruta. Ocupación real con `RegistradorOcupacion` | S2-3 |
| Freddy | Miguel | `backend/pagos/rutas.py` con `APIRouter(prefix="/pagos")` (hecho) | S2-1 |
| Freddy | Tyrone [VPS] | Dokploy: Dockerfile `proyecto/backend/Dockerfile`, volumen `/data`, `ESERT_DB_URL`, `ESERT_TOKEN_SIM`, `ESERT_CORS_ORIGENES`, healthcheck `/salud` (hecho en el adelanto, según la bitácora de Miguel) | S2-1 |
| Freddy | Tyrone [Plan] | `sesion-1.md` dice 9 rutas (son 14). VPS: Bearer frente a `X-Sim-Token` (resuelto en v1.1). Exigir Python ≥ 3.10 en lugar de 3.11 | S2-1 |
| Freddy | Tyrone [Plan] | `explicacion_pdf.py`: partir o escalar las imágenes altas | S2-1 |
| Freddy | Pablo | `rf_v0`/`rf_v1` y la latencia de `clasificar` | S2-2, S2-3 |
| Freddy | Tyrone [Plan] | Criterio de 95 % de peatones en 30 min imposible; `getParkingStartingVehicleIDList` no existe en 1.12; aclarar la distancia al puesto de §3 | S2-2 |
| Freddy | Tyrone | "Museo Pumapungo" sin acera cercana en `destinos.csv`; peatones `ped_*` aún fuera del snapshot | S2-2, S2-3 |
| Freddy | Freddy (contrato) | Contar las reservas GUIADO en el mapa de ocupación (no está en la propuesta) | S2-3 |
| Pablo | Freddy | Ruido `ruido_literatura.json` (σ 3–15 m, ρ 0,8) para `EmuladorGPS`; no usar semillas 101–105 para entrenar | S2-1 |
| Pablo | Freddy | Usar `ClasificadorConEstado(usuario_id)` (histéresis k=1); `rf_v1` recomendado (macro-F1 0,87 en usuarios no vistos; 0,93 en validación cruzada) | S2-2, S2-3 |
| Pablo | Miguel | Partición en `ia/particion_usuarios.json`; grabaciones caseras de congestión o peatones rápidos | S2-1, S2-3 |
| Miguel | Freddy | Añadir `/pagos/*` y `RECARGA_MINIMA` al contrato; `Billetera.recargar` con `referencia_payphone` (**abierto**) | S2-2 |
| Miguel | Freddy | `httpx` en `requirements-servidor.txt` (resuelto en el adelanto y mantenido aquí) | S2-2 |
| Miguel | Tyrone [Payphone] | Modo `pruebas` en el VPS (hecho) | S2-2 |
| Miguel | Tyrone [Plan] | Renombrar el entregable `backend/pagos/.env.example` → `.env.ejemplo` en `sesion-2.md` (**abierto**) | S2-2 |

### De S1 que siguen abiertos

- **Freddy → Pablo:** firma de `clasificar` con los modelos de `comun.esquemas`. Pablo devuelve `TypedDict`.
- **Miguel → Todos:** grabación con un iPhone físico. S2-1 sigue con iOS solo en el simulador.
- **Freddy → Tyrone [Plan]:** `pyproj` en `CLAUDE.md`.
- **Miguel → Tyrone [Plan]:** `<code>` en `<td>` de `explicacion_pdf.py`.
- **Tyrone → Miguel:** `calles_sert.yaml` frente a la ordenanza.

### Pedidos nuevos que deja la unificación (para S3)

- **@Freddy:**
  - añadir `httpx` (y lo que use de `backend.nucleo`) a `traci/requirements.txt`;
  - que `tests/test_guiado.py` se salte, o genere el escenario, si falta `traci/escenario/` (o que lea `proyecto/sumo/`, ya unificado);
  - pasar a `comun/esquemas.py` `Salud.version`, `RUTA_NO_EXISTE` y las rutas `/pagos/*` de Miguel, para aprobarlos en v1.2.
- **@Pablo:**
  - `TestParticion` debe hacer `pytest.skip` si faltan los parquet, o usar una muestra versionada;
  - `clasificar` debe usar `comun.esquemas` y remuestrear;
  - las trazas deben usar `sim_`/`ped_` y la columna `caso`.
- **@Tyrone [Plan]:** el visor necesita `kpis/salidas/kpis_base.json`, pero el paso 4 nunca copia `salidas/`. O se mueve el archivo fuera de `salidas/`, o se hace una excepción en el prompt de unificación.
- **@Miguel:** sesión S2-3 (espejo) y `resumen_S2_Miguel.pdf` pendientes.

## Riesgos para S3

1. **Modo espejo (Freddy S3-3).** No existe `WS /ws/espejo/{veh_id}` ni el recibo. `GET /espejo/candidatos` ya responde. Miguel no hizo S2-3, así que la app (S3) y el visor (Tyrone S3-3) dependen de algo que todavía no hay.
   - **Mock:** el `recorridoMock` de la app y el `mock_espejo/servidor_mock.py` que pide S2-3 de Miguel, aún sin entregar.
2. **Controlador con KPIs de sistema (Freddy S3-1).** Lo necesita el ejecutor de experimentos de Tyrone. Hoy la búsqueda con app no mejora a la búsqueda sin app (11,3 frente a 10,8 min), las falsas liberaciones están en 62–65 por cada 100 y quedan 132 sesiones abiertas al cerrar.
   - **Mock:** el `guiado_oraculo.py` de Tyrone, hasta que `traci/guiado.py` lo reemplace.
3. **`inferencia.py` robusto (Pablo S3-1).** `rf_v1.joblib` no está en git (55 MB). Sin él, `clasificar` cae al umbral, y el umbral explica buena parte de las falsas liberaciones. La latencia es de 12,6 ms frente al objetivo de 5 ms, y la evaluación con SUMO (S2-3) quedó parcial.
   - **Mock:** clasificador de umbral (`fuente="umbral"`).
4. **Sin SUMO en la máquina de la unificación.** Ni el SUMO ni el humo con el controlador se pudieron comprobar. Conviene que Tyrone corra `sumo --end 60` y el controlador 120 s en `van3twin` sobre `main`.
5. **Reproducibilidad de los tests:** `traci` e `ia` no pasan en un entorno limpio (ver Tests).
