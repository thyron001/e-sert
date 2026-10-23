**Estado:** fusionado en main

# S1 · Resultado de la unificación

Ejecutada el **viernes 2026-10-23** en la computadora de Tyrone, a su pedido, en lugar de la
tarea programada del domingo 25. Todas las ramas ya tenían sus tres sesiones con push. Si
alguien sube commits nuevos antes del plazo (sábado 24, 23:59), habrá que reejecutarla en
`unificacion/s1-r<HHMM>`.

Rama de trabajo: `unificacion/s1`, creada desde `origin/main` (`715751b`).

## Ramas por persona

| Persona | Rama | Commits | Último commit | Tardía | Sesiones hechas / parciales / bloqueadas | Evidencias encontradas / declaradas | Criterios | PDF semanal |
|---|---|---|---|---|---|---|---|---|
| Tyrone | `origin/tyrone/s1` | 3 | 2026-10-22T01:53:47-05:00 | no | 3 / 0 / 0 | 4 / 4 (+3 extra) | 17 / 17 | sí |
| Freddy | `origin/freddy/s1` | 3 | 2026-10-22T17:56:24-05:00 | no | 3 / 0 / 0 | 4 / 4 | 12 / 12 | sí |
| Pablo | `origin/pablo/s1` | 3 | 2026-10-22T11:55:18-05:00 | no | 3 / 0 / 0 | 5 / 5 | 14 / 14 | sí |
| Miguel | `origin/miguel/s1` | 4 | 2026-10-22T23:00:37-05:00 | no | 2 / 1 / 0 | 5 / 5 (+3 extra) | 13 / 14 | sí |

- **Sin push:** ninguna persona. **Tardías:** ninguna.
- Miguel, sesión 2 `parcial` (3/4): el criterio de iOS solo se probó en el simulador, sin un
  iPhone físico.
- No hay archivos de más de 50 MB ni secretos en ninguna rama. El mayor es
  `resumen_S1_Miguel.pdf`, con 12,3 MB.

## Conflictos

Ninguno. Las cuatro fusiones `--no-ff` (en orden Freddy, Tyrone, Pablo y Miguel) entraron
limpias.

## Archivos fuera de carpeta y cambios a la planificación descartados

- **Archivos fuera de carpeta revertidos:** ninguno. Cada rama solo toca `semanas/S1/<Nombre>/`
  y `bitacoras/<nombre>.md`.
- **Cambios a la planificación descartados:** ninguno. Nadie modificó sus `sesion-*.md` ni
  otros archivos de planificación.

## Copia a `proyecto/`

- Se copiaron **192 archivos** versionados, todos dentro de los módulos de su dueño:
  - Tyrone: `sumo/`;
  - Freddy: `comun/`, `backend/` y `traci/`;
  - Pablo: `ia/`;
  - Miguel: `app/` y `datos/`.
- **Archivos no copiados:**

  | Persona | Ruta | Motivo |
  |---|---|---|
  | Freddy | `comun/CONTRATO.propuesto.md` | Sigue su propio flujo: se aplicó a `docs/CONTRATO.md` |
  | Todos | `codigo/.gitkeep` | Marcador de carpeta, fuera de cualquier módulo |

- **Posibles eliminaciones, no aplicadas:** los `.gitkeep` de `proyecto/app`, `backend`, `ia`,
  `kpis`, `sumo`, `traci` y `visor`, que no están en las copias. Son marcadores sin contenido.
- **Ajuste posterior a la copia** (decisión de Tyrone durante la unificación): en
  `proyecto/comun/tests/test_esquemas.py`, si no existe `comun/CONTRATO.propuesto.md`, los
  tests leen ahora `docs/CONTRATO.md`. Sin ese cambio, 2 tests fallaban en `proyecto/` porque
  la propuesta no se copia allí. La copia de Freddy en `semanas/` sigue igual.

## Verificación independiente

Un subagente sin contexto verificó todas las afirmaciones de este archivo. Hubo 2 vueltas.
En la primera encontró que el bloque de Estado de `docs/CONTRATO.md` había perdido el párrafo
"Versión del contrato: `1` … manda `esquemas.py`" (ya restaurado) y un comando mal escrito en
la tabla de tests (ya corregido). Todo lo demás cumple.

## Tests

Desde `proyecto/`: `PYTHONPATH=. <m>/.venv/bin/python -m pytest -q <m>/tests`.

| Módulo | Comando | Resultado | Duración |
|---|---|---|---|
| `comun` | ídem con `comun/.venv` y `comun/tests` | 163 pasados | 0,4 s |
| `backend` | ídem con `backend/.venv` y `backend/tests` | 63 pasados | 11,2 s |
| `traci` | ídem con `traci/.venv` y `traci/tests` | 14 pasados, 3 saltados | 1,7 s |
| `ia` | ídem con `ia/.venv` y `ia/tests` | 35 pasados (6 avisos) | 2,4 s |
| `sumo`, `datos` | — | sin tests | — |
| `app` | — | no forma parte de la verificación (pytest solo cubre Python) | — |

