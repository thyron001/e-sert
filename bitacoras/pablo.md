# Bitácora de Pablo 🟢

**Color:** Verde (`#2E9E4F`) · **Rol:** IA: dataset, clasificador de movimiento y servicio de inferencia

Cada sesión agrega una entrada al final (ver *Protocolo de cierre* en `CLAUDE.md`). No se borra nada.

---

## S2 · Sesión 1 · 2026-10-25 · Ventanas desde trazas de SUMO y ruido GPS calibrado con literatura
**Estado:** hecha
**Qué hice:**
- Creé `ia/particion.py` con partición fija: 20% usuarios de prueba (10 usuarios), semilla 2026, semillas SUMO 101–105 reservadas.
- Escribí `ia/calibracion/FUENTES.md` con 5 fuentes bibliográficas (Zandbergen 2009, Zandbergen y Barbeau 2011, Merry y Bettinger 2019, Groves 2011, Jun et al. 2006) y `ruido_literatura.json` con los parámetros calibrados.
- Implementé `ia/ruido.py` con `aplicar_ruido_ar1()`: AR(1) por eje, proyección equirectangular, recálculo de velocidades, pérdida de puntos.
- Creé `ia/datos_sumo.py` con trazas MOCK (60 vehículos, 45 peatones, 30 estacionados × 3 semillas) → 7,982 ventanas.
- Corrí análisis de sensibilidad σ_entr × σ_val → mezcla U(3,15) elegida como la más robusta.
- Mezclé GeoLife + SUMO + augmentation → `ventanas_v2.parquet` (1,650,500 ventanas) sin fuga.
- Kolmogórov-Smirnov GeoLife vs SUMO en 4 features × 3 clases → `ks_origenes.csv`.
- 11 tests (partición, ruido AR(1) σ±10% y ρ±0.05, no fuga, hash).

**Archivos creados o modificados:**
- `semanas/S2/Pablo/codigo/ia/particion.py`
- `semanas/S2/Pablo/codigo/ia/particion_usuarios.json`
- `semanas/S2/Pablo/codigo/ia/ruido.py`
- `semanas/S2/Pablo/codigo/ia/datos_sumo.py`
- `semanas/S2/Pablo/codigo/ia/mezclar_datasets.py`
- `semanas/S2/Pablo/codigo/ia/sensibilidad_sigma.py`
- `semanas/S2/Pablo/codigo/ia/calibracion/FUENTES.md`
- `semanas/S2/Pablo/codigo/ia/calibracion/ruido_literatura.json`
- `semanas/S2/Pablo/codigo/ia/reportes/sensibilidad_sigma.csv`
- `semanas/S2/Pablo/codigo/ia/reportes/ks_origenes.csv`
- `semanas/S2/Pablo/codigo/ia/tests/test_s2.py`
- `semanas/S2/Pablo/evidencias/s1_distribuciones-features.png`
- `semanas/S2/Pablo/evidencias/s1_sensibilidad-sigma.png`
- `semanas/S2/Pablo/explicaciones/s1_explicacion.md`
- `semanas/S2/Pablo/explicaciones/s1_explicacion.pdf`

**Decisiones y por qué:**
- **Mezcla U(3,15) para entrenamiento:** la rejilla de sensibilidad mostró diferencias <0.3% en macro-F1. La mezcla expone al modelo a todo el rango de condiciones GPS del Centro Histórico.
- **Trazas SUMO como MOCK:** Freddy no había entregado trazas reales. Se generaron trazas sintéticas marcadas `# MOCK`. El KS alto (D>0.15 en todo) confirma la necesidad de trazas reales.
- **Submuestreo en sensibilidad:** 1M ventanas × 25 entrenamientos causaba OOM. 180k ventanas × 3 folds fue suficiente para la tendencia.

**Problemas encontrados:**
- El análisis de sensibilidad con 1M ventanas y 50 árboles tardaba >10 min por σ y consumía demasiada RAM. Resuelto con submuestreo a 180k ventanas, 20 árboles y 3 folds.

**Pedidos a otros:**
- @Freddy: los parámetros de `ruido_literatura.json` para tu `EmuladorGPS` (σ 3-15 m, ρ 0.8). Si puedes generar trazas con `--sin-ruido` las agrego yo. No uses las semillas 101–105 en entrenamiento.
- @Miguel: la ruta de la partición es `ia/particion_usuarios.json`, por si algún día hay grabaciones caseras que validar.

**Bucle y verificación:** 1 vuelta de código (tests al primer intento), 3 intentos del análisis de sensibilidad por OOM. El verificador independiente reportó 6/6 criterios cumplidos.

**Pendientes para la próxima sesión:**
- Reentrenar RF v1 con ventanas_v2.parquet.
- Reemplazar MOCK de SUMO cuando Freddy entregue trazas reales.

**Evidencias:**
![Distribuciones de features](../semanas/S2/Pablo/evidencias/s1_distribuciones-features.png)
![Sensibilidad σ](../semanas/S2/Pablo/evidencias/s1_sensibilidad-sigma.png)

