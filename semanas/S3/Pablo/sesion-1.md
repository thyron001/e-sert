---
semana: S3
persona: Pablo
sesion: 1
titulo: Servicio de inferencia robusto - huecos, latencia menor a 5 ms y fallback
horas: 3-4
modulo: ia
depende: [S2-Pablo-2, S2-Pablo-3]
entrega: [ia/inferencia.py, ia/validacion.py, ia/bench_inferencia.py, ia/modelos/rf_v1.meta.json, ia/tests/test_inferencia.py]
evidencias: [s1_latencia-inferencia.png]
---
# S3 · Sesión 1 · Pablo 🟢: Servicio de inferencia robusto (huecos, latencia < 5 ms y *fallback*)

## Contexto
Lee `CLAUDE.md` y `docs/CONTRATO.md` (sección 2, firma de `clasificar`). Es la primera sesión de
S3: copia `proyecto/ia/` a `semanas/S3/Pablo/codigo/ia/` si no está. Desde esta semana
`inferencia.py` corre **en dos lugares exigentes**: dentro de TraCI con cientos de usuarios
(Freddy S3-2, 80 % de penetración) y en el backend con teléfonos reales que pierden señal
(Freddy S3-3). Debe ser rápido y **no fallar nunca** por datos sucios.

## Objetivo
Dejar `clasificar` robusto ante huecos, duplicados y ruido, con latencia p95 < 5 ms por ventana,
una versión en lote y un *fallback* al umbral cuando falten datos o el modelo.

## Pasos
1. Crea `ia/validacion.py` con `limpiar(ventana) -> (np.ndarray, Calidad)`:
   - ordena por `t`, elimina `t` duplicados y descarta `lat`/`lon` `NaN` o fuera de rango;
   - descarta puntos con `precision_m > 50` m (parámetro `precision_max_m`);
   - elimina saltos imposibles (velocidad implícita > 50 m/s);
   - remuestrea a 1 Hz e interpola linealmente huecos de hasta 5 s;
   - `Calidad` = `{n_validos, cobertura (0..1), hueco_max_s, precision_mediana_m}`.
2. Reescribe `ia/inferencia.py` sin romper la firma del contrato:
   - `clasificar(ventana, previo: ResultadoModo | None = None) -> ResultadoModo`;
   - con cobertura ≥ 0,6 y hueco máximo ≤ 10 s: Random Forest (`fuente: "rf"`);
   - con cobertura menor pero al menos 5 puntos: umbral del contrato (8 y 0,5 km/h), con la
     confianza multiplicada por la cobertura (`fuente: "umbral"`);
   - con menos de 5 puntos: devuelve `previo` con la confianza ×0,5 o, si no hay, el umbral con
     confianza 0;
   - si el modelo no carga o `predict` lanza: umbral y un `warnings.warn` **una sola vez**;
   - nunca lanza por datos; solo `TypeError` si la entrada no es una lista de puntos.
3. **Latencia:**
   - carga perezosa del modelo una vez (`functools.lru_cache`), `n_jobs=1` y sin `pandas` en el
     camino caliente: características con `numpy` vectorizado en el orden de `rf_v1.meta.json`;
   - `clasificar_lote(ventanas: list) -> list[ResultadoModo]` con una sola llamada a
     `predict_proba` para todas; meta: < 0,5 ms por ventana amortizado con 500 ventanas;
   - si el RF no llega a la meta, reduce `n_estimators` o `max_depth` y reporta la pérdida de
     macro-F1, o prueba `skl2onnx` + `onnxruntime`. Documenta la decisión.
4. Crea `ia/modelos/rf_v1.meta.json`: orden de características, versión de scikit-learn, SHA-256
   del `.joblib`, fecha, hiperparámetros y métricas de S2. Al cargar, avisa si la versión de
   scikit-learn no coincide.
5. Crea `ia/bench_inferencia.py`: 10 000 ventanas reales (SUMO y Cuenca), `time.perf_counter_ns`,
   descarta las 100 primeras de calentamiento y reporta p50, p95 y p99, individual y en lote.
6. **Tests** (`ia/tests/test_inferencia.py`, pytest + `hypothesis`):
   - propiedad: para ventanas aleatorias, `clasificar` no lanza, `modo` está en el enum y la
     confianza en [0, 1];
   - casos borde: lista vacía, 1 punto, todos los puntos iguales, `t` desordenado, `NaN`, un hueco
     de 15 s y `precision_m = 200`;
   - con ventanas limpias, el resultado coincide al 100 % con las predicciones guardadas de S2;
   - con la ruta del modelo rota, usa el umbral y avisa una vez;
   - `clasificar_lote` da lo mismo que llamar `clasificar` uno por uno.
7. Paraleliza: un subagente escribe los tests de propiedades mientras tú haces `validacion.py`;
   el *benchmark* se escribe al final, sobre el código ya estable.
8. **Evidencia** `evidencias/s1_latencia-inferencia.png`: histograma (escala log) de la latencia
   por ventana, individual y en lote, con líneas en p95 y en el límite de 5 ms.

## Dónde escribir
`semanas/S3/Pablo/codigo/ia/` y `evidencias/`.

## Hecho cuando
- [ ] `pytest ia/tests` pasa, con al menos 200 ejemplos de `hypothesis`.
- [ ] El p95 individual es < 5 ms y el lote < 0,5 ms por ventana en el *benchmark*.
- [ ] El *fallback* funciona sin modelo y con datos insuficientes (tests).
- [ ] La firma de `clasificar` sigue siendo compatible con el contrato.
- [ ] Existen `rf_v1.meta.json` y `s1_latencia-inferencia.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 1, Pablo). En "Pedidos a otros":
@Freddy, firma de `clasificar_lote`, el parámetro `previo` y las cifras de latencia; @Miguel, la
precisión máxima aceptada (50 m) por si quieres filtrarla en la app.
