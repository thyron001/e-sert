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
