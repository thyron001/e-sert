**Estado:** fusionado en main
**Cobertura de experimentos:** 0 de 8 escenarios (penetración {0, 20, 50, 80} % × clasificador {umbral, rf}) con agregados en `proyecto/kpis/`, y 0 con 2 semillas. Tyrone no subió `tyrone/s3`. Solo hay corridas sueltas de Freddy al 50 % y al 80 %, con el umbral y la semilla 1.

# S3 · Resultado de la unificación

La tarea programada la ejecutó el **domingo 2026-11-08**, sin nadie presente. La rama de trabajo
es `unificacion/s3`, creada desde `origin/main` (`9d367e7`).

`publicar_resultados.py --push` no hizo cambios: main ya tenía los resultados de `freddy/s3`,
`pablo/s3` y `pablo/s4`.

## Ramas por persona

Plazo: `2026-11-07T23:59:59-05:00`.

| Persona | Rama | Commits | Último commit | Tardía | Sesiones hechas / parciales / bloqueadas | Evidencias encontradas / declaradas | Criterios | PDF semanal |
|---|---|---|---|---|---|---|---|---|
| Tyrone | **sin push** (`origin/tyrone/s3` no existe) | 0 | — | — | 0 / 0 / 0 | — | — | no |
| Freddy | `origin/freddy/s3` (`d717d89`) | 3 | 2026-11-06T00:36:10-05:00 | no | 2 / 1 / 0 | 8 / 8 | 15 / 16 | sí (`resumen_S3_Freddy.pdf`) |
| Pablo | `origin/pablo/s3` (`c03f28b`) | 3 | 2026-11-06T23:07:53-05:00 | no | 3 / 0 / 0 | 9 / 9 | 15 / 15 | sí (`resumen_S3_Pablo.pdf`) |
| Miguel | **sin push** (`origin/miguel/s3` no existe) | 0 | — | — | 0 / 0 / 0 | — | — | no |

- **Sin push:** Tyrone y Miguel. **Tardías:** ninguna.
- **Freddy:** S3-3 es `parcial` (5/6). Falta la prueba en línea contra el VPS: la demo corre `main` sin S3-3 y el token lo tiene Tyrone.
  - En S3-2, el p95 por paso es de 162 ms, frente a la meta de 100 ms. Está documentado como límite del propio `simulationStep`, cuyo p95 es de 142 ms.
  - Las cifras de S3-1 y S3-2 se tomaron sin guiado. Con los escenarios de Tyrone ningún auto se guiaba, porque `param destino` trae coordenadas. Se corrigió en S3-3, pero esas corridas no se repitieron.
  - En la bitácora de S3-3, el pedido `[VPS]` le pide a Tyrone el token "por privado". `CLAUDE.md` no permite que una sesión que no es de Tyrone pida credenciales. Se anota para Tyrone; no se tocó nada.
- **Pablo:** las tres sesiones están `hecha`. Lo que queda abierto:
  - En S3-3 quedan 4 marcadores `[PENDIENTE: cifra de Tyrone S3-2]` en la Sección 8 de `informe/pablo.md`.
  - La bitácora de S3-2 anota 6 vueltas del bucle (el máximo de `CLAUDE.md` es 5).
  - La latencia que declaran `estado.json` y la bitácora (p95 de 1,56 ms individual y 0,33 ms por ventana en lote) no coincide con la de `ia/reportes/bench_inferencia.json` (1,74 ms y 0,35 ms). Las dos cumplen la meta de < 5 ms.
- **Fuera del alcance de S3:** existe `origin/pablo/s4`, con 3 commits del 2026-11-07 (S4-1 y S4-2 `hecha`, S4-3 `parcial` con 3/6). No se fusiona aquí.
- **Archivos grandes y secretos:** no hay archivos de más de 50 MB ni secretos. `backend/.env.ejemplo` solo tiene claves vacías, y el `"secreto"` de los tests es un valor de prueba.

## Conflictos

- `bitacoras/pablo.md`, al fusionar `pablo/s3`. Se resolvió con la versión de main (`--ours`), que ya traía las tres entradas S3 de Pablo.
- La fusión de `freddy/s3` entró limpia.

## Archivos fuera de carpeta y cambios a la planificación descartados

