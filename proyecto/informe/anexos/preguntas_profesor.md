## Preguntas probables del profesor

Banco de preguntas para la exposición, agrupadas por tema. Cada una indica quién responde y la evidencia en el repositorio. Las respuestas de Freddy, Tyrone y Miguel se escribieron solo con hechos comprobables en `docs/`, bitácoras y resúmenes, y en el cierre (2026-11-17) se verificaron contra el código: umbrales de `traci/estados.py`, `traci/peatones.py`, `sumo/demanda/generar_demanda.py`, `comun/tarifa.json` y `kpis/kpis.py`.

### Inteligencia artificial (Pablo)

#### P1. ¿Por qué un Random Forest y no una LSTM?
**Responde:** Pablo. **Evidencia:** `ia/MODEL_CARD.md`, `ia/reportes/importancia_permutacion_final.csv`.

La entrada son `18` características por ventana de `30 s`, es decir, datos tabulares y pocos usuarios de GeoLife; un bosque se entrena en minutos, no necesita ajuste fino y se puede explicar: el desplazamiento neto aporta 0,340 de caída del F1 macro al permutarlo. Además corre en 2,12 ms en el percentil 99, muy bajo la meta de 5 ms. No se probó una LSTM; con tan pocos usuarios y sin datos de campo es difícil que generalice mejor, y sería un trabajo futuro. <!-- fuente: ia/reportes/importancia_permutacion_final.csv; ia/reportes/metricas_rf_final.json -->

#### P2. ¿Hay fuga de datos entre entrenamiento y prueba?
**Responde:** Pablo. **Evidencia:** `ia/tests/test_modelo_final.py` (clase `TestNoFuga`), `ia/particion_usuarios.json`.

No. Los 10 usuarios de prueba de GeoLife y las semillas de SUMO `101 a 105` nunca entran al entrenamiento; se entrenó con 38 usuarios y las semillas `201` y `202`. Un test lo comprueba al cargar el modelo y sobre las ventanas de entrenamiento. Dentro de cada fuente la partición es por usuario, no por ventana, porque las ventanas se solapan `25` de `30` segundos. <!-- fuente: ia/modelos/rf_final.json:entrenamiento -->

#### P3. ¿Cómo se derivó la clase `quieto`?
**Responde:** Pablo. **Evidencia:** `ia/ventanas.py`, `informe/pablo.md`.

GeoLife solo etiqueta caminar y vehículo. Una ventana de esas clases pasa a `quieto` si su velocidad efectiva es menor que `0,3 m/s` y su desplazamiento neto menor que `10 m`. Es una regla propia, así que la clase `quieto` es fácil de acertar (F1 0,999 en usuarios no vistos) y esa cifra no mide cuánto se parece a un parqueo real; en SUMO `quieto` es un auto estacionado de verdad. <!-- fuente: ia/reportes/metricas_rf_final.json -->

#### P4. ¿Transfiere un modelo entrenado en Beijing a un centro histórico simulado?
**Responde:** Pablo. **Evidencia:** `ia/reportes/metricas_rf_final.json`, `ia/reportes/curvas_sigma_final.csv`.

Solo en parte. En usuarios no vistos de GeoLife el F1 macro es 0,872, y en SUMO normal con σ = 5 m es 0,738. Sin ruido sube a 0,911 y con σ = 15 m baja a 0,519, de modo que la transferencia depende sobre todo del ruido del GPS. Por eso el modelo final se entrenó con ruido sobre las posiciones y con episodios reales de SUMO, no solo con GeoLife. <!-- fuente: ia/reportes/metricas_rf_final.json; ia/reportes/curvas_sigma_final.csv -->

#### P5. ¿Por qué no hay datos de campo?
**Responde:** Pablo. **Evidencia:** `docs/CONTEXTO.md`, `ia/MODEL_CARD.md`.

