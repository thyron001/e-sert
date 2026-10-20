---
semana: S2
persona: Pablo
sesion: 2
titulo: Ajuste de hiperparámetros, importancia y suavizado temporal - rf_v1
horas: 3-4
modulo: ia
depende: [S2-Pablo-1]
entrega: [ia/entrenar.py, ia/suavizado.py, ia/modelos/rf_v1.joblib, ia/modelos/rf_v1.json, ia/inferencia.py, ia/tests/]
evidencias: [s2_matriz-confusion.png, s2_importancia.png, s2_suavizado.png]
---
# S2 · Sesión 2 · Pablo 🟢: Ajuste de hiperparámetros, importancia y suavizado temporal (`rf_v1`)

## Contexto
Lee `CLAUDE.md` y `docs/CONTRATO.md` (sección 2: la firma de `clasificar` **no cambia**).
Trabaja sobre `ventanas_v2.parquet` de S2-1. Freddy usa `inferencia.py` en S2-2 y S3-1
dentro del bucle de TraCI, así que importa tanto la calidad como la latencia. La métrica
principal es **macro-F1** con validación agrupada por usuario; nunca dividas al azar por
ventana (ventanas solapadas del mismo usuario filtran información). Los usuarios de prueba de
`ia/particion_usuarios.json` y las semillas SUMO 101–105 **no se usan aquí** (ni para elegir
hiperparámetros ni `k`): son la prueba de S2-3. Añade un test que lo compruebe.

## Objetivo
Entrenar `rf_v1` con hiperparámetros ajustados, entender qué características pesan, añadir
un suavizado temporal que reduzca los cambios espurios de modo y publicarlo detrás de la
misma interfaz `clasificar`.

## Pasos
1. Crea `ia/entrenar.py` (`python -m ia.entrenar --datos ia/datos/ventanas_v2.parquet
   --n-iter 40 --semilla 42`):
   - `GroupKFold(n_splits=5)` con `groups = grupo`;
   - `Pipeline` con el `RandomForestClassifier` (sin escalado);
   - `RandomizedSearchCV(scoring="f1_macro", n_iter=40, cv=GroupKFold, n_jobs=-1,
     random_state=42)` sobre: `n_estimators` 100–600, `max_depth` {None, 8, 12, 16, 24},
     `min_samples_leaf` 1–10, `max_features` {"sqrt", "log2", 0.3, 0.5, 0.8},
     `class_weight` {None, "balanced", "balanced_subsample"};
   - reporta macro-F1 por *fold* (media ± desviación), comparado con la línea base por
     umbral sobre los mismos *folds*.
   La búsqueda tarda: lánzala **en segundo plano** y vigílala con `Monitor`; mientras tanto,
   escribe `suavizado.py`.
2. **Importancia**: `sklearn.inspection.permutation_importance` sobre el *fold* de
   validación (`n_repeats=10`, `scoring="f1_macro"`), no solo la impureza. Si una
   característica tiene importancia ≈ 0 y es cara de calcular, quítala y reentrena (anota la
   decisión).
3. Crea `ia/suavizado.py` con `Suavizador(metodo="media_movil", k=3)` que recibe la secuencia
   de probabilidades por ventana de un usuario:
   - `media_movil`: promedio de las últimas `k` probabilidades y luego `argmax`;
   - `histeresis`: cambia de modo solo si el nuevo modo supera `umbral_cambio=0.6` durante
     `k` ventanas seguidas;
   - métrica nueva: **cambios espurios por hora** (cambios de modo que no existen en
     `modo_real`), además de macro-F1. Elige método y `k` (1, 2, 3, 5) con validación
     agrupada; documenta la latencia añadida (`k × 5 s`).
4. Entrena el modelo final con los mejores hiperparámetros sobre todos los datos de
   entrenamiento y guarda:
   - `ia/modelos/rf_v1.joblib`;
   - `ia/modelos/rf_v1.json`: orden de características, hiperparámetros, versión de
     scikit-learn, macro-F1 de validación (media ± desviación), *hash* SHA-256 de los datos,
     suavizado elegido y fecha.
5. Actualiza `ia/inferencia.py` **sin cambiar la firma**: carga `rf_v1` una sola vez (caché
   de módulo), construye las características de la ventana y devuelve
   `{modo, confianza, fuente: "rf"}`; si el modelo no carga o la ventana tiene menos de 10
   puntos, cae a la regla de umbral con `fuente: "umbral"`. Añade
   `ClasificadorConEstado(usuario_id)` para el suavizado, sin romper `clasificar`.
6. **Tests** (`ia/tests/`): la firma y los tipos del contrato; *fallback* a umbral con
   ventana vacía; resultado determinista; latencia de `clasificar` < 5 ms por ventana
   (mediana de 1 000 llamadas, `time.perf_counter`); el JSON de metadatos coincide con el
   modelo cargado.
7. **Evidencias** (`dpi=150`):
   - `s2_matriz-confusion.png`: matriz normalizada por fila, agregada de los 5 *folds*,
     umbral frente a `rf_v1` lado a lado;
   - `s2_importancia.png`: importancia por permutación con barras de error;
   - `s2_suavizado.png`: modo real, crudo y suavizado de una secuencia de ejemplo con una
     transición `vehiculo → quieto → a_pie`.

## Dónde escribir
`semanas/S2/Pablo/codigo/ia/` y `semanas/S2/Pablo/evidencias/`. Si `rf_v1.joblib` pesa más
de 50 MB, no lo subas: deja el script que lo regenera y su *hash*.

## Hecho cuando
- [ ] La macro-F1 con `GroupKFold` de `rf_v1` supera a la del umbral (reporta ambas con ±).
- [ ] El suavizado reduce los cambios espurios por hora al menos un 30 % sin bajar la
  macro-F1 más de 0,02.
- [ ] `inferencia.py` mantiene la firma del contrato, usa `rf_v1` y tiene *fallback*.
- [ ] La latencia mediana de `clasificar` es menor a 5 ms.
- [ ] Existen las tres evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 2, Pablo). En "Pedidos a
otros": @Freddy, cómo usar `ClasificadorConEstado` en tu máquina de estados y la latencia
medida.
