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

## Sesión 2 · Ajuste de hiperparámetros, importancia y suavizado temporal (rf_v1)

Se entrenó el modelo Random Forest v1 con RandomizedSearchCV (15 iteraciones sobre 50k
ventanas submuestreadas) y validación GroupKFold(3) sobre 537k ventanas. Los mejores
hiperparámetros: n_estimators=200, max_depth=20, min_samples_leaf=3, max_features=sqrt,
class_weight=balanced.

Se analizó la importancia por permutación: `desplazamiento_neto` domina (0.3514), seguido
de `rectitud` (0.0171). Se implementó suavizado temporal con histéresis k=1 que reduce 61.9%
los cambios espurios sin pérdida significativa de F1.

**Métricas de validación cruzada (macro-F1):**
- RF v1: 0.9259 ± 0.0219
- Umbral: 0.7265 ± 0.0746

**Suavizado elegido:** histéresis k=1 (reducción 61.9%, delta_F1 = -0.0003)

**Tests:** 25/25 pasan.

![Matriz de confusión](evidencias/s2_matriz-confusion.png)

![Importancia de features](evidencias/s2_importancia.png)

![Suavizado temporal](evidencias/s2_suavizado.png)

## Sesión 3 · Evaluación de generalización con usuarios no vistos y escenarios difíciles de SUMO

Se evaluó el clasificador RF v1 sobre 294,579 ventanas de 10 usuarios de GeoLife nunca vistos
en entrenamiento, midiendo macro-F1 con intervalos de confianza al 95% por bootstrap agrupado
(1,000 remuestreos por usuario). El RF obtiene macro-F1 = 0.8743 [0.821, 0.947], superando
significativamente al umbral (0.6983, Δ = +0.185, IC [+0.158, +0.226]).

La brecha de generalización es de 5.2 puntos respecto a la validación cruzada de S2-2
(0.9259 -> 0.8743), esperable con usuarios nuevos. La tasa vehiculo->a_pie (falsas
liberaciones) es del 24.3% para el RF, concentrada en vehículos que circulan a menos de
8 km/h por congestión.

Los escenarios difíciles de SUMO (tráfico lento, peatón rápido, barrido de σ GPS) no se
generaron porque el contenedor van3twin no estaba corriendo. El script está listo para
ejecutarse. La sesión queda **parcial** (4/7 criterios cumplidos).

**Métricas principales (GeoLife prueba):**

| Sistema | macro-F1 | IC 95% | Tasa veh->a_pie |
|---------|----------|--------|-----------------|
| RF v1 | 0.8743 | [0.821, 0.947] | 24.3% |
| RF+suav | 0.8724 | [0.819, 0.944] | 24.1% |
| Umbral | 0.6983 | [0.619, 0.756] | 27.2% |

**Tests:** 11/11 pasan.

![Umbral vs RF por fuente](evidencias/s3_umbral-vs-rf-por-fuente.png)

![Curvas sigma](evidencias/s3_curvas-sigma.png)

![Tráfico lento](evidencias/s3_trafico-lento.png)