- **Archivos fuera de carpeta revertidos:** ninguno. Cada rama solo toca `semanas/S3/<Nombre>/` y `bitacoras/<nombre>.md`.
- **Cambios a la planificación descartados:** ninguno. Nadie modificó sus `sesion-*.md` ni otros archivos de planificación.

## Copia a `proyecto/`

Se hizo con un script temporal fuera del repo, solo sobre archivos versionados y solo en las
rutas del dueño (`docs/EQUIPO.md`).

| Persona | Archivos revisados | Nuevos | Sobrescritos | Idénticos | Módulos |
|---|---|---|---|---|---|
| Freddy | 145 | 33 | 25 | 87 | `traci/`, `backend/` (sin `pagos/` ni `asistente/`), `comun/` |
| Pablo | 94 | 42 | 8 | 44 | `ia/`, `informe/` (`pablo.md`, `figuras/ia/`, `referencias_ia.bib` y los scripts) |

- En total, el commit `[S3-U] Copia módulos de S3 a proyecto/` cambia 108 archivos.
- **No copiados por estar fuera de su módulo:**
  - `Freddy: comun/CONTRATO.propuesto.md`, que va al paso del contrato;
  - el `.gitkeep` de la raíz de `codigo/` de Freddy y de Pablo.
- **Excluidos por la regla `.env*`:** `backend/.env.ejemplo` de Freddy, que ya está en `proyecto/`.
- **Resultados de Freddy:** se copiaron los agregados versionados de `traci/salidas_kpi/` (JSON, `robustez.csv` y una figura), porque no son salidas crudas de SUMO. `traci/salidas/` y `traci/escenario/` están ignorados por git.
- **Posibles eliminaciones:** ninguna en los módulos copiados (`backend/.env.ejemplo` solo aparece por la exclusión). No se borró nada.

## Contrato

**Contrato v1.2 aplicado** en `docs/CONTRATO.md`, con fecha 2026-11-08. Es la propuesta de
Freddy de S3, aditiva y ya implementada en `proyecto/comun/esquemas.py` y `proyecto/backend/`,
con tests. `X-Contrato-Version` y `Salud.contrato` siguen en `1`.

1. `POST /sim/kpi` 🔒, que se difunde como `kpi`.
2. Aclaración del mensaje `verdad`: `ocupados`, `estacionados` y `falsas_liberaciones`.
3. Nuevo motivo de cierre `timeout_sin_senal`.
4. Marca `sin_senal` y política de datos pobres.
5. Bloque interno `espejo` y respuesta `RespuestaSnapshot{aceptado, espejos}`.
6. En §7: cierres 4404/1000, 1 Hz con latido de 2 s, recibo una vez por sesión y `Cache-Control: no-store`.
7. `Salud.ts` opcional.

**Coherencia con el código de los demás:**

- **Visor de Tyrone:** consume `kpi` y `verdad` con la misma forma; los cambios solo añaden semántica.
- **App de Miguel:** usa su copia `app/src/contrato/esquemas.ts` de v1.1, que no incluye `timeout_sin_senal` ni `Salud.ts`. Como los cambios son aditivos, no se rompe: `npx tsc --noEmit` sale sin errores.
- **`ResultadoModo` de Pablo:** no cambia.

**Desvíos que siguen abiertos:**

- **Pablo:** `ia/inferencia.py` sigue sin importar `comun.esquemas`. Define `TypedDict` propios, aunque con las claves correctas, y añade `clasificar(ventana, previo=None)` y `clasificar_lote`, que el contrato §2 no documenta.
- **Miguel:** las rutas `/pagos/*` siguen sin estar en el contrato.

## Verificaciones

### Tests

Desde la raíz: `PYTHONPATH=proyecto proyecto/<m>/.venv/bin/python -m pytest -q -m "not e2e" proyecto/<m>`.
Cada venv se creó desde su `requirements.txt` (más `pytest`). El de `backend` lleva además
`pagos/requirements.txt` y `requirements-servidor.txt`.

**Primera vuelta, con un entorno limpio:**