El alcance acordado es una simulación completa: el teléfono no se mueve, sigue a un auto de SUMO, y no hay pruebas en el Centro Histórico. Las grabaciones caseras eran opcionales y no se hicieron, así que no hay validación con GPS real de un teléfono. Es la principal limitación y la primera tarea de trabajo futuro.

#### P6. ¿Qué pasa si el teléfono queda dentro del auto?
**Responde:** Pablo. **Evidencia:** `ia/MODEL_CARD.md` (limitaciones), `informe/pablo.md`.

El modelo solo ve el GPS y no sabe quién lleva el teléfono. Si el dueño se baja y deja el teléfono dentro, el teléfono sigue `quieto` y no se detecta el paseo; la sesión se cierra cuando el auto sale, aunque el dueño no vaya dentro. Con el teléfono en el bolsillo funciona como se diseñó. Un acelerómetro o una confirmación en la app ayudaría a detectar este caso.

#### P7. ¿Por qué no se usó el acelerómetro?
**Responde:** Pablo. **Evidencia:** `docs/CONTEXTO.md`, `informe/pablo.md`.

Porque todo es simulado y SUMO no produce aceleración de un sensor, solo posiciones. El conjunto SHL queda como opción si después se suma el acelerómetro, y resolvería casos que el GPS no separa: el auto en tráfico lento a paso de peatón y el teléfono dejado en el auto. Es trabajo futuro, no una decisión técnica contra el sensor.

#### P8. ¿Por qué ventanas de 30 segundos?
**Responde:** Pablo. **Evidencia:** `docs/CONTRATO.md` §2, `ia/reportes/suavizado_k_final.csv`.

La ventana de `30 s` con paso de `5 s` la fija el contrato (§2) como compromiso: con menos tiempo el ruido del GPS domina, y con más tiempo la decisión llega tarde. Con esa ventana el retardo mediano de cierre del RF es 14,0 s con la máquina de Freddy. No se hizo un estudio de otras duraciones, y esa comparación queda como trabajo futuro. <!-- fuente: ia/reportes/suavizado_k_final.csv -->

#### P9. ¿Qué pasa en un semáforo largo?
**Responde:** Pablo. **Evidencia:** `ia/reportes/metricas_rf_final.json`.

Un auto detenido más de 30 s se ve como `quieto` y no cuenta como `vehiculo`, así que retrasa el cierre de la sesión, pero no la cierra por error: en SUMO normal la precisión de `vehiculo` es 1,00 y su recall 0,55. Cerrar en falso exige dos ventanas seguidas de `vehiculo` a más de `20 m` del puesto. No se evaluó un semáforo largo como escenario aparte. <!-- fuente: ia/reportes/metricas_rf_final.json -->

#### P10. ¿Por qué `GroupKFold` por usuario?
**Responde:** Pablo. **Evidencia:** `ia/reportes/cv_search_rf_v1.csv`, `informe/pablo.md`.

Las ventanas se solapan 25 de sus 30 segundos y un mismo usuario repite rutas y estilo. Con una validación aleatoria, casi las mismas ventanas caerían en entrenamiento y validación, y la calidad saldría inflada. Con `GroupKFold` todas las ventanas de un usuario quedan del mismo lado, y se usó para elegir hiperparámetros; la evaluación final usa usuarios de prueba que nunca se vieron.

#### P11. ¿Qué es una falsa liberación y por qué la métrica no es la exactitud?
**Responde:** Pablo. **Evidencia:** `docs/CONTRATO.md` §3, `informe/pablo.md`.

Es cerrar la sesión, y ofrecer el puesto a otros, mientras el auto sigue estacionado. Una ventana mal clasificada no basta: se necesitan dos ventanas seguidas de `vehiculo` con el teléfono a más de `20 m` del puesto. Por eso se mide cuántas sesiones por 100 se cierran en falso y cuánto tarda en cerrarse una correcta, no el porcentaje de ventanas acertadas.