- **SUMO** (contenedor `van3twin`, 1.12): `sumo -c centro_base.sumocfg --end 60 --no-step-log`,
  con las salidas a `/dev/null`, terminó con código 0.
- **Total:** 275 pasados, 3 saltados y 0 fallados. **Las pruebas pasan.**

En la primera vuelta, `comun` dio 2 fallos (`test_tarifa_carga_y_coincide_con_contrato` y
`test_contrato_documenta_todos_los_codigos`), por el `FileNotFoundError` de la propuesta
explicado arriba. Con una copia temporal del contrato congelado pasaban los 163, así que el
contenido del contrato es coherente con `esquemas.py` y `tarifa.json`.

### Cimientos para S2 en `proyecto/`

| Archivo | Estado |
|---|---|
| `sumo/red/centro.net.xml` | OK |
| `sumo/parqueos/puestos.csv` | OK (610 puestos) |
| `comun/esquemas.py` y `comun/esquemas.ts` | OK |
| `traci/trazas/sumo_semilla1_muestra.csv` | OK |
| `ia/inferencia.py` | OK |
| `app/package.json` | OK |
| `datos/PROTOCOLO_CASERO.md` | OK |
| `ia/modelos/rf_v0.joblib` | **falta** (`clasificar` cae al umbral) |

## Contrato

**v1 aplicado y congelado.** `docs/CONTRATO.md` es ahora la propuesta de Freddy, con el
encabezado "Contrato de interfaces (v1, congelado el 2026-10-23 en la unificación de S1)". Está
completo, no remite al v0 y trae la sección "Cambios respecto a v0".

Incoherencias encontradas (no impiden congelarlo; el v1 manda):

1. **`puestos.csv`:** columnas `puesto_id,edge,lane,calle,capacidad,lat,lon,x,y`, y los 610 IDs
   cumplen `^pa_.+_\d+$`. Coherente con §1. El contrato no fija las columnas del CSV, solo lo
   que devuelve `GET /puestos`.
2. **Trazas:** la muestra de Freddy (`usuario_id,t,lat,lon,precision_m,velocidad_mps,modo_real,lat_real,lon_real,velocidad_real_mps,caso`)
   y la de Pablo (`…,modo_real,segmento_id,fuente`) traen las 7 columnas primero, como pide
   §8. Las extra están permitidas, pero la columna `fuente` de Pablo es la fuente del dato
   (GeoLife) y comparte nombre con `FuenteModo` (`rf`/`umbral`), lo que puede confundir.
3. **`ia/inferencia.py`:** la firma `clasificar(ventana: list[PuntoGPS]) -> ResultadoModo`, los
   `modo` ∈ {a_pie, quieto, vehiculo} y las `fuente` ∈ {rf, umbral} coinciden con §2. Pero
   define sus propios `TypedDict` (`modo: str`, `fuente: str`) en lugar de importar
   `from comun.esquemas import PuntoGPS, ResultadoModo`, como dice §2. Además, el modelo
   `rf_v0.joblib` no está en git.
4. **Cliente API de la app (`app/src/api/tipos.ts`, `cliente.ts`):** `tipos.ts` se escribió a
   mano desde el v0 y no es una copia de `comun/esquemas.ts`.
   - `CuerpoError` no tiene `detalle` (`DetalleError`).
   - Espera `cerrar → {sesion_id, minutos_cobrados, debitado}`, sin `minutos_reales` ni
     `saldo`.
   - `POST /sesiones` no envía `ts`/`t_sim` (son opcionales).
   - No usa `GET /salud`, `GET /tarifa` ni `GET /espejo/candidatos`: el espejo funciona con un
     mock.
   - Las rutas y el prefijo `/api/v1`, con `X-Contrato-Version: 1`, sí coinciden.
5. **Tarifa:** `comun/tarifa.json` coincide con la tarifa SERT que verificó Miguel (USD 0,25 por
   media hora, Art. 36; máximo 120 min). La fracción de 5 min, el cobro mínimo y la recarga
   mínima son reglas de la app. Miguel propone añadir `tolerancia_ingreso_min: 10` (Art. 10),
   que queda para un `CONTRATO.propuesto.md` de S2.

## Pedidos cruzados (de las bitácoras de S1)

