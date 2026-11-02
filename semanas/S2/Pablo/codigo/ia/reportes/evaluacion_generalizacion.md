# Evaluación de generalización — RF v1

## Resumen

Se evaluó el clasificador RF v1 (entrenado en S2-2) sobre **294,579 ventanas de 10 usuarios
de GeoLife nunca vistos** y **43,508 ventanas de escenarios SUMO** (semillas 101–105) con
tráfico lento y condiciones normales. El RF obtiene macro-F1 = 0.87 en GeoLife pero cae a
0.70 en SUMO normal y a 0.33 en tráfico lento, revelando una brecha de dominio importante
entre datos reales (Beijing) y simulados (Cuenca).

## Fuentes evaluadas

| Fuente | Ventanas | Grupos | Estado |
|--------|----------|--------|--------|
| GeoLife prueba | 294,579 | 10 usuarios | Evaluada |
| SUMO normal (σ=5) | 33,051 | 5 semillas | Evaluada |
| SUMO tráfico lento (σ=5) | 10,457 | 5 semillas | Evaluada |
| SUMO peatón rápido | 0 | — | Sin datos (simulación corta) |
| Grabaciones caseras | — | — | No disponibles |

## Métricas por sistema — GeoLife prueba

| Sistema | macro-F1 | IC 95% | Tasa veh→a_pie |
|---------|----------|--------|----------------|
| **RF v1** | **0.8743** | [0.821, 0.947] | 24.3% |
| RF v1 + suavizado | 0.8724 | [0.817, 0.947] | 24.1% |
| Umbral | 0.6983 | [0.619, 0.756] | 27.2% |

## Métricas por sistema — SUMO normal (σ=5 m)

| Sistema | macro-F1 | IC 95% | Tasa veh→a_pie |
|---------|----------|--------|----------------|
| RF v1 | 0.6958 | [0.677, 0.714] | 69.3% |
| RF v1 + suavizado | 0.5502 | [0.530, 0.569] | 62.4% |
| Umbral | 0.2512 | [0.239, 0.262] | 0.2% |

El RF confunde la mayoría de los vehículos SUMO con peatones (tasa veh→a_pie = 69.3%).
Esto se debe a la brecha de dominio: las velocidades y patrones de movimiento de SUMO
difieren sustancialmente de GeoLife. El umbral, en cambio, casi no confunde vehículos con
peatones porque las velocidades absolutas de SUMO sí superan el umbral de 6 km/h, pero
falla en clasificar quietos (solo 2 clases efectivas).

## Métricas por sistema — SUMO tráfico lento (σ=5 m)

| Sistema | macro-F1 | IC 95% | Tasa veh→a_pie |
|---------|----------|--------|----------------|
| RF v1 | 0.3333 | [0.333, 0.333] | 100.0% |
| RF v1 + suavizado | 0.2345 | [0.219, 0.252] | 98.3% |
| Umbral | 0.3292 | [0.328, 0.330] | 0.5% |

En tráfico lento (vehículos forzados a 0.8–2.0 m/s), el RF clasifica el **100%** de las
ventanas de vehículo como a_pie. Es el caso de fallo esperado: a velocidad de peatón, las
features de movimiento son indistinguibles. El umbral no falla porque incluso a 2 m/s
(7.2 km/h) supera ligeramente su umbral, pero su macro-F1 también es baja por el mismo
desbalance de clases.

## Brecha de generalización

| Fuente | CV (S2-2) | Prueba | Brecha |
|--------|-----------|--------|--------|
| GeoLife | 0.9259 | 0.8743 | −0.052 |
| SUMO normal | 0.9259 | 0.6958 | −0.230 |
| SUMO tráfico lento | 0.9259 | 0.3333 | −0.593 |

La brecha GeoLife (5.2pp) es aceptable: misma distribución, usuarios nuevos. La brecha SUMO
(23pp normal, 59pp tráfico lento) confirma que el modelo necesitaría reentrenamiento con
datos del dominio de Cuenca (SUMO o reales) para funcionar bien en el Centro Histórico.

## Comparación estadística (bootstrap pareado — GeoLife)

| Comparación | Δ macro-F1 | IC 95% | Significativo |
|-------------|-----------|--------|---------------|
| RF − Umbral | +0.185 | [+0.158, +0.226] | Sí |
| RF+suav − Umbral | +0.183 | [+0.156, +0.224] | Sí |

En GeoLife, el RF supera significativamente al umbral. En SUMO, el RF supera al umbral
en macro-F1 (0.70 vs 0.25) pero con una tasa de falsas liberaciones mucho mayor (69% vs 0.2%).

## Curvas F1 vs σ (ruido GPS)

Las curvas están en `curvas_sigma.csv` con 18 puntos (6 niveles de σ × 3 sistemas). Los
resultados muestran que:
- El RF mantiene macro-F1 ~0.70 para σ ∈ [0, 15] en SUMO: el ruido GPS no es el factor
  dominante; la brecha de dominio es más importante.
- El umbral es más sensible al ruido: σ > 10 m infla la velocidad aparente de los quietos,
  empeorando su recall.
- La tasa veh→a_pie del RF permanece alta (~69%) independientemente de σ, confirmando que
  el problema es la distribución de features, no el ruido.

## Tráfico lento (filtro vel < 8 km/h)

**81 ventanas**, **6.8 minutos** de simulación, velocidad media 7.47 km/h.

| Sistema | Recall vehículo |
|---------|----------------|
| Umbral | 0.0% |
| RF v1 | 0.0% |
| RF+suavizado | 0.0% |

Ningún sistema reconoce vehículos que circulan a <8 km/h. Es el límite fundamental del
enfoque: sin información adicional (acelerómetro, contexto de calle, historial de ruta),
un vehículo lento es indistinguible de un peatón solo con GPS.

## Limitaciones

1. **GeoLife es Beijing, no Cuenca**: el RF funciona bien en GeoLife (0.87) pero mal en SUMO
   (0.70), mostrando que los patrones aprendidos no transfieren directamente.
2. **SUMO no modela el multitrayecto real**: el ruido AR(1) simula error de posición pero no
   la reflexión en cañones urbanos.
3. **Peatón rápido no generado**: la simulación corta (600s, 30 peatones) no produjo
   suficientes ventanas de peatón rápido. Requeriría más peatones o mayor duración.
4. **10 usuarios de prueba (GeoLife)**: IC amplio [0.821, 0.947].
5. **Grabaciones caseras no disponibles**: Miguel no ha subido grabaciones a `proyecto/datos/`.
6. **Brecha de dominio**: el hallazgo principal es que el modelo necesita datos del dominio
   objetivo (Cuenca, real o simulado) para ser útil en producción.
