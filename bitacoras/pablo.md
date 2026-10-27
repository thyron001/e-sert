# Bitácora de Pablo 🟢

**Color:** Verde (`#2E9E4F`) · **Rol:** IA: dataset, clasificador de movimiento y servicio de inferencia

Cada sesión agrega una entrada al final (ver *Protocolo de cierre* en `CLAUDE.md`). No se borra nada.

---

## S1 · Sesión 1 · 2026-10-21 · Ingesta del dataset GeoLife
**Estado:** hecha
**Qué hice:**
- Descargué GeoLife Trajectories 1.3 (~299 MB) con script idempotente (`descargar_geolife.py`).
- Procesé los 69 usuarios etiquetados (64 con datos útiles) con `ingesta_geolife.py`.
- Mapeé walk→a_pie, car/taxi/bus→vehiculo; descarté bike, train, subway, airplane, boat, run, motorcycle (1.6M puntos).
- Calculé velocidad por haversine, filtré 1,518 saltos >50 m/s.
- Generé Parquet de 3.25M filas, muestra CSV de 10K filas, y `geolife_info.json` con estadísticas.
- Escribí 18 tests unitarios (mapeo, unión de intervalos, filtro de saltos, haversine).
- Generé dos evidencias PNG: horas por modo y trayectorias al azar.

**Archivos creados o modificados:**
- `semanas/S1/Pablo/codigo/ia/datos/descargar_geolife.py`
- `semanas/S1/Pablo/codigo/ia/datos/ingesta_geolife.py`
- `semanas/S1/Pablo/codigo/ia/datos/evidencias_geolife.py`
- `semanas/S1/Pablo/codigo/ia/datos/geolife_info.json`
- `semanas/S1/Pablo/codigo/ia/datos/procesados/geolife_muestra.csv`
- `semanas/S1/Pablo/codigo/ia/tests/test_ingesta.py`
- `semanas/S1/Pablo/codigo/ia/tests/datos/` (fixtures sintéticos)
- `semanas/S1/Pablo/codigo/ia/requirements.txt`
- `semanas/S1/Pablo/evidencias/s1_geolife-horas-por-modo.png`
- `semanas/S1/Pablo/evidencias/s1_geolife-trayectorias.png`
- `semanas/S1/Pablo/estado.json`

**Decisiones y por qué:**
- **Bus como vehículo:** el clasificador opera sobre GPS puro (posición y velocidad). Un bus urbano en el Centro Histórico tiene un patrón de movimiento similar al de un auto; distinguirlos requeriría datos de paradas o rutas fijas que no tenemos.
- **Filtro de 50 m/s:** conservador (180 km/h), elimina saltos GPS sin perder viajes reales.
- **Segmentos por cambio de modo o gap >5 min:** segmenta naturalmente las trayectorias para el cálculo de velocidad y la clase "quieto" futura.

**Problemas encontrados:**
- El cálculo de `t` (segundos Unix) tenía un error: con pandas datetime64[us], `astype("int64")` da microsegundos, no nanosegundos. Se corrigió usando `(timestamp - epoch).dt.total_seconds()`.
- No se pudo crear un venv (falta python3-venv y no hay sudo); se instalaron dependencias con `pip --user --break-system-packages`.

**Pedidos a otros:** ninguno.

**Bucle y verificación:** 2 vueltas (la primera detectó el bug de timestamps); el verificador independiente reportó 5/5 criterios cumplidos.

**Pendientes para la próxima sesión:**
- Derivar la clase `quieto` a partir de ventanas de baja velocidad.
- Remuestrear a 1 Hz y generar ventanas de 30 s con paso de 5 s.
- Extraer características (velocidad media, desviación, distancia, bearing) para el Random Forest.

**Evidencias:**
![Horas por modo](../semanas/S1/Pablo/evidencias/s1_geolife-horas-por-modo.png)
![Trayectorias](../semanas/S1/Pablo/evidencias/s1_geolife-trayectorias.png)

---