#### P12. ¿Por qué una regla de velocidad falla con ruido?
**Responde:** Pablo. **Evidencia:** `ia/reportes/curvas_sigma_final.csv`, `ia/reportes/suavizado_k_final.csv`.

El error del GPS se parece al del segundo anterior (AR(1) con `ρ = 0,8`), y entre muestras consecutivas hace que un teléfono quieto parezca avanzar a más de `8 km/h`. El F1 macro del umbral baja de 0,798 sin ruido a 0,202 con σ = 5 m, y cierra en falso 88,2 de cada 100 sesiones. El RF aprende que el desplazamiento neto de la ventana, no la velocidad, es lo que importa. <!-- fuente: ia/reportes/curvas_sigma_final.csv; ia/reportes/suavizado_k_final.csv -->

#### P13. ¿Qué cambió entre el primer modelo y el modelo final?
**Responde:** Pablo. **Evidencia:** `ia/datos/construir_entrenamiento_final.py`, `ia/MODEL_CARD.md`.

El primer entrenamiento "aumentaba" las ventanas multiplicando algunas características por factores al azar, sin ruido en las posiciones, y el modelo nunca vio características calculadas sobre trazas ruidosas. El modelo final aplica ruido AR(1) a las posiciones, recalcula las `18` características con el mismo código de inferencia y usa episodios reales de SUMO. Con σ = 5 m su F1 macro es 0,711 en SUMO. <!-- fuente: ia/reportes/curvas_sigma_final.csv -->

#### P14. ¿Por qué rinde peor en tráfico lento y en peatón rápido?
**Responde:** Pablo. **Evidencia:** `ia/reportes/metricas_rf_final.json`, `informe/figuras/pablo/f06_trafico-lento.png`.

En tráfico lento los autos van a paso de peatón y con solo GPS son indistinguibles: el RF clasifica a pie el 63,7 % de ellos y el F1 macro es 0,051. En peatón rápido, un peatón a 1,8 a 2,5 m/s con ruido se parece a un auto lento y el recall de `a_pie` es 0,86 (F1 macro 0,453). Son escenarios adversariales y artificiales; el modelo mejora en el escenario realista. <!-- fuente: ia/reportes/metricas_rf_final.json -->

#### P15. ¿Qué significa `k` y por qué `k = 1` o `k = 5`?
**Responde:** Pablo. **Evidencia:** `ia/reportes/suavizado_k_final.csv`, `ia/reportes/suavizado_k_final_contrato.csv`.

`k` es cuántas ventanas se votan para suavizar el modo; con `k = 1` no se suaviza. Con la máquina de Freddy actual el RF libera en falso 0,78 por 100 con `k = 1`, y los intervalos con `k = 3` y `k = 5` se solapan, así que se queda el menor. Con las transiciones literales del contrato baja de 13,11 a 5,44 por 100 con `k = 5`, con retardo mediano de 26 s, dentro del límite de `60 s`. <!-- fuente: ia/reportes/suavizado_k_final.csv; ia/reportes/suavizado_k_final_contrato.csv -->

#### P16. ¿Por qué se redujo el modelo a 100 árboles?
**Responde:** Pablo. **Evidencia:** `ia/modelos/rf_final.json:nota_tamano`, `ia/entrenar_final.py`.

Con las ventanas ruidosas, los árboles crecen mucho más, y el modelo con 200 árboles y hoja mínima 3 pesaba `106,6 MB`, sobre el límite de `50 MB` para versionarlo. Con 100 árboles y hoja mínima 5 pesa 48,0 MB y mantiene el F1 macro de 0,872 en usuarios no vistos. <!-- fuente: ia/modelos/rf_final.json; ia/reportes/metricas_rf_final.json -->

#### P17. ¿Cómo se garantiza que se usa siempre el mismo modelo?
**Responde:** Pablo. **Evidencia:** `ia/modelos/rf_final.json:sha256_modelo`, `ia/tests/test_modelo_final.py`.

