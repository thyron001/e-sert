# Evaluación de generalización — RF v1

## Resumen

Se evaluó el clasificador RF v1 (entrenado en S2-2) sobre **294,579 ventanas de 10 usuarios
de GeoLife nunca vistos** durante el entrenamiento. Los escenarios difíciles de SUMO (semillas
101–105) no se generaron porque el contenedor `van3twin` no estaba disponible; esa parte queda
pendiente.

## Fuentes evaluadas

| Fuente | Ventanas | Usuarios/trayectorias | Estado |
|--------|----------|----------------------|--------|
| GeoLife prueba | 294,579 | 10 usuarios | ✓ Evaluada |
| SUMO normal | — | — | Pendiente (sin contenedor) |
| SUMO tráfico lento | — | — | Pendiente |
| SUMO peatón rápido | — | — | Pendiente |
| Grabaciones caseras | — | — | No disponibles |

## Métricas por sistema — GeoLife prueba

| Sistema | macro-F1 | IC 95% | Tasa veh→a_pie |
|---------|----------|--------|----------------|
| **RF v1** | **0.8743** | [0.821, 0.947] | 24.3% |
| RF v1 + suavizado | 0.8724 | [0.819, 0.944] | 24.1% |
| Umbral | 0.6983 | [0.619, 0.756] | 27.2% |

### Métricas por clase

| Sistema | a_pie P/R/F1 | quieto P/R/F1 | vehiculo P/R/F1 |
|---------|-------------|---------------|-----------------|
| RF v1 | 0.69/0.92/0.79 | 1.00/1.00/1.00 | 0.94/0.76/0.84 |
| RF+suav | 0.69/0.92/0.79 | 0.98/1.00/0.99 | 0.94/0.76/0.84 |
| Umbral | 0.58/0.87/0.70 | 1.00/0.42/0.59 | 0.91/0.73/0.81 |

### Matrices de confusión normalizadas (RF v1)

|  | →a_pie | →quieto | →vehiculo |
|--|--------|---------|-----------|
| **a_pie** | 0.92 | 0.00 | 0.08 |
| **quieto** | 0.00 | 1.00 | 0.00 |
| **vehiculo** | 0.24 | 0.00 | 0.76 |

## Brecha de generalización

| Métrica | Validación cruzada (S2-2) | GeoLife prueba | Brecha |
|---------|--------------------------|----------------|--------|
| RF v1 macro-F1 | 0.9259 ± 0.0219 | 0.8743 [0.821, 0.947] | −0.052 |
| Umbral macro-F1 | 0.7265 ± 0.0746 | 0.6983 [0.619, 0.756] | −0.028 |

La brecha de 5.2 puntos del RF es esperable: los usuarios de prueba tienen patrones de
movimiento distintos a los de entrenamiento. La brecha del umbral es menor porque su regla
no depende de patrones aprendidos.

## Comparación estadística (bootstrap pareado)

| Comparación | Δ macro-F1 | IC 95% | Significativo |
|-------------|-----------|--------|---------------|
| RF − Umbral | +0.185 | [+0.158, +0.226] | Sí |
| RF+suav − Umbral | +0.183 | [+0.156, +0.224] | Sí |

## Curvas F1 vs σ (ruido GPS)

**No disponibles**: requieren escenarios SUMO que no se generaron por falta del contenedor
`van3twin`. El script `ia/escenarios_dificiles.py` está listo para ejecutarse cuando el
contenedor esté activo.

## Tráfico lento

**No disponible**: requiere escenarios SUMO con `trafico_lento` (vehículos a velocidad de
peatón, 0.8–2.0 m/s).

**Predicción sobre GeoLife**: la tasa vehiculo→a_pie del RF (24.3%) ya muestra que los
vehículos lentos son el caso más difícil. En GeoLife (Beijing, tráfico urbano) hay segmentos
donde los vehículos van a menos de 8 km/h por congestión, y el modelo los confunde con
peatones.

## Limitaciones

1. **GeoLife es Beijing, no Cuenca**: los patrones de velocidad, congestión y geometría urbana
   difieren. Sin embargo, las features (desplazamiento_neto, rectitud, etc.) son genéricas.
2. **SUMO no modela el multitrayecto real**: el ruido AR(1) simula el error de posición pero
   no la reflexión de señal en cañones urbanos reales.
3. **Escenarios SUMO pendientes**: sin las semillas 101–105 no se puede completar el análisis
   de sensibilidad a σ ni el caso de tráfico lento con datos controlados.
4. **10 usuarios de prueba**: el IC 95% es amplio [0.821, 0.947] por el bajo número de grupos
   en el bootstrap.
5. **Grabaciones caseras no disponibles**: Miguel no ha subido grabaciones a `proyecto/datos/`.
