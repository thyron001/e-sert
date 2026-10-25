# S2 · Pablo 🟢 · Resumen semanal

## Sesión 1 · Ventanas desde trazas de SUMO y ruido GPS calibrado con literatura

Se creó la partición fija de usuarios GeoLife (20% prueba, 10 usuarios, semilla 2026) con
semillas SUMO 101–105 reservadas para escenarios difíciles en S2-3. Se implementó ruido GPS
AR(1) calibrado con valores de la literatura (σ de 3 a 15 m en cañón urbano, ρ = 0.8 a 1 Hz)
y se generaron ventanas desde trazas SUMO mock (7,982 ventanas de 3 clases).

El análisis de sensibilidad σ_entrenamiento × σ_validación con GroupKFold mostró diferencias
< 0.3% en macro-F1 entre configuraciones. Se eligió la mezcla U(3,15) por diversidad de
condiciones GPS. Se mezcló GeoLife + SUMO en `ventanas_v2.parquet` (1,650,500 ventanas)
con augmentation del 50% y prueba aparte sin aumentar (294,579 ventanas).

**Métricas de la rejilla (macro-F1 promedio):**
- σ_entr=0: 0.872 | σ_entr=3: 0.870 | σ_entr=8: 0.871 | σ_entr=15: 0.871 | σ_entr=mezcla: 0.872

**Comparación KS GeoLife vs SUMO:**
- Las distribuciones difieren significativamente (D > 0.15 en todas las features), esperado
  con trazas MOCK. Se normalizará al recibir trazas reales de Freddy.

**Tests:** 11/11 pasan (partición, ruido AR(1), no fuga, hash).

![Distribuciones de features](evidencias/s1_distribuciones-features.png)

![Sensibilidad σ](evidencias/s1_sensibilidad-sigma.png)