Con el SHA-256 del archivo, que `inferencia.py` verifica antes de leerlo: si no coincide, falta o no hay referencia, el servicio cae al umbral con un aviso en el registro. Dos entrenamientos con la misma semilla dan el mismo hash y 30 ventanas fijas producen siempre las mismas salidas. Cualquier cambio posterior sería `rf_final_v2`.

#### P18. ¿Cuánto tarda `clasificar`?
**Responde:** Pablo. **Evidencia:** `ia/reportes/metricas_rf_final.json:latencia`, `ia/bench_inferencia.py`.

En 9 900 llamadas (tras 100 de calentamiento) la latencia es de 1,35 ms de mediana y 2,12 ms en el percentil 99, bajo la meta de 5 ms. Se logra convirtiendo los árboles a arreglos de NumPy y recorriéndolos todos a la vez, con las mismas predicciones que scikit-learn. <!-- fuente: ia/reportes/metricas_rf_final.json -->

#### P19. ¿Qué es el intervalo bootstrap agrupado y por qué es tan ancho en GeoLife?
**Responde:** Pablo. **Evidencia:** `ia/evaluar_final.py`, `ia/reportes/metricas_rf_final.json`.

Se remuestrean usuarios completos, no ventanas, porque las ventanas de un usuario están correlacionadas; con 1 000 remuestreos se toman los percentiles `2,5 y 97,5`. Con solo 10 usuarios de prueba, el F1 macro del RF queda en 0,872 con intervalo de 0,818 a 0,946. La diferencia con el umbral, 0,183, es significativa (0,156 a 0,224). <!-- fuente: ia/reportes/metricas_rf_final.json -->

#### P20. ¿Por qué ruido AR(1) y de dónde salen σ de 3 a 15 m?
**Responde:** Pablo. **Evidencia:** `ia/calibracion/FUENTES.md`, `informe/pablo.md`.

El error de un GPS real no es independiente entre segundos: cambia lentamente, y el AR(1) con `ρ = 0,8` lo reproduce. El rango de σ, de `3 a 15 m`, se adoptó a partir de literatura sobre error de GPS urbano, pero los valores exactos son una elección del proyecto, no una cifra de un artículo. No modela el multitrayecto real de las fachadas, que produce saltos.

### Sistema y simulación (Freddy)

#### P21. ¿Cómo funciona la máquina de estados de la sesión?
**Responde:** Freddy (verificada contra el repositorio el 2026-11-17). **Evidencia:** `docs/CONTRATO.md` §3, `proyecto/traci/estados.py`.

La sesión pasa por BUSCANDO, GUIADO, ESTACIONADO, A_PIE, REGRESANDO, SALIENDO y CERRADA. Pasa a A_PIE si el modo es `a_pie` y la distancia al puesto supera `15 m`, a REGRESANDO si baja de `30 m`, y a SALIENDO con dos ventanas de `vehiculo` a más de `20 m`. La clase `MaquinaSesion` es pura (sin TraCI), por lo que se prueba sin SUMO.

#### P22. ¿Cómo se mide una falsa liberación en la simulación?
**Responde:** Freddy (verificada contra el repositorio el 2026-11-17). **Evidencia:** `docs/CONTRATO.md` §3, `bitacoras/freddy.md`.

Se cuenta como falsa liberación cerrar la sesión mientras el auto sigue estacionado, y se verifica con `traci.vehicle.isStoppedParking`; `ControlSesiones` la registra en un CSV. En su corrida de 30 minutos con el clasificador de umbral, Freddy midió 214 falsas liberaciones, 62,4 por 100 sesiones. <!-- fuente: bitacoras/freddy.md -->

#### P23. ¿Por qué un modo espejo?
**Responde:** Freddy (verificada contra el repositorio el 2026-11-17). **Evidencia:** `docs/CONTEXTO.md`, `docs/CONTRATO.md` §7.