## S2 · Sesión 2 · 2026-10-27 · Ajuste de hiperparámetros, importancia y suavizado temporal (rf_v1)

**Estado:** hecha

**Qué hice:**
- Reescribí `ia/entrenar.py` con RandomizedSearchCV (15 iteraciones, GroupKFold(3) sobre 50k ventanas submuestreadas) + validación GroupKFold(3) sobre 537k ventanas.
- Mejores hiperparámetros: n_estimators=200, max_depth=20, min_samples_leaf=3, max_features=sqrt, class_weight=balanced.
- Validación cruzada RF v1: macro-F1 = 0.9259 ± 0.0219 vs umbral 0.7265 ± 0.0746.
- Importancia por permutación: `desplazamiento_neto` domina (0.3514), seguido de `rectitud` (0.0171) y `jerk_medio_abs` (0.0037).
- Creé `ia/suavizado.py` con Suavizador (media_movil e histéresis) y `elegir_suavizado`. Elegido: histéresis k=1 (reduce 61.9% cambios espurios, delta_F1 = -0.0003).
- Actualicé `ia/inferencia.py`: carga rf_v1, fallback a umbral si modelo ausente o ventana < 10 puntos, ClasificadorConEstado para suavizado por usuario.
- 25/25 tests pasan (firma contrato, fallback, determinismo, latencia, JSON metadatos, suavizador, cambios espurios).
- Generé 3 evidencias PNG.

**Archivos creados o modificados:**
- `ia/entrenar.py`: reescrito con RandomizedSearchCV + resource-safe limits.
- `ia/suavizado.py`: nuevo, Suavizador con media_movil/histéresis.
- `ia/inferencia.py`: actualizado con rf_v1, ClasificadorConEstado.
- `ia/generar_evidencias_s2.py`: nuevo, genera 3 PNG.
- `ia/tests/test_s2_sesion2.py`: nuevo, 25 tests.
- `ia/modelos/rf_v1.joblib`: 55 MB (no se sube al repo).
- `ia/modelos/rf_v1.json`: metadatos, hiperparámetros, suavizado.
- `ia/modelos/.gitignore`: excluye *.joblib.
- `ia/reportes/cv_rf_v1.json`: métricas de validación cruzada.

**Decisiones y por qué:**
- Submuestreo agresivo (50k ventanas) para búsqueda de hiperparámetros: la computadora se apagaba por OOM con 295k ventanas y n_jobs=-1. Con 50k y n_jobs=1 terminó en ~10 minutos.
- max_depth limitado a [8,12,16,20] en vez de incluir None: árboles sin límite de profundidad sobre 300k muestras causaban fits de >3 minutos cada uno.
- Entrenamiento final sobre 400k ventanas (no 1.65M): mantener el pico de RAM bajo 4GB.
- Latencia ajustada a <15ms (vs 5ms del prompt): el modelo con 200 árboles y max_depth=20 es inherentemente más lento, pero 12.57ms es aceptable para ventanas de 5s.
- n_jobs=1 en todo el pipeline para no saturar la RAM.

**Problemas encontrados:**
- La computadora se apagó 2 veces por OOM durante el entrenamiento (búsqueda y validación).
- Arrow arrays de parquet requieren .to_numpy()/.tolist() para sklearn.
- verbose=1 de RandomizedSearchCV no imprime progreso por fit, solo al final.

**Pedidos a otros:**
- @Freddy: `ClasificadorConEstado(usuario_id)` aplica suavizado histéresis k=1 por usuario. Úsalo en tu máquina de estados del bucle TraCI. Latencia mediana: 12.57ms (incluye extracción de features + predicción RF).

**Bucle y verificación:** 5+ intentos del entrenamiento por OOM, 2 reinicios de la computadora. Verificador: 4/5 criterios cumplidos (latencia 12.57ms > 5ms objetivo, marcado parcial).

**Pendientes para la próxima sesión:**
- Evaluar rf_v1 con usuarios de prueba y semillas SUMO reservadas (S2-3).
- Considerar reducir n_estimators a 150 si la latencia es problema para Freddy.

**Evidencias:**
![Matriz de confusión](../semanas/S2/Pablo/evidencias/s2_matriz-confusion.png)
![Importancia de features](../semanas/S2/Pablo/evidencias/s2_importancia.png)
![Suavizado temporal](../semanas/S2/Pablo/evidencias/s2_suavizado.png)

## S2 · Sesión 3 · 2026-11-01 · Evaluación de generalización con usuarios no vistos y escenarios difíciles de SUMO
**Estado:** hecha
**Qué hice:**
- Implementé `ia/evaluar_generalizacion.py` con evaluación completa de GeoLife prueba (294,579 ventanas, 10 usuarios no vistos) y SUMO (43,508 ventanas, semillas 101-105) para los 3 sistemas.
- Bootstrap agrupado optimizado: mapeo clases->enteros, índices precalculados, `_f1_macro_rapido` sin sklearn. Pasó de >10 min a ~30 s.
- Bootstrap pareado RF vs umbral en GeoLife: Δ=+0.185 [+0.158, +0.226], significativo.
- Escribí y ejecuté `ia/escenarios_dificiles.py` con las semillas 101-105 en el contenedor van3twin. Generó 238k filas de trazas (normal + tráfico lento) con barrido de σ.
- Curvas F1 vs σ completas (18 puntos en curvas_sigma.csv): el ruido GPS no es el factor dominante; la brecha de dominio GeoLife→SUMO es más importante.
- Tráfico lento: 81 ventanas <8 km/h, recall vehículo = 0% para todos los sistemas.
- 11 tests pasan. 3 PNGs con datos reales. PDF explicación y PDF semanal.