| Módulo | Resultado |
|---|---|
| `comun` | 169 pasados |
| `backend` (incluye `pagos/`) | 148 pasados, 1 saltado |
| `kpis` | 14 pasados |
| `traci` | **3 errores de colección** (`ModuleNotFoundError: httpx`) |
| `ia` | **2 errores de colección** (falta `hypothesis` y falta `pydantic`, que necesita `traci.estados`) |
| `visor` | 7 pasados, 1 saltado, **1 fallado** (`kpis_base.json` en `kpis/salidas/`, que no se copia) |

**Segunda vuelta, con el entorno completado de forma temporal** (como en S1 y S2, sin cambiar archivos versionados):

- se instaló `backend/requirements*.txt` en el venv de `traci`;
- se instalaron `hypothesis` y `comun/requirements.txt` en el venv de `ia`;
- se corrió `traci/obtener_escenario.py`;
- se copió temporalmente `kpis_base.json` y se borró después.

| Módulo | Resultado |
|---|---|
| `traci` | 71 pasados, 12 saltados (los de SUMO) |
| `visor` | 8 pasados, 1 saltado |
| `ia` | 139 pasados, 9 saltados, **10 fallados y 3 errores: no verificables en este entorno** |

Las 13 pruebas no verificables de `ia` dependen de datos sin versionar:

- **10 fallos** necesitan `ia/modelos/rf_v1.joblib`, que pesa 55 MB y está en `ia/modelos/.gitignore`. Sin él, `clasificar` cae al umbral y el test espera `fuente == "rf"`, o lee el archivo para comparar el hash.
  - `test_inferencia.py`: `TestContrato` (3), `TestBordes` (3), `TestEquivalenciaS2` (2) y `TestMeta` (1).
  - `test_s2_sesion2.py::TestFallback` (1).
  - Uno de los dos de `TestEquivalenciaS2` falla, además, por `ventanas_prueba_geolife.parquet`.
- **3 errores** (`test_evaluacion.py::TestParticion`) necesitan los parquet de GeoLife. Ya pasaba en S2.

**Total:** 0 fallos de lógica. Hay 13 pruebas de `ia` no verificables por datos y cuatro
problemas de empaquetado (ver Pedidos). Con el mismo criterio de S2, se considera que **las
pruebas pasan** y se fusiona en main. Es la última semana, y S4 necesita en `proyecto/` el
espejo, los KPIs de sistema y el contrato v1.2.

### SUMO

`docker` no tiene daemon en esta máquina (`/var/run/docker.sock` no existe) y no hay `sumo`
instalado. `sumo -c proyecto/sumo/centro_base.sumocfg --end 60` y la corrida corta del ejecutor
quedan **no verificables en este entorno**. No se instaló SUMO como alternativa.

### Resultados de experimentos

No hay agregados de experimentos en `proyecto/kpis/` (ni `resultados/` ni CSV de la matriz),
porque Tyrone no subió `tyrone/s3`. Tampoco existe el script de figuras finales de S3, así que
no se pudo regenerar ninguna figura. Lo único disponible son las corridas de Freddy en
`proyecto/traci/salidas_kpi/`.

| Penetración | umbral | rf | ≥ 2 semillas |
|---|---|---|---|
| 0 % | falta | falta | no |
| 20 % | falta | falta | no |
| 50 % | solo Freddy: `ejemplo_p50_umbral_s1` (semilla 1) y la rejilla `robustez.csv` (semillas 1–2, solo KPIs de sistema) | `ejemplo_p50_rf_s1` y `_3600`, pero **usaron el umbral** (`clasificador_usado: "umbral"`, falta `rf_v1.joblib`) | no (en la matriz) |
| 80 % | falta (solo perfiles de rendimiento) | `perfil_p80_rf_s1_*`: solo rendimiento, con el umbral | no |

**Cobertura:** 0 de 8 escenarios con agregados de la matriz y 0 con 2 semillas.

**KPIs del alcance presentes:**

| KPI | ¿Está? | Fuente o cifra |
|---|---|---|
| Tiempo y distancia de búsqueda | **no** | no hay cifras de S3 |
| CO₂ | **no** | no hay cifras de S3 |
| Falsas liberaciones por 100 sesiones | sí | `salidas_kpi/` de Freddy |
| Retardo de cierre | sí | `salidas_kpi/` de Freddy |
| Error de facturación | sí | `salidas_kpi/` de Freddy |
| Precisión del mapa | sí | `salidas_kpi/` de Freddy |