Porque todo el proyecto es simulado: el teléfono no envía su GPS, sino que sigue a un auto de SUMO elegido y muestra lo que vería su conductor (guiado al puesto, sesión, costo en vivo, avisos y recibo). El backend emite un mensaje por segundo por cada vehículo seguido en `/ws/espejo/{veh_id}`. No hay pruebas de campo en el Centro.

#### P24. ¿Cómo se simula que el conductor se baja y vuelve?
**Responde:** Freddy (verificada contra el repositorio el 2026-11-17). **Evidencia:** `proyecto/traci/peatones.py`, `bitacoras/freddy.md`.

`GestorPeatones` crea un peatón por cada auto de búsqueda que estaciona: va a su destino, espera la diligencia y vuelve; mientras tanto la parada del auto se extiende y se reanuda cuando el peatón regresa. Incluye casos difíciles: regreso corto en el 15 % de los casos y espera dentro del auto en el 10 %. <!-- fuente: bitacoras/freddy.md -->

#### P25. ¿El guiado reduce el tiempo de búsqueda?
**Responde:** Freddy y Tyrone (verificada contra el repositorio el 2026-11-17). **Evidencia:** `bitacoras/freddy.md`.

En la corrida de S2 con 50 % de app, con el mapa de ocupación del sistema la búsqueda con app fue de 11,3 min frente a 10,8 min sin app, es decir, no mejoró; con la ocupación real sí (10,0 frente a 10,7 min). Freddy propuso contar en el mapa las reservas de los autos en GUIADO. En la corrida final la búsqueda con la app no mejoró: 432,7 s a ciegas frente a 434,3, 438,2 y 450,7 s con 20, 50 y 80 % de app (el IC de Tyrone incluye la línea base en 20 y 50 %). <!-- fuente: kpis/resultados/final/resumen.csv --> <!-- fuente: bitacoras/freddy.md -->

### Escenario y KPIs (Tyrone)

#### P26. ¿Cómo se construye el escenario de hora pico?
**Responde:** Tyrone (verificada contra el repositorio el 2026-11-17). **Evidencia:** `bitacoras/tyrone.md`, `proyecto/sumo/demanda/generar_demanda.py`.

Con la red OSM del Centro Histórico, los `parkingArea` generados por script y una demanda de 1 800 vehículos por hora, calibrada para llegar a una ocupación media de 87,0 % y 87,7 % en las dos semillas. Hay 80 % de ocupación de fondo (autos ya estacionados), 40 % de tráfico de paso, llegadas Poisson y estadía lognormal de media 45 min. <!-- fuente: bitacoras/tyrone.md -->

#### P27. ¿Qué mide cada KPI?
**Responde:** Tyrone (verificada contra el repositorio el 2026-11-17). **Evidencia:** `bitacoras/tyrone.md`, `proyecto/kpis/kpis.py`.

La búsqueda empieza al entrar al primer tramo a 300 m o menos del destino y termina cuando el auto se detiene en un `parkingArea`; la distancia cuenta tramos completos, y el CO₂ integra las emisiones muestreadas cada 10 s (validado contra tripinfo con razón 0,988). También se miden ocupación, falsas liberaciones por 100 sesiones y retardo de cierre. En la línea base, la búsqueda media fue de 349 y 362 s. <!-- fuente: bitacoras/tyrone.md -->

#### P28. ¿Qué penetración de la app se simula?
**Responde:** Tyrone (verificada contra el repositorio el 2026-11-17). **Evidencia:** `docs/CONTEXTO.md`, `bitacoras/tyrone.md`.

El alcance fija la búsqueda a ciegas (línea base, `con_app = 0`) frente a la app con `20`, `50` y `80 %` de usuarios y al menos 2 semillas. Los resultados de la corrida final, falsas liberaciones por 100 sesiones y retardo de cierre por penetración, con umbral fueron 88,9, 87,2 y 86,6 por 100 sesiones y con `rf_final` 0 en las tres penetraciones; el retardo mediano de cierre con `rf_final` fue 22,7, 18,8 y 18,4 s <!-- fuente: kpis/resultados/final/resumen.csv -->.

