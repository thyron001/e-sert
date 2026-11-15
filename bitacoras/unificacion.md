# Bitácora de unificaciones

Una entrada por domingo, escrita por la tarea programada de las 09:00.

---

## S1 · Unificación · 2026-10-23
**Resultado:** fusionado en main (ejecutada el viernes 23 a pedido de Tyrone, no por la tarea del domingo)
**Ramas:** tyrone (3 commits), freddy (3), pablo (3), miguel (4); tardías: ninguna; sin push: ninguna
**Conflictos:** ninguno · **No copiados:** `comun/CONTRATO.propuesto.md` de Freddy (flujo del contrato) · **Contrato:** v1 congelado
**Tests:** 275 pasados, 3 saltados, 0 fallados (comun 163, backend 63, traci 14+3 saltados, ia 35); 2 tests de comun ajustados para leer `docs/CONTRATO.md` en `proyecto/` (decisión de Tyrone) · **SUMO:** ok
**Verificador:** 2 vueltas; restauró un párrafo del encabezado del contrato y un comando del resultado
**Riesgos para S2:** la app sigue con tipos del v0 (reemplazar por `comun/esquemas.ts`); falta `ia/modelos/rf_v0.joblib` (`clasificar` cae al umbral); la API REST de Freddy todavía no existe (mocks en la app y el visor hasta S2-1)

## S2 · Adelanto del backend para la demo · 2026-10-28
**Pedido por:** Tyrone, para probar Payphone en `esert-demo` (Dokploy) antes del domingo.
**Qué se hizo:**
- `proyecto/backend/` = `semanas/S2/Freddy/codigo/backend/` de `origin/freddy/s2` (9e3f230), copiado sin fusionar la rama.
- `proyecto/backend/pagos/` = `semanas/S2/Miguel/codigo/backend/pagos/` de `origin/miguel/s2` (19dc14e).
- `httpx` añadido a `requirements-servidor.txt` y `requirements.txt` del backend (pedido de Miguel a Freddy): sin él, pagos no se monta.
**Verificación:** pytest 132/132 (102 backend + 30 pagos); `docker build -f proyecto/backend/Dockerfile .` construye; en modo mock, `/salud` 200 y preparar → aprobar → billetera +$5.
**Para la unificación de S2:** el paso 4 vuelve a copiar estos módulos desde las ramas y sobrescribe esta copia. Si Freddy no agregó `httpx` a su `requirements-servidor.txt`, mantener esa línea.

## S2 · Unificación · 2026-11-01
**Resultado:** fusionado en main
**Ramas:** tyrone (4 commits), freddy (4), pablo (3), miguel (3); tardías: ninguna; sin push: ninguno
**Conflictos:** `bitacoras/pablo.md` (versión de main) · **No copiados:** `comun/CONTRATO.propuesto.md` (Freddy); `kpis/salidas/` de Tyrone y `.env.ejemplo`/`.env.example` por regla · **Contrato:** v1.1 aplicado (alias `/interno/snapshot`, token Bearer/`ESERT_TOKEN_SIM`, `/salud` en la raíz, `?verdad`, semántica de `/guia`)
**Tests:** entorno limpio: comun 163, backend 132, kpis 14 ok; traci 7 fallos, ia 3 errores, visor 1 fallo (dependencia `httpx`, escenario y parquet sin versionar, `kpis_base.json` en `salidas/`); con el entorno completado: 0 fallos de lógica, 3 de ia no verificables · **SUMO:** no verificable (sin `van3twin`) · **Integración backend↔TraCI↔app:** parcial (backend↔app ok en 12/12 sub-pasos; el controlador TraCI no es verificable sin SUMO)
**Riesgos para S3:** falta `WS /ws/espejo` y Miguel no hizo S2-3; el guiado no mejora la búsqueda y hay 62 falsas liberaciones por cada 100; `rf_v1.joblib` fuera de git (`clasificar` cae al umbral)
**Verificador:** 1 vuelta; todas las afirmaciones comprobables cumplen. Se corrigieron 3 imprecisiones menores (parámetro `?verdad` del visor, línea de estado v1 del contrato, plantillas `.env` con valores por defecto)