**Cifras principales al 50 %** (Freddy, umbral, semilla 1, sin guiado; para comparar el próximo domingo):

| Indicador | Valor |
|---|---|
| Búsqueda | **sin dato** (el último dato es de S2: 11,3 min con app frente a 10,8 min sin app) |
| Falsas liberaciones, 900 s | 100,0 por 100 (39/39) |
| Falsas liberaciones, 3600 s | 91,1 por 100 (246/270) |
| Retardo de cierre, 3600 s | mediana 21,5 s; p90 260 s |
| Error medio de facturación | −0,12 USD |
| Precisión del mapa (solo app) | 1,00 |
| Precisión del mapa (total) | 0,82 en 900 s; 0,62 en 3600 s |
| Rejilla de robustez | 97,4–100 falsas por 100, saturada por el umbral |

### Informativo

| Comprobación | Resultado |
|---|---|
| Latencia de `ia/inferencia.py` < 5 ms | No se pudo volver a correr: `python -m ia.bench_inferencia` necesita `geolife_etiquetado.parquet` (sin versionar). El último benchmark versionado (`ia/reportes/bench_inferencia.json`) da p95 de 1,74 ms individual y 0,35 ms por ventana en lote: cumple. |
| `npx tsc --noEmit` en `proyecto/app/` | sin errores (`npm ci` y luego `tsc`; `node_modules/` se borró después) |
| `proyecto/informe/pablo.md` | existe: 9 secciones más "Preguntas abiertas para S4" y "Referencias", con 4 `[PENDIENTE]` en la Sección 8 |

## Pedidos cruzados

### De las bitácoras de S3

| De | Para | Pedido | Sesión |
|---|---|---|---|
| Freddy | Tyrone | Usar `KPIsSistema(controlador, nucleo, intervalo_mapa_s=60)` y las claves de `resumen()` en el ejecutor. Con `duracion_s` corta, el retardo y la facturación salen NaN | S3-1 |
| Freddy | Pablo | Publicar `rf_v1.joblib` o explicar cómo regenerarlo (hoy, 100 % de fallback al umbral) | S3-1, S3-2 |
| Freddy | Tyrone [Plan] | Aprobar v1.2: `/sim/kpi`, `timeout_sin_senal`, `sin_senal`, espejo y `Salud.ts` (**aplicado hoy**) | S3-1, S3-2, S3-3 |
| Freddy | Tyrone | Usar `--libsumo` en el ejecutor, con un proceso por corrida. Para bajar el p95 habría que reducir los autos de fondo o los rerouters | S3-2 |
| Freddy | Miguel | Mostrar `timeout_sin_senal` en el recibo. Del espejo: URLs, claves de §7, `recibo` dentro de `espejo`, cierres 4404/1000, latido de 2 s y `Salud.ts` | S3-2, S3-3 |
| Freddy | Tyrone | `espejos` ya va en el snapshot. `param destino` trae `"lat,lon"`; el nombre está en `destino_nombre` | S3-3 |
| Freddy | Tyrone [VPS] | Redeploy de `esert-demo` tras la unificación y comprobar `/salud.ts`; confirmar `ESERT_TOKEN_SIM` y el volumen `/data`; 10–15 min de `correr_kpis --publicar` con `espejo.seguir`; compartir logs y CPU/RAM | S3-3 |
| Freddy | Pablo | Qué umbral de confianza usar para mostrar "detectando…" | S3-3 |
| Pablo | Freddy | Usar `clasificar(ventana, previo=None)` y `clasificar_lote` en cada paso (el modelo ocupa unos 100 MB y tarda unos segundos en cargar). k = 1 con RF y un parámetro de suavizado en el controlador. Revisar `REGRESANDO → A_PIE` en `traci/estados.py`, que deja sin cerrar alrededor del 97 % de las sesiones | S3-1, S3-2 |
| Pablo | Miguel | `precision_max_m` = 50 m | S3-1 |
| Pablo | Tyrone [Plan] | `CONTRATO.md` §2: documentar `previo` y `clasificar_lote`. §3: aclarar si existe `REGRESANDO → A_PIE` | S3-1, S3-2 |
| Pablo | Tyrone | k = 1 en la corrida final. Confirmar las cifras `[PENDIENTE]` de `hallazgos.md`. [Plan] Incluir el commit `f9e6872` de S2-3, que sigue solo en `origin/pablo/s2` | S3-2, S3-3 |
| Pablo | Freddy, Miguel | Mismo formato de trazabilidad: `<!-- fuente: archivo -->` y un comprobador de cifras | S3-3 |

