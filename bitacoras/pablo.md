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