## S3 · Unificación · 2026-11-08
**Resultado:** fusionado en main
**Ramas:** tyrone (sin push), freddy (3 commits), pablo (3), miguel (sin push); tardías: ninguna; sin push: tyrone, miguel
**Conflictos:** `bitacoras/pablo.md` (versión de main) · **No copiados:** `comun/CONTRATO.propuesto.md` (Freddy); `backend/.env.ejemplo` por regla · **Contrato:** v1.2 aplicado (`/sim/kpi`, `timeout_sin_senal`, `sin_senal`, bloque `espejo` y `RespuestaSnapshot`, reglas del §7, `Salud.ts`)
**Tests:** entorno limpio: comun 169, backend 148, kpis 14 ok; traci 3 errores (`httpx`), ia 2 errores (`hypothesis`, `pydantic`), visor 1 fallo (`kpis_base.json`); con el entorno completado: traci 71, visor 8, ia 139 ok y 13 no verificables (`rf_v1.joblib` y parquet de GeoLife sin versionar); 0 fallos de lógica · **SUMO:** no verificable (sin `van3twin`) · **Experimentos:** 0/8 combinaciones con agregados (Tyrone sin push); búsqueda al 50 %: sin dato; falsas liberaciones al 50 % (umbral, Freddy): 100,0 por 100 en 900 s y 91,1 por 100 en 3600 s
**Riesgos para S4:** no existe la matriz de experimentos ni las figuras finales (Tyrone); `rf_v1.joblib` nunca llegó a git, así que todo cae al umbral; la app de Miguel no tiene S3 (cierre con recibo, espejo); falta redeploy del VPS con S3-3
**Verificador:** 1 vuelta; cumplen todas las afirmaciones comprobables. Se corrigieron 4 imprecisiones: 9 marcadores `[PENDIENTE]` (no 4) en `informe/pablo.md`, el título de sección cambiado en el contrato, la fuente de las cifras de 3600 s (`ejemplo_p50_rf_s1_3600.json`, umbral usado) y la columna de archivos copiables. Se añadió el pedido a Pablo por la ruta del parquet en `ia/datos/ventanas_prueba.py`

## S4 · Unificación final · 2026-11-15
**Resultado:** no fusionado en main: falla 1 pytest de `informe/` (`RAIZ_REPO = AQUI.parents[4]` en `construir_informe.py`); sin tag (además, `verificar_informe.py` sale con 1 por 30 `[PENDIENTE]`). Todo queda en `unificacion/s4`.
**Ramas:** tyrone (3 commits), freddy (6), pablo (4), miguel (8); tardías: miguel (2 commits el domingo 00:06 y 00:16, incluidos); sin push: ninguna
**Conflictos:** `bitacoras/freddy.md` (versión de main) · **Revertidos:** `semanas/S2/Freddy/{RESUMEN.md,estado.json}` (Freddy) y 175 archivos añadidos en `semanas/S3/Tyrone/codigo/` (Tyrone) · **No copiados:** `comun/CONTRATO.propuesto.md`, `informe/freddy_cifras.py`, `informe/datos/freddy/` (Freddy); `informe/tyrone.cifras.json`, `informe/tyrone.plantilla.md` (Tyrone); `.env.ejemplo`/`.env.example` por regla · **Contrato:** v1.3 final (editorial: `ts?` en `GET /salud`); `verificar_contrato_api.py` sale con 1 por `/pagos/*` fuera de §4.3
**Tests:** entorno limpio: comun 169 y visor 11 ok; backend, traci, ia y kpis fallan en colección por dependencias no declaradas; con el entorno completado: backend 244, traci 74, kpis 23 e ia 164 ok (3 no verificables por el parquet de GeoLife sin versionar); informe 1 fallo real (`test_genera_pdf_sin_pandoc`) · **Modelo:** hash ok · **Higiene:** ok · **SUMO/e2e/demo:** no verificables (sin `van3twin`)
**Informe:** construido con fallas (PDF de 8,9 MB con las 4 secciones, generado con el script de Pablo y `--carpeta proyecto/informe`; con el comando oficial solo sale HTML; `verificar_informe.py` sale con 1 por 30 `[PENDIENTE]`)
**Riesgos para el lunes 16:** main sin S4 hasta que Tyrone fusione; cifras finales sin integrar en el resumen y las conclusiones; demo, e2e y SUMO sin verificar; token del VPS sin configurar; mapa en 0/610 en la demo guiada; video del plan B solo en Drive