## S1 · Sesión 2 · 2026-10-22 · Remuestreo, ventanas y características
**Estado:** hecha
**Qué hice:**
- Creé `ia/ventanas.py` con `remuestrear()` (interpolación a 1 Hz, partición en huecos >10 s) y `ventanear()` (ventanas de 30 s, paso 5 s, cobertura y pureza ≥80%).
- Implementé la derivación de `quieto`: velocidad efectiva (desplazamiento neto / duración) < 0.3 m/s Y desplazamiento < 10 m. Se usa velocidad efectiva porque el ruido GPS genera ~2.6 m/s aparentes incluso estando quieto.
- Creé `ia/caracteristicas.py` con `extraer()`: 18 features robustas (velocidad, aceleración, jerk, rumbo, proporciones, rectitud, distancia, precisión, paradas-arranques). Velocidades sobre posiciones suavizadas con mediana móvil de 3.
- Creé `ia/datos/construir_ventanas.py` para aplicar el pipeline completo a GeoLife. Procesamiento secuencial por usuario (joblib con n_jobs=-1 causaba OOM en usuarios grandes de >300k puntos).
- Escribí 11 tests con trazas sintéticas (línea recta, punto fijo con ruido, hueco, SUMO).
- Generé boxplots de 6 características × 3 clases como evidencia.

**Archivos creados o modificados:**
- `semanas/S1/Pablo/codigo/ia/ventanas.py`
- `semanas/S1/Pablo/codigo/ia/caracteristicas.py`
- `semanas/S1/Pablo/codigo/ia/datos/construir_ventanas.py`
- `semanas/S1/Pablo/codigo/ia/datos/evidencias_ventanas.py`
- `semanas/S1/Pablo/codigo/ia/tests/test_ventanas.py`
- `semanas/S1/Pablo/codigo/ia/README.md`
- `semanas/S1/Pablo/codigo/ia/__init__.py`
- `semanas/S1/Pablo/evidencias/s2_caracteristicas-por-clase.png`
- `semanas/S1/Pablo/explicaciones/s2_explicacion.md`
- `semanas/S1/Pablo/explicaciones/s2_explicacion.pdf`

**Decisiones y por qué:**
- **Velocidad efectiva para quieto:** la mediana de velocidades instantáneas no funciona porque el ruido GPS (σ~5 m) genera velocidades aparentes de ~2.6 m/s incluso tras suavizado. El desplazamiento neto / duración cancela el ruido aleatorio en 30 s.
- **Procesamiento secuencial:** `joblib.Parallel(n_jobs=-1)` causaba OOM kills (código 137) porque cada worker copiaba el DataFrame del usuario grande. Con n_jobs=1 tarda ~68 min pero completa de forma estable.
- **Bus como vehiculo (heredado de S1):** el GPS no distingue bus de auto en un entorno urbano.

**Problemas encontrados:**
- OOM kills repetidos con joblib paralelo. Resuelto cambiando a procesamiento secuencial.
- `matplotlib.Axes.boxplot()` no acepta `labels=` en la versión instalada. Corregido con `set_xticklabels()`.
- `fpdf2` no soporta tablas markdown con pipes dentro de `<td>`. Simplificadas las tablas en la explicación.

**Pedidos a otros:** ninguno.

**Bucle y verificación:** 1 vuelta de código (tests pasaron al primer intento), 4 intentos del pipeline por OOM. El verificador independiente reportó 5/5 criterios cumplidos.

**Pendientes para la próxima sesión:**
- Entrenar clasificador Random Forest con GroupKFold sobre las ventanas generadas.
- Integrar con trazas SUMO reales de Freddy cuando estén disponibles.

**Evidencias:**
![Características por clase](../semanas/S1/Pablo/evidencias/s2_caracteristicas-por-clase.png)

---