### De S1 y S2 que siguen abiertos

- **Miguel → Freddy:** `/pagos/*` y `RECARGA_MINIMA` en el contrato (no entró en v1.2).
- **Miguel → Tyrone [Plan]:** `.env.example` → `.env.ejemplo` en `sesion-2.md`.
- **Miguel → Todos:** grabación con un iPhone físico.
- **Miguel:** S2-3 (espejo) y `resumen_S2_Miguel.pdf`. Además, toda S3 sin push.
- **Freddy → Pablo:** `clasificar` con los modelos de `comun.esquemas`. Sigue con `TypedDict`.
- **Freddy → Tyrone [Plan]:** `pyproj` en `CLAUDE.md`. El criterio de peatones de 30 min.
- **Tyrone [Plan]:** `kpis_base.json` en `salidas/`, que rompe el test del visor en un clon limpio.
- **Tyrone → Miguel:** `calles_sert.yaml` frente a la ordenanza.

### Pedidos nuevos que deja la unificación (para S4)

- **@Freddy:** añadir `httpx` (y lo que usa de `backend`) a `traci/requirements.txt`. Ya se pidió en S2 y sigue igual.
- **@Pablo:**
  - añadir `hypothesis` y `pydantic` a `ia/requirements.txt`;
  - `pytest.skip` en los tests que necesitan `rf_v1.joblib` o los parquet;
  - publicar el modelo final de S4 de forma accesible, porque `rf_v1.joblib` no está en ningún sitio que la unificación o Freddy puedan usar.
- **@Tyrone:** subir `tyrone/s3` (ejecutor de experimentos, agregados y figuras) o rehacerlo en S4, y atender el pedido `[VPS]` de Freddy.
- **@Miguel:** subir `miguel/s3` (cierre automático con recibo y `timeout_sin_senal`).

## Riesgos para S4 (semana final; plazo real: sábado 14 a las 23:59)

1. **Experimentos y figuras finales (Tyrone).** Hoy no hay **ningún** agregado de la matriz penetración × clasificador × semillas, ni cifras de búsqueda o CO₂ de S3, ni figuras finales. `tyrone/s3` no existe.
   - La corrida final (S4-2) depende del modelo congelado de Pablo. Hay que hacerla con el código de `main` de hoy (guiado corregido en S3-3, `--libsumo`).
   - **Es el riesgo principal:** sin ella, el informe no tiene resultados.
2. **Modelo final congelado (Pablo S4-1).** Está hecho en `origin/pablo/s4` (`rf_final`), pero `rf_v1.joblib` nunca llegó a git ni a Freddy. Todas las cifras de falsas liberaciones (91–100 por 100) son del umbral.
   - Si el `.joblib` final no se puede usar en `van3twin`, la corrida final volverá a caer al umbral.
3. **App (Miguel).** No hay `miguel/s3`: falta el cierre automático con recibo en la app, el consumo del `WS /ws/espejo` y el ensayo con el teléfono espejo contra el VPS. También el video de plan B; no hay pruebas de campo, todo es simulado.
4. **Demo en un comando (Tyrone S4-1).** Necesita el redeploy de `esert-demo` con `main` de hoy (S3-3) y la prueba en línea del espejo que dejó pendiente Freddy (`[VPS]`).
5. **Pruebas e2e (Freddy S4-1)** y reproducibilidad. `traci` e `ia` no pasan en un entorno limpio por dependencias que faltan en `requirements.txt` y por datos sin versionar. En esta máquina no hubo SUMO para comprobar nada de punta a punta.
6. **Informe (S4-3).** Ya están la sección de Pablo y su integración en `pablo/s4` (S4-3 `parcial`). Faltan las secciones de Tyrone, Freddy y Miguel, y las cifras `[PENDIENTE]` de Tyrone.
