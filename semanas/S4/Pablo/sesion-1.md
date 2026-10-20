---
semana: S4
persona: Pablo
sesion: 1
titulo: Modelo final congelado y model card
horas: 3-4
modulo: ia
depende: [S3-Pablo-1, S3-Pablo-2]
entrega: [ia/entrenar_final.py, ia/modelos/rf_final.joblib, ia/modelos/rf_final.json, ia/MODEL_CARD.md, ia/inferencia.py, ia/tests/test_modelo_final.py, ia/tests/datos/ventanas_golden.json, informe/GUIA_ESTILO.md]
evidencias: [s1_model-card-metricas.png]
---
# S4 · Sesión 1 · Pablo 🟢: Modelo final congelado y *model card*

## Contexto
Lee `CLAUDE.md`, `docs/CONTRATO.md` (sección 2) y lo que quedó en `proyecto/ia/` tras S3:
hiperparámetros de S2-2, servicio robusto de S3-1 y análisis de errores y suavizado de S3-2.
Primero copia `ia/` e `informe/` desde `proyecto/` a `semanas/S4/Pablo/codigo/`. Tyrone
necesita el modelo **congelado en esta sesión** para la corrida final (S4-2), así que
publícalo pronto en `pablo/s4`. Plazo real de la semana: sábado 14, 23:59.

## Objetivo
Entrenar de forma determinista el `rf_final`, fijarlo con su hash, evaluarlo una última vez
sobre los usuarios de GeoLife no vistos y los escenarios difíciles de SUMO, documentarlo con una *model card* y dejar `inferencia.py` cargándolo por
defecto.

## Pasos
1. Crea `ia/entrenar_final.py`:
   - hiperparámetros fijos tomados del mejor resultado de S2-2/S3-2 (cítalo en un
     comentario con la ruta del archivo de resultados);
   - entrenamiento con GeoLife + ventanas de SUMO; **los usuarios de prueba de
     `ia/particion_usuarios.json` y las semillas SUMO 101–105 siguen siendo solo prueba** (nunca
     entran al entrenamiento; un test lo comprueba);
   - determinista: `random_state=42`, `n_jobs` fijo, orden de filas estable; dos ejecuciones
     deben dar el mismo SHA-256;
   - guarda `ia/modelos/rf_final.joblib` (`compress=3`) y `rf_final.json` con: SHA-256 del
     modelo, versión de `scikit-learn` (fíjala en `requirements.txt`), lista ordenada de
     características, orden de clases, ventana 30 s y paso 5 s, parámetros del suavizado,
     umbral de confianza para el *fallback*, SHA-256 de cada CSV de entrada, fecha y métricas.
2. **Evaluación final** con `ia/evaluar_generalizacion.py` de S2-3, por fuente (GeoLife no
   vistos, SUMO normal, tráfico lento, peatón rápido y, si existen, grabaciones caseras): F1
   macro, precisión y *recall* por clase, matriz de confusión, F1 de `vehiculo` en tráfico lento
   y curvas frente a σ (3–15 m), todo frente al `umbral` del contrato; IC 95 % *bootstrap*
   agrupado por usuario o trayectoria. Latencia de
   `clasificar` p50 y p99 en 10 000 llamadas (debe ser menor que 5 ms).
3. Actualiza `ia/inferencia.py`: carga `rf_final` por defecto, verifica el SHA-256 contra
   `rf_final.json` al cargar y, si no coincide o falta, cae a `fuente="umbral"` con un aviso
   en el log. La firma del contrato no cambia.
4. `ia/tests/test_modelo_final.py`:
   - el hash del archivo coincide con `rf_final.json`;
   - `ventanas_golden.json` (30 ventanas de prueba: 10 por clase, incluidas 3 de tráfico lento de SUMO)
     produce exactamente las salidas guardadas;
   - ventana con huecos, ventana de 1 punto y ventana vacía no lanzan excepciones;
   - p99 de latencia menor que 5 ms.
5. Escribe `ia/MODEL_CARD.md` (formato de Mitchell et al., 2019): detalles del modelo, uso
   previsto (detectar la salida real del auto para no liberar el puesto antes de tiempo),
   usos fuera de alcance, datos de entrenamiento y prueba con sus conteos por clase,
   métricas, resultados, **limitaciones y sesgos** (GeoLife es Beijing; todo es simulado y sin datos
   de campo; el ruido de cañón urbano es un AR(1) calibrado con literatura; tráfico lento), privacidad de las trazas y cómo
   reproducirlo con un comando.
6. **Congelado:** a partir de aquí el modelo no cambia. Cualquier cambio posterior sería
   `rf_final_v2` y se avisa por pedido. Anótalo al inicio de la *model card*.
7. Crea `informe/GUIA_ESTILO.md` para que todos escriban igual: cada sección empieza en `##`,
   figuras en `informe/figuras/<nombre>/` enlazadas en relativo, pie de figura en cursiva,
   tablas en Markdown, citas `[@clave]` contra `referencias.bib`, comentario
   `<!-- fuente: ... -->` junto a cada cifra y longitud objetivo de 1 500–2 500 palabras.
8. **Evidencia** `evidencias/s1_model-card-metricas.png`: matriz de confusión normalizada de
   `rf_final` en usuarios no vistos, barras de F1 por clase RF frente a umbral con IC y un recuadro con la
   latencia p50/p99.

## Dónde escribir
`semanas/S4/Pablo/codigo/ia/`, `semanas/S4/Pablo/codigo/informe/GUIA_ESTILO.md` y
`evidencias/`. Si el `.joblib` pasa de 50 MB, reduce árboles o profundidad y documéntalo.

## Hecho cuando
- [ ] `python ia/entrenar_final.py` dos veces da el mismo SHA-256.
- [ ] `pytest ia/tests` pasa completo, incluido `test_modelo_final.py`.
- [ ] `inferencia.py` carga `rf_final` por defecto y cae a `umbral` si el hash no coincide.
- [ ] `MODEL_CARD.md` tiene todas las secciones y cifras con su fuente.
- [ ] `informe/GUIA_ESTILO.md` está publicado en `pablo/s4`.
- [ ] Existe la evidencia `s1_model-card-metricas.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 1, Pablo). Haz el push en
cuanto termines. En "Pedidos a otros": @Tyrone, ruta y SHA-256 de `rf_final.joblib` para la
corrida final; @Freddy, `inferencia.py` ya carga `rf_final`; @todos, existe
`informe/GUIA_ESTILO.md`.
