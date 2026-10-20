---
semana: S2
persona: Pablo
sesion: 3
titulo: Evaluación de generalización con usuarios no vistos y escenarios difíciles de SUMO
horas: 3-4
modulo: ia
depende: [S2-Pablo-1, S2-Pablo-2, S1-Freddy-3, S1-Tyrone-3]
entrega: [ia/escenarios_dificiles.py, ia/evaluar_generalizacion.py, ia/reportes/evaluacion_generalizacion.md, ia/reportes/metricas_generalizacion.json, ia/reportes/curvas_sigma.csv, ia/tests/test_evaluacion.py]
evidencias: [s3_umbral-vs-rf-por-fuente.png, s3_curvas-sigma.png, s3_trafico-lento.png]
---
# S2 · Sesión 3 · Pablo 🟢: Evaluación de generalización con usuarios no vistos y escenarios difíciles de SUMO

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (sección IA) y tus bitácoras de S2-1 y S2-2. Esta es **la
evaluación que va al informe**. Todo el proyecto es simulado, así que la prueba combina dos
fuentes que el modelo nunca vio: los **usuarios de GeoLife de prueba** de
`ia/particion_usuarios.json` (`ventanas_prueba_geolife.parquet`) y **escenarios difíciles
generados en SUMO** con las semillas reservadas 101–105. La red y la demanda se leen de
`proyecto/sumo/`; el emulador, de `proyecto/traci/gps.py` (o tu `ia/ruido.py`). Las
grabaciones caseras de Miguel son **opcionales**: solo se usan si existen en `proyecto/datos/`.

## Objetivo
Medir con honestidad cómo rinden `umbral`, `rf_v1` y `rf_v1 + suavizado` fuera de la
distribución de entrenamiento, por fuente, frente al ruido GPS y en el caso de auto en tráfico
lento, que es el que causa falsas liberaciones.

## Pasos
1. **Escenarios difíciles** (`ia/escenarios_dificiles.py --semillas 101 102 103 104 105`), con
   `traci` sobre `centro_base.sumocfg`, posiciones limpias con `traci.vehicle.getPosition` /
   `traci.person.getPosition` y `traci.simulation.convertGeo`, CSV del contrato más la columna
   `escenario`:
   - `trafico_lento`: autos con `traci.vehicle.setMaxSpeed(veh, U(0,8; 2,0))` m/s en tramos de
     2–5 min, con paradas y arranques (*stop-and-go*), es decir, a velocidad de peatón;
   - `peaton_rapido`: personas con `traci.person.setSpeed(p, U(1,8; 2,5))` m/s;
   - `normal`: la mezcla habitual de autos, peatones y esperas, como referencia;
   - **barrido de σ**: cada traza limpia pasa por `aplicar_ruido_ar1` con σ ∈ {3, 5, 8, 10,
     15} m, `rho` de `ruido_literatura.json` y semilla fija por (traza, σ).
   Corre las 5 semillas **en segundo plano** (un proceso por semilla) y vigílalas con `Monitor`.
   Si no hay SUMO, la sesión queda `parcial`; no sustituyas SUMO por datos inventados.
2. Crea `ia/evaluar_generalizacion.py`: mismo remuestreo, ventanas y características que en
   entrenamiento. **Prohibido** reentrenar, elegir `k` o ajustar umbrales con estos datos; si algo
   lo pide a gritos, anótalo como propuesta para `rf_v1.1` en S3.
3. **Métricas por fuente** (`geolife_prueba`, `sumo_normal`, `sumo_trafico_lento`,
   `sumo_peaton_rapido` y, si existen, `caseras`), para los tres sistemas:
   - macro-F1, *recall* y precisión por clase, matriz de confusión normalizada;
   - IC 95 % por *bootstrap* **agrupado** (1 000 remuestreos): por usuario en GeoLife y por
     trayectoria en SUMO, nunca por ventana;
   - la **brecha de generalización** frente a la validación cruzada de S2-2.