## S1 · Sesión 3 · 2026-10-22 · Línea base por umbral y primer Random Forest
**Estado:** hecha
**Qué hice:**
- Creé `ia/umbral.py` con la regla del contrato: vel_media > 8 km/h = vehiculo, < 0.5 km/h = quieto, resto = a_pie.
- Creé `ia/entrenar.py` con Pipeline(SimpleImputer + RandomForest), validación GroupKFold(5) por usuario_id.
- Creé `ia/evaluar.py` con métricas por fold (accuracy, macro-F1, recall, matrices de confusión, tasas de error críticas).
- Creé `ia/inferencia.py` con `clasificar()` del contrato §2: caché de modelo, fallback a umbral, variables ESERT_MODELO y ESERT_CLASIFICADOR.
- Escribí 6 tests de inferencia (auto→vehiculo, peatón→a_pie, modelo ausente→umbral, latencia <10ms, formato).
- Generé las 2 evidencias PNG: matrices de confusión lado a lado y F1 por clase con barras de error.

**Archivos creados o modificados:**
- `semanas/S1/Pablo/codigo/ia/umbral.py`
- `semanas/S1/Pablo/codigo/ia/entrenar.py`
- `semanas/S1/Pablo/codigo/ia/evaluar.py`
- `semanas/S1/Pablo/codigo/ia/inferencia.py`
- `semanas/S1/Pablo/codigo/ia/tests/test_inferencia.py`
- `semanas/S1/Pablo/codigo/ia/modelos/rf_v0.joblib` (197 MB, no va a git)
- `semanas/S1/Pablo/codigo/ia/modelos/rf_v0_info.json`
- `semanas/S1/Pablo/codigo/ia/resultados/s1_metricas.json`
- `semanas/S1/Pablo/codigo/ia/README.md` (actualizado con GroupKFold e inferencia)
- `semanas/S1/Pablo/codigo/ia/requirements.txt` (añadido scikit-learn, joblib)
- `semanas/S1/Pablo/evidencias/s3_matrices-umbral-vs-rf.png`
- `semanas/S1/Pablo/evidencias/s3_f1-por-clase.png`
- `semanas/S1/Pablo/explicaciones/s3_explicacion.md`
- `semanas/S1/Pablo/explicaciones/s3_explicacion.pdf`
- `semanas/S1/Pablo/evidencias/resumen_S1_Pablo.pdf`

**Decisiones y por qué:**
- **50 árboles en vez de 300:** los 300 árboles consumían >6 GB de RAM y causaban cierres de sesión (OOM). La validación cruzada se hizo con 300 árboles (métricas correctas), el modelo final con 50.
- **Modelo fuera de git:** pesa 197 MB (>50 MB). Se versiona rf_v0_info.json con metadatos y se regenera con `python -m ia.entrenar`.
- **n_jobs=2 para el modelo final:** evita OOM al no lanzar tantos procesos paralelos.

**Problemas encontrados:**
- El entrenamiento con n_jobs=-1 y 300 árboles causaba cierre de Claude por OOM (>6 GB). Resuelto reduciendo a 50 árboles y n_jobs=2.
- La compresión a nivel 9 del joblib tardaba demasiado.

**Pedidos a otros:**
- @Freddy: la firma de inferencia es `from ia.inferencia import clasificar`. Recibe `list[PuntoGPS]` (con t, lat, lon, precision_m) y devuelve `{"modo": str, "confianza": float, "fuente": "rf"|"umbral"}`. Variables: `ESERT_MODELO` para elegir modelo, `ESERT_CLASIFICADOR=umbral|rf` para forzar uno.
- @Miguel: las grabaciones caseras son opcionales. Si hay tiempo, ~10 minutos por clase (caminando, en auto, parado) servirían como validación extra independiente de GeoLife.

**Bucle y verificación:** 1 vuelta de código + 3 intentos de entrenamiento por OOM. El verificador independiente reportó 4/4 criterios cumplidos.

**Pendientes para S2:**
- Mejorar tasa vehiculo→a_pie (14%) con features de acelerómetro o datos SUMO difíciles.
- Integrar con trazas SUMO reales de Freddy.

**Evidencias:**
![Matrices de confusión](../semanas/S1/Pablo/evidencias/s3_matrices-umbral-vs-rf.png)
![F1 por clase](../semanas/S1/Pablo/evidencias/s3_f1-por-clase.png)

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