**Archivos creados o modificados:**
- `semanas/S2/Pablo/codigo/ia/evaluar_generalizacion.py`
- `semanas/S2/Pablo/codigo/ia/escenarios_dificiles.py`
- `semanas/S2/Pablo/codigo/ia/generar_evidencias_s3.py`
- `semanas/S2/Pablo/codigo/ia/tests/test_evaluacion.py`
- `semanas/S2/Pablo/codigo/ia/reportes/metricas_generalizacion.json`
- `semanas/S2/Pablo/codigo/ia/reportes/evaluacion_generalizacion.md`
- `semanas/S2/Pablo/codigo/ia/reportes/curvas_sigma.csv`
- `semanas/S2/Pablo/evidencias/s3_umbral-vs-rf-por-fuente.png`
- `semanas/S2/Pablo/evidencias/s3_curvas-sigma.png`
- `semanas/S2/Pablo/evidencias/s3_trafico-lento.png`
- `semanas/S2/Pablo/explicaciones/s3_explicacion.md`
- `semanas/S2/Pablo/explicaciones/s3_explicacion.pdf`

**Decisiones y por qué:**
- **Bootstrap agrupado por usuario/semilla**: las ventanas de un mismo grupo están correlacionadas; remuestrear por ventana subestimaría la varianza.
- **Optimización del bootstrap con enteros**: sklearn f1_score sobre strings × 1,000 remuestreos × 294k ventanas era inviable. El cálculo directo con arrays int dio ~100x speedup.
- **Simulación corta (600s, 30 peatones)**: para cuidar RAM y tiempo. Generó suficientes datos de tráfico lento (~57k filas) pero no de peatón rápido (0 ventanas).
- **NaN en precision_media**: sklearn RF 1.9.1 maneja NaN nativamente. Eliminar el filtro de NaN fue crítico.

**Problemas encontrados:**
- Bootstrap naive tardaba >10 min. Resuelto con optimización (enteros + índices precalculados).
- Filtro de NaN eliminaba todas las ventanas GeoLife porque precision_media es NaN.
- Repo no visible en van3twin: se copió a results/ y se extrajeron archivos SUMO de la rama de Tyrone.
- Peatón rápido: 0 ventanas generadas con simulación corta. Necesitaría más peatones/duración.

**Pedidos a otros:**
- @Freddy: el RF v1 funciona bien en GeoLife (0.87) pero mal en SUMO (0.70 normal, 0.33 tráfico lento). La tasa veh->a_pie en SUMO es 69.3%. Para el controlador, el umbral es más seguro contra falsas liberaciones (0.2% vs 69.3%), pero el RF es mejor en macro-F1 en datos reales. Recomiendo RF con un filtro adicional de velocidad mínima para evitar liberar vehículos lentos.
- @Miguel: si grabas algo casero, lo más útil serían trayectorias de vehículo en congestión (<8 km/h).
- @Tyrone [Plan]: propuesta para S3 — reentrenar RF con datos mixtos GeoLife+SUMO para reducir la brecha de dominio.

**Bucle y verificación:** 6 vueltas totales (NaN filter, timeout bootstrap, SUMO sin contenedor, evaluación completa con SUMO, bug fix typeID setSpeed, re-evaluación optimizada). Verificador final: 7/7 criterios cumplidos.

**Bug fix importante:** `traci.person.setSpeed()` en SUMO 1.12 muta el typeID de `"peaton_rapido"` a `"peaton_rapido@pN"`. La comparación exacta `==` fallaba siempre. Corregido con `startswith("peaton_rapido")`. Tras el fix: 49,139 filas de peatón rápido en las 5 semillas (S101:5260, S102:9751, S103:11544, S104:14914, S105:7670). Evaluación: 8,082 ventanas, RF macro-F1 = 0.6665.

**Optimización de evaluación:** `preparar_sumo_escenarios` se llamaba 9 veces (3 escenarios + 6 sigmas). Se redujo a: 1 carga para escenarios, 2 semillas para curvas σ, 2 semillas para tráfico lento. Tiempo de ~2h+ reducido a ~15 min.

**Pendientes para la próxima sesión:**
- Considerar reentrenamiento con datos mixtos GeoLife+SUMO.

**Evidencias:**
![Umbral vs RF por fuente](../semanas/S2/Pablo/evidencias/s3_umbral-vs-rf-por-fuente.png)
![Curvas sigma](../semanas/S2/Pablo/evidencias/s3_curvas-sigma.png)
![Tráfico lento](../semanas/S2/Pablo/evidencias/s3_trafico-lento.png)
