# S3 · Freddy 🍅: resumen semanal

## Sesión 1 · 2026-11-05 · KPIs de sistema: falsas liberaciones, retardo de cierre, facturación y mapa

Los cuatro KPIs que dependen del controlador se miden dentro de la simulación:
- `traci/verdad.py` obtiene la verdad de SUMO a partir del bit de parking de la suscripción;
- `traci/kpis_sistema.py` entrega `KPIsSistema.resumen()`, `detalle_sesiones()` y `serie_mapa()`, la interfaz acordada con Tyrone;
- `traci/correr_kpis.py` corre `p{pen}_{clf}_s{sem}` sobre los escenarios unificados de Tyrone, lo que reemplaza el mock del 50 % de S2;
- se publica `kpi` por la ruta nueva `POST /api/v1/sim/kpi`, y `verdad` ya lleva datos reales.

Cifras con 50 % de autos con app y semilla 1:

| Medida | Resultado |
|---|---|
| Precisión del mapa solo con app (900 s) | 1,00 |
| Precisión del mapa total (900 s) | 0,82 |
| Falsas liberaciones por 100 sesiones | 100 en 900 s; 91 en 3600 s |
| Retardo de cierre, mediana (3600 s) | 21,5 s |
| Error de facturación medio (3600 s) | −0,12 USD |
| Sobrecosto de los KPIs por paso | 1,7–3,6 % |

La corrida `rf` usó en realidad el umbral, porque falta `rf_v1.joblib`.

![KPIs de sistema](evidencias/s1_kpis-sistema.png)

Explicación: [explicaciones/s1_explicacion.pdf](explicaciones/s1_explicacion.pdf)
