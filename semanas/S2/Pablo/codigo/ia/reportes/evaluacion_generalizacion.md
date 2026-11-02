# Evaluación de generalización — RF v1

## Resumen

Se evaluó el clasificador RF v1 (entrenado en S2-2) sobre **294,579 ventanas de 10 usuarios
de GeoLife nunca vistos** y **353,868 ventanas de escenarios SUMO** (semillas 101–105) con
tráfico lento, peatón rápido y condiciones normales. El RF obtiene macro-F1 = 0.87 en
GeoLife pero cae a 0.64 en SUMO normal, 0.67 en peatón rápido y 0.33 en tráfico lento,
revelando una brecha de dominio importante entre datos reales (Beijing) y simulados (Cuenca).

## Fuentes evaluadas

| Fuente | Ventanas | Grupos | Estado |
|--------|----------|--------|--------|
| GeoLife prueba | 294,579 | 10 usuarios | Evaluada |
| SUMO normal (σ=5) | 253,385 | 5 semillas | Evaluada |
| SUMO tráfico lento (σ=5) | 92,401 | 5 semillas | Evaluada |
| SUMO peatón rápido (σ=5) | 8,082 | 5 semillas | Evaluada |
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
| RF v1 | 0.6395 | [0.629, 0.650] | — |
| RF v1 + suavizado | — | — | — |
| Umbral | — | — | — |

El RF obtiene macro-F1 = 0.64 en SUMO normal (253k ventanas). La brecha de dominio
(29pp vs CV) confirma que los patrones de GeoLife (Beijing) no transfieren directamente
a SUMO (Cuenca simulado).

## Métricas por sistema — SUMO tráfico lento (σ=5 m)

| Sistema | macro-F1 | IC 95% | Tasa veh→a_pie |
|---------|----------|--------|----------------|
| RF v1 | 0.3327 | [0.332, 0.333] | ~100% |
| RF v1 + suavizado | — | — | — |
| Umbral | — | — | — |

En tráfico lento (vehículos forzados a 0.8–2.0 m/s), el RF clasifica virtualmente
**todas** las ventanas de vehículo como a_pie (macro-F1 = 0.33, el mínimo para 3 clases).

## Métricas por sistema — SUMO peatón rápido (σ=5 m)

| Sistema | macro-F1 | IC 95% | Tasa veh→a_pie |
|---------|----------|--------|----------------|
| RF v1 | 0.6665 | [0.666, 0.667] | — |
| RF v1 + suavizado | — | — | — |
| Umbral | — | — | — |

Peatones rápidos (1.8–2.5 m/s) confunden parcialmente al RF (F1=0.67). El escenario es
menos severo que el tráfico lento porque los peatones rápidos solo afectan una fracción de
las ventanas (8k de 353k totales).

## Brecha de generalización

| Fuente | CV (S2-2) | Prueba | Brecha |
|--------|-----------|--------|--------|
| GeoLife | 0.9259 | 0.8743 | −0.052 |
| SUMO normal | 0.9259 | 0.6395 | −0.286 |
| SUMO peatón rápido | 0.9259 | 0.6665 | −0.260 |
| SUMO tráfico lento | 0.9259 | 0.3327 | −0.593 |

La brecha GeoLife (5.2pp) es aceptable: misma distribución, usuarios nuevos. La brecha SUMO
(29pp normal, 26pp peatón rápido, 59pp tráfico lento) confirma que el modelo necesitaría
reentrenamiento con datos del dominio de Cuenca (SUMO o reales) para funcionar bien en el
Centro Histórico.

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

**399 ventanas**, **33.2 minutos** de simulación.

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
3. **Peatón rápido**: se corrigió un bug donde `traci.person.setSpeed()` mutaba el typeID
   (de `"peaton_rapido"` a `"peaton_rapido@pN"`). Con el fix, se generaron 8,082 ventanas.
4. **10 usuarios de prueba (GeoLife)**: IC amplio [0.821, 0.947].
5. **Grabaciones caseras no disponibles**: Miguel no ha subido grabaciones a `proyecto/datos/`.
6. **Brecha de dominio**: el hallazgo principal es que el modelo necesita datos del dominio
   objetivo (Cuenca, real o simulado) para ser útil en producción.
