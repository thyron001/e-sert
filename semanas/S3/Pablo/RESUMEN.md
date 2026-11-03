# S3 · Pablo 🟢 · Resumen semanal

## Sesión 1 · Servicio de inferencia robusto: huecos, latencia menor a 5 ms y fallback

`clasificar` ahora limpia la ventana (duplicados, NaN, precisión > 50 m, saltos imposibles,
huecos), degrada con elegancia (RF → umbral → resultado previo) y nunca lanza por datos. Para
la latencia se compiló el Random Forest de 200 árboles a arrays de numpy: mismas predicciones
que sklearn, pero ~14 veces más rápido.

| Medida (10 000 ventanas) | p50 | p95 | p99 |
|---|---|---|---|
| `clasificar` individual (ms) | 1,23 | 1,56 | 1,84 |
| `clasificar_lote` (ms por ventana) | 0,313 | 0,326 | 0,334 |

**Tests:** 49/49 en `test_inferencia.py` (300 ejemplos de hypothesis por propiedad).

![](evidencias/s1_latencia-inferencia.png)
