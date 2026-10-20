---
semana: S1
persona: Pablo
sesion: 3
titulo: Línea base por umbral y primer Random Forest
horas: 3-4
modulo: ia
depende: [S1-Pablo-2]
entrega: [ia/entrenar.py, ia/evaluar.py, ia/inferencia.py, ia/modelos/rf_v0.joblib, ia/modelos/rf_v0_info.json]
evidencias: [s3_matrices-umbral-vs-rf.png, s3_f1-por-clase.png]
---
# S1 · Sesión 3 · Pablo 🟢: Línea base por umbral y primer Random Forest

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (línea base del clasificador) y `docs/CONTRATO.md`
(sección 2, firma de `clasificar`). **Si el Random Forest no le gana a la regla tonta de
"más de 8 km/h es auto", no aporta nada.** Esa comparación es la tabla central de la
sección de IA. Freddy importará `ia.inferencia.clasificar` desde el controlador TraCI en S2.

## Objetivo
Entrenar y evaluar con rigor (sin fuga de datos entre usuarios) la línea base por umbral y
un primer Random Forest, y publicar la función de inferencia del contrato.

## Pasos
1. `ia/umbral.py` implementa exactamente la regla del contrato: velocidad media de la ventana
   mayor a 8 km/h es `vehiculo`; menor a 0,5 km/h es `quieto`; el resto es `a_pie`.
2. `ia/entrenar.py`:
   - `RandomForestClassifier(n_estimators=300, class_weight="balanced_subsample", min_samples_leaf=2, n_jobs=-1, random_state=42)`;
   - imputación de NaN con `SimpleImputer(strategy="median")` dentro de un `Pipeline`;
   - validación con **`GroupKFold(n_splits=5)` agrupando por `usuario_id`**: ningún usuario
     aparece en entrenamiento y prueba a la vez. Explica en `ia/README.md` por qué un
     `KFold` normal inflaría las métricas.
3. `ia/evaluar.py`:
   - por *fold* y en total: *accuracy*, **macro-F1**, *recall* por clase y matriz de
     confusión normalizada;
   - lo mismo para la regla de umbral, sobre las mismas ventanas;
   - una métrica orientada al problema: **la tasa de ventanas `vehiculo` reales clasificadas
     como `a_pie`**, y al revés. La primera es la que causaría falsas liberaciones.
   - Guarda `ia/resultados/s1_metricas.json`.
4. Entrena el modelo final con todo GeoLife y guarda `ia/modelos/rf_v0.joblib`, junto con
   `rf_v0_info.json`:
   - lista y orden de características;
   - versión de scikit-learn;
   - métricas de la validación cruzada;
   - fecha;
   - hash de los datos.
5. `ia/inferencia.py` cumple **exactamente** el contrato:
   - `clasificar(ventana: list[PuntoGPS]) -> ResultadoModo`;
   - carga el modelo una sola vez (caché a nivel de módulo) y reutiliza `ventanas.py` y
     `caracteristicas.py`;
   - si el modelo no existe, o la ventana tiene menos del 80 % de cobertura, usa la regla de
     umbral con `fuente="umbral"`;
   - variable de entorno `ESERT_MODELO` para elegir el modelo y
     `ESERT_CLASIFICADOR=umbral|rf` para forzar uno (Tyrone la usará en los experimentos).
6. **Tests** (`ia/tests/test_inferencia.py`):
   - ventana de auto sintética → `vehiculo`;
   - ventana a pie → `a_pie`;
   - modelo ausente → `fuente="umbral"`;
   - latencia media menor a 10 ms por ventana (mídela).
7. **Evidencias:**
   - `s3_matrices-umbral-vs-rf.png`: las dos matrices de confusión lado a lado, con el
     macro-F1 en el título.
   - `s3_f1-por-clase.png`: barras de F1 por clase, umbral frente a RF, con barras de error
     entre *folds*.

## Dónde escribir
`semanas/S1/Pablo/codigo/ia/` y `evidencias/`. Los `.joblib` mayores de 50 MB no van a git:
reduce `n_estimators` o usa `compress=3`.

## Hecho cuando
- [ ] La validación es GroupKFold por usuario y está documentada.
- [ ] El RF supera a la regla de umbral en macro-F1. Si no la supera, documenta por qué y qué
  probarás en S2.
- [ ] `from ia.inferencia import clasificar` funciona desde la raíz del módulo, y los tests
  pasan.
- [ ] Existen las dos evidencias PNG y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 3, Pablo), **incluido el PDF
semanal**. En "Pedidos a otros": @Freddy, la firma y la ruta de `clasificar` y las variables
de entorno; @Miguel, que las grabaciones caseras son opcionales y cuántos minutos por clase
servirían como validación extra si hay tiempo.