#### P29. ¿Por qué hay `6 194` puestos si las fuentes oficiales dan unas `2 500`?
**Responde:** Tyrone (verificada contra el repositorio el 2026-11-17). **Evidencia:** `bitacoras/miguel.md`, `bitacoras/tyrone.md`.

Miguel lo advirtió al revisar la red: el script genera `6 194` plazas en 103 calles, y las fuentes oficiales dan unas `2 500` en toda la ciudad (`1 424` en el Centro Histórico en 2020). Para llegar a una ocupación realista, Tyrone añadió un `80 %` de autos de fondo ya estacionados. El escenario final adopta ese `80 %` de puestos ocupados al inicio (`generar_demanda.py --ocupacion-fondo 0.80`, valor por defecto). <!-- fuente: bitacoras/miguel.md -->

#### P30. ¿Qué se hace con los buscadores que no alcanzan a estacionar?
**Responde:** Tyrone (verificada contra el repositorio el 2026-11-17). **Evidencia:** `bitacoras/tyrone.md`.

Se excluyen de las estadísticas de búsqueda y se reportan aparte, porque su búsqueda está censurada al final de la simulación: en las dos semillas de la línea base fueron 201 y 248 buscadores. La corrida final mantiene ese criterio: `kpis/kpis.py` los reporta como `buscadores_sin_estacionar` y `busqueda_censurada_media_s`. <!-- fuente: bitacoras/tyrone.md -->

### App y cobro (Miguel)

#### P31. ¿Cómo se calcula el cobro por fracciones?
**Responde:** Miguel (verificada contra el repositorio el 2026-11-17). **Evidencia:** `docs/CONTEXTO.md`, `docs/CONTRATO.md` §5.

Se retiene el bloque mínimo al confirmar la llegada y, al detectar la salida real, se debita el tiempo real en fracciones de 5 min con un cobro mínimo de 10 min, y se libera la retención. La tarifa sale de la ordenanza SERT: USD 0,25 por media hora o fracción, que equivale a un valor de USD 0,50 por hora, con un máximo de 2 horas. <!-- fuente: docs/CONTRATO.md; bitacoras/miguel.md -->

#### P32. ¿Qué diferencia hay con la tarjeta SERT?
**Responde:** Miguel (verificada contra el repositorio el 2026-11-17). **Evidencia:** `bitacoras/miguel.md`, `docs/CONTRATO.md` §5.

La tarjeta tiene 4 casilleros de 30 minutos, así que se paga por bloques; la app cobra el tiempo real por fracciones de 5 min y el recibo muestra el ahorro frente a la tarjeta. En el recorrido de ejemplo de la app, 50 min cobran 0,42 USD frente a 0,50 USD con tarjeta. <!-- fuente: bitacoras/miguel.md -->

#### P33. ¿Qué pasa si falla Payphone o el pago queda pendiente?
**Responde:** Miguel (verificada contra el repositorio el 2026-11-17). **Evidencia:** `bitacoras/miguel.md`, `docs/CONTEXTO.md`.

La intención de pago es la fuente de verdad y acredita una sola vez: tres retornos repetidos acreditan una vez. Un pago pendiente que no se confirma lo reversa Payphone a los 5 minutos. El modo `pruebas` se probó en el VPS con un pago aprobado, y los autos simulados nunca llaman a Payphone. <!-- fuente: bitacoras/miguel.md -->

#### P34. ¿Qué datos de ubicación recoge la app y cómo se protege la privacidad?
**Responde:** Miguel (verificada contra el repositorio el 2026-11-17). **Evidencia:** `docs/CONTEXTO.md`, `bitacoras/miguel.md`.