| De | Para | Pedido | Sesión |
|---|---|---|---|
| Tyrone | Freddy | Red en `proyecto/sumo/red/`: proyección UTM 17 y `convertGeo`; ojo con las islas peatonales | S1-1 |
| Tyrone | Pablo | Misma red y proyección para las trazas de SUMO | S1-1 |
| Tyrone | Miguel | Verificar `calles_sert.yaml` contra la ordenanza SERT | S1-2 |
| Tyrone | Freddy | `puestos.csv` es la fuente de puestos; el sufijo `_0` no es el carril (usar `lane`) | S1-2 |
| Tyrone | Freddy | `param con_app` como interruptor; IDs `busca_*`, `paso_*` y `fondo_*`; `destinos.csv` para el espejo | S1-3 |
| Tyrone | Pablo | Los `busca_*` sirven para los casos difíciles de tráfico lento | S1-3 |
| Freddy | Tyrone | El visor usa `/ws/estado?rol=visor` y compara `snapshot` con `verdad` | S1-1 |
| Freddy | Tyrone [VPS] | Definir `SIM_TOKEN` en el `.env` de Dokploy | S1-1 |
| Freddy | Pablo | Firma de `clasificar` con los modelos de `comun.esquemas`; `segmento_id` como columna extra | S1-1 |
| Freddy | Miguel | Reemplazar `src/api/tipos.ts` por `comun/esquemas.ts` (lista de cambios del v1) | S1-1 |
| Freddy | Tyrone | Con `puestos.csv` en `proyecto/`, el núcleo lo carga solo (ya ocurre) | S1-2 |
| Freddy | Tyrone | El sobrecobro de la tarjeta SERT es $0,101 por estadía (19,3 %), para la exposición | S1-2 |
| Freddy | Miguel | Confirmar que la tarjeta SERT es de bloques de 30 min | S1-2 |
| Freddy | Pablo | Trazas de SUMO en `proyecto/traci/trazas/` (muestra en git; las completas se regeneran) | S1-3 |
| Freddy | Tyrone | `centro_base.sumocfg` unificado; atributo "con app"; peatones al estacionar; `--output-prefix` por semilla | S1-3 |
| Freddy | Tyrone [Plan] | `CLAUDE.md`: el contenedor no trae `pyproj`; listarlo entre las dependencias a instalar | S1-3 |
| Pablo | Freddy | `from ia.inferencia import clasificar`; variables `ESERT_MODELO` y `ESERT_CLASIFICADOR` | S1-3 |
| Pablo | Miguel | Grabaciones caseras opcionales (~10 min por clase) | S1-3 |
| Miguel | Freddy | `esquemas.ts`, `tarifa.json`; campos de `GET /sesiones/{id}` y `Movimiento` (resuelto en el v1) | S1-1 |
| Miguel | Tyrone [Plan] | `herramientas/explicacion_pdf.py`: no transformar `<code>` dentro de `<td>` | S1-1 |
| Miguel | Todos | Instalar Expo Go (SDK 58) | S1-2 |
| Miguel | Pablo | Grabación casera de Android en `datos/grabaciones/` como validación extra | S1-2 |
| Miguel | Todos | Una grabación corta con un iPhone físico para cerrar el criterio 1 de S1-2 | S1-2 |
| Miguel | Freddy | Tarifa sin cambios; añadir `tolerancia_ingreso_min: 10`; ¿`saldo_bajo` usa `saldo − costo` o `saldo − max(retención, costo)`? | S1-3 |

### Pedidos nuevos que deja la unificación (para S2)

- **@Miguel:** reemplazar `app/src/api/tipos.ts` por `comun/esquemas.ts` (incoherencia 4).
- **@Pablo:**
  - importar `PuntoGPS` y `ResultadoModo` desde `comun.esquemas` (incoherencia 3);
  - subir `rf_v0.joblib` (no lo excluye el `.gitignore`) o documentar cómo regenerarlo;
  - considerar renombrar la columna extra `fuente` del CSV de GeoLife.
- **@Freddy:**
  - adoptar en su copia de S2 el ajuste de `comun/tests/test_esquemas.py` que lee
    `docs/CONTRATO.md`;
  - responder la duda de `saldo_bajo` y valorar `tolerancia_ingreso_min` en el próximo
    `CONTRATO.propuesto.md`.

## Riesgos para S2

| Dependencia (`docs/PLAN.md`) | Estado en `proyecto/` | Riesgo y mock |
|---|---|---|
| Red y puestos de Tyrone → Freddy (S2-2) y Pablo (S2-1) | `sumo/red/centro.net.xml`, `sumo/parqueos/puestos.csv` y `sumo/centro_base.sumocfg` presentes; SUMO corre | Bajo |
| Trazas de SUMO de Freddy → Pablo (S2-1) | Solo la muestra de 5000 filas (las completas, de ~40 MB, se regeneran en el contenedor con `traci.generar_trazas`) | Bajo: Pablo debe regenerarlas o usar la muestra |
| `inferencia.py` de Pablo → Freddy (S2-2) | Presente, pero sin `rf_v0.joblib` | **Medio:** sin el modelo, `clasificar` siempre devuelve `fuente: "umbral"`. Mock natural: el umbral, hasta que Pablo suba o regenere el modelo |
| API de Freddy → Miguel (S2) y visor de Tyrone (S2-2) | `backend/nucleo/` (billetera, tarifa y sesiones) con 63 tests; todavía no hay rutas FastAPI | **Medio:** la API llega en S2-1. Mientras tanto, Miguel usa `src/api/mock.ts` y el visor, un mock del WebSocket `/ws/estado` |
| Grabaciones caseras de Miguel → Pablo (S2-3) | Hay una de Android anonimizada | Opcional, no es riesgo |

**Riesgo principal:** que el cliente de la app siga con los tipos del v0 mientras el backend
implementa el v1. Hay que hacer el reemplazo por `comun/esquemas.ts` al inicio de S2.
