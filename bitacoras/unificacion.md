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