En este proyecto el teléfono no envía su ubicación: sigue a un auto simulado. Las grabaciones caseras, si se hacen, son opcionales, anonimizadas y quedan en `datos/grabaciones/` según un protocolo, y las credenciales de Payphone viven solo en un `.env` fuera del repositorio. La política para un despliegue real (retención, consentimiento) no está definida en el proyecto y queda como trabajo futuro.

#### P35. ¿La app funciona en segundo plano y en un iPhone?
**Responde:** Miguel (verificada contra el repositorio el 2026-11-17). **Evidencia:** `docs/CONTEXTO.md`, `bitacoras/miguel.md`.

En iPhone el segundo plano es limitado, así que la app debe estar abierta durante la demostración. La recarga de punta a punta se probó en Android con Expo Go (de 4,92 a 14,92 USD tras aprobar 10 USD). No hubo un iPhone físico: en iOS solo se probaron pantallas en el simulador de Xcode (sección de Miguel). <!-- fuente: bitacoras/miguel.md -->

### Preguntas añadidas tras la revisión externa (IA, Pablo)

#### P36. ¿Aporta el Random Forest algo más que una regla simple de desplazamiento?
**Responde:** Pablo. **Evidencia:** `ia/reportes/linea_base_desplazamiento.json`, `informe/figuras/pablo/f03_importancia-permutacion.png`.

Depende de los datos. Un árbol de profundidad 3 que solo mira el desplazamiento neto obtiene un F1 macro de 0,750 en GeoLife no vistos, frente a 0,872 del Random Forest, así que en datos reales el modelo aporta bastante. En SUMO normal, con las mismas 58 005 ventanas, el árbol llega a 0,775 y el Random Forest a 0,738: no lo supera. Coincide con la importancia por permutación, que concentra casi todo en el desplazamiento neto. <!-- fuente: ia/reportes/linea_base_desplazamiento.json -->

#### P37. ¿No es circular evaluar en SUMO con el mismo ruido con el que se entrenó?
**Responde:** Pablo. **Evidencia:** `ia/MODEL_CARD.md`, `informe/pablo.md`.

En parte sí. Las semillas de prueba (101 a 105) son distintas de las de entrenamiento (201 y 202), pero el generador de ruido AR(1) y el escenario son los mismos; por eso SUMO mide la robustez al ruido modelado y no el desempeño real. El único dato real es GeoLife (usuarios no vistos), y es de Beijing. No hay datos de campo.

### Resumen

*Preguntas por tema, responsable y evidencia.*

| Pregunta | Responde | Evidencia |
|---|---|---|
| P1 a P20, P36 y P37: Random Forest, fuga, `quieto`, transferencia, datos de campo, teléfono en el auto, acelerómetro, ventana, semáforo, `GroupKFold`, falsa liberación, umbral, cambio de modelo, escenarios difíciles, `k`, árboles, SHA-256, latencia, bootstrap, ruido | Pablo | `ia/MODEL_CARD.md`, `ia/reportes/metricas_rf_final.json`, `informe/pablo.md` |
| P21 a P25: máquina de estados, falsa liberación, modo espejo, peatones, guiado | Freddy (P25 con Tyrone) | `docs/CONTRATO.md`, `proyecto/traci/estados.py`, `bitacoras/freddy.md` |
| P26 a P30: hora pico, KPIs, penetración, puestos, buscadores censurados | Tyrone | `bitacoras/tyrone.md`, `proyecto/kpis/kpis.py` |
| P31 a P35: cobro, tarjeta SERT, Payphone, privacidad, iPhone | Miguel | `docs/CONTRATO.md`, `bitacoras/miguel.md` |

Recuento: 22 de Pablo (P1 a P20, P36 y P37), 5 de Freddy, 5 de Tyrone y 5 de Miguel, 37 en total. Las 15 preguntas de Freddy, Tyrone y Miguel quedaron verificadas contra el repositorio en el cierre del 2026-11-17.