4. **Curvas frente a σ** (`ia/reportes/curvas_sigma.csv`): macro-F1 y tasa `vehiculo → a_pie`
   (la que produce falsas liberaciones) en función de σ, para los tres sistemas, con IC. Anota el
   σ a partir del cual cada sistema cae por debajo de macro-F1 0,7. Explica por qué el umbral
   empeora con σ: el ruido infla la velocidad aparente de `quieto`.
5. **Tráfico lento**: ventanas con `modo_real = vehiculo` y velocidad media < 8 km/h. Reporta
   número de ventanas y minutos, *recall* de `vehiculo` y a qué clase se confunde. El umbral
   falla por diseño (`vehiculo` lento → `a_pie`); muestra cuánto recupera el RF y el suavizado.
6. **Comparación con la línea base**: tabla `fuente × sistema` con Δmacro-F1 RF − umbral e IC
   *bootstrap* pareado (mismos remuestreos para ambos sistemas); marca dónde la diferencia no
   es significativa.
7. **Grabaciones caseras (opcional)**: si `proyecto/datos/` tiene CSV válidos con `modo_real`,
   evalúalos como fuente `caseras` (validación extra, IC por grabación). Si no hay, escribe
   "no disponibles" en el reporte; **no** generes un mock de esta fuente.
8. Escribe `ia/reportes/evaluacion_generalizacion.md` (redactado para el informe): fuentes y
   minutos por clase, tablas con IC, curvas, tráfico lento, comparación con el umbral,
   limitaciones (GeoLife es Beijing; SUMO no modela el multitrayecto real) y cifras en
   `metricas_generalizacion.json`.
9. **Tests** (`ia/tests/test_evaluacion.py`): los usuarios evaluados son exactamente los de
   prueba de la partición (y su *hash* no cambió); las semillas 101–105 no aparecen en
   `ventanas_v2.parquet`; el *bootstrap* es determinista con semilla.
   Paraleliza: un subagente genera los escenarios (paso 1) mientras tú evalúas GeoLife.
10. **Evidencias** (`dpi=150`):
    - `s3_umbral-vs-rf-por-fuente.png`: macro-F1 por fuente de los tres sistemas, con IC 95 %;
    - `s3_curvas-sigma.png`: F1 y tasa `vehiculo → a_pie` frente a σ, una línea por sistema;
    - `s3_trafico-lento.png`: velocidad de una traza de tráfico lento con franjas del modo real
      y de lo que predijo cada sistema.

## Dónde escribir
`semanas/S2/Pablo/codigo/ia/` y `semanas/S2/Pablo/evidencias/`. Los CSV de escenarios van en
`.gitignore`; publica una muestra y su *hash*. Si hay grabaciones caseras, léelas sin copiarlas.

## Hecho cuando
- [ ] Los escenarios de las semillas 101–105 existen con `trafico_lento`, `peaton_rapido`,
  `normal` y los 5 niveles de σ.
- [ ] Un test demuestra que la evaluación usa solo usuarios de prueba y semillas reservadas.
- [ ] Hay macro-F1 con IC 95 % agrupado por fuente para los tres sistemas.
- [ ] `curvas_sigma.csv` y la figura muestran F1 y la tasa `vehiculo → a_pie` frente a σ.
- [ ] El caso tráfico lento está reportado con su número de ventanas y minutos.
- [ ] `evaluacion_generalizacion.md` está listo para el informe (caseras incluidas o "no disponibles").
- [ ] Existen las tres evidencias PNG y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 3, Pablo), **incluido el PDF
semanal**. En "Pedidos a otros": @Freddy, qué sistema conviene usar por defecto en el
controlador y el σ a partir del cual sube la tasa `vehiculo → a_pie`; @Miguel, si graba algo
casero (opcional), qué casos aportarían más.
