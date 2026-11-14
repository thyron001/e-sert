## Escenario de simulación y resultados experimentales

<!-- Plantilla: las cifras de resultados son marcadores que se rellenan desde
     kpis/resultados/final/resumen.csv con
     demo/.venv/bin/python demo/presentacion/generar_diapositivas.py --plantilla informe/tyrone.plantilla.md --salida informe/tyrone.md
     No se edita tyrone.md a mano. -->

Esta sección describe el escenario de SUMO sobre el que corre todo el sistema, el diseño de los
experimentos y lo que midieron. La pregunta es la del proyecto: si una parte de los conductores
que buscan parqueo en la zona SERT del Centro Histórico de Cuenca usa la app, ¿cuánto baja el
tiempo, la distancia y el CO₂ de la búsqueda, y qué tan fiable es el mapa de ocupación que la app
construye a partir del clasificador de movimiento?

### Escenario SUMO

**Red.** La red se construyó con `netconvert` a partir de OpenStreetMap, en el recuadro
`[-2,905; -79,013; -2,8895; -78,9945]`, que cubre el Centro Histórico y sus accesos. Tiene 985
aristas para autos, 1 824 peatonales, 775 cruces, 129 semáforos y 90,66 km de vías.
<!-- fuente: sumo/red/red_info.json -->
Se conservaron las aceras y los cruces peatonales porque el conductor, al bajarse, camina hasta su
destino y vuelve, y ese recorrido a pie es el que observa el clasificador.

**Puestos.** Los puestos SERT se generaron como `parkingArea` sobre las calles tarifadas
(residenciales, terciarias y secundarias con nombre, del lado derecho), con `5,5 m` por puesto y
`8 m` libres en cada esquina. Resultan 610 áreas con 6 194 puestos en 103 calles, una media de
10,15 puestos por área. <!-- fuente: sumo/parqueos/parqueos_info.json -->
Su identificador (`pa_<arista>_0`) es el mismo en SUMO, en el backend y en la app.

**Demanda.** La demanda de hora pico tiene tres componentes:

- autos de fondo que ocupan el `80 %` de los puestos desde el inicio, como estadía larga;
- tráfico de paso (`40 %` de las llegadas), que cruza la zona sin estacionar;
- buscadores, que van a 12 destinos reales (mercados, plazas e iglesias) con una estadía lognormal
  de `45 min` y que, si su puesto está lleno, siguen buscando con los `rerouter` de parqueo de SUMO.

**Calibración.** La tasa de llegadas `--veh-hora` se calibró para que la ocupación media en la hora
pico quede entre `85 %` y `95 %`, el rango en que buscar parqueo cuesta. Con `1800` veh/h, la
ocupación media de la línea base es de {{ciegas.ocupacion_media|1|pct}} % (IC 95 %
[{{ciegas.ocupacion_ic_lo|1|pct}}; {{ciegas.ocupacion_ic_hi|1|pct}}] %).
<!-- fuente: kpis/resultados/final/resumen.csv -->
Cada corrida simula `75 min`: `15 min` de calentamiento y `60 min` de hora pico. Solo cuentan los
buscadores que estacionan dentro de la hora medida.

**Definiciones.** La búsqueda empieza cuando el auto entra a `300 m` de su destino (o a la arista
de su puesto objetivo) y termina al estacionar. La distancia de búsqueda es lo recorrido en ese
lapso, y el CO₂ de búsqueda, lo que SUMO (modelo HBEFA) atribuye a esos pasos. Estas definiciones
están fijas en `kpis/kpis.py` desde S2 y no cambiaron.

### Diseño experimental

La matriz cruza la penetración de la app {`0`, `20`, `50`, `80`} % con dos clasificadores de
movimiento, el umbral de velocidad y el `rf_final` de Pablo (bosque aleatorio congelado), y cinco
semillas. El `0 %` es la búsqueda a ciegas y corre una vez por semilla, lo que da 35 corridas.

- **Números aleatorios comunes.** La demanda depende solo de la semilla. Quién tiene app sale de un
  sorteo aparte (`default_rng([semilla, 7])`), así que los usuarios con app al `20 %` también la
  tienen al `50 %` y al `80 %`. Entre escenarios de una misma semilla salen los mismos autos a la
  misma hora; la única diferencia es la app.
- **Sistema completo.** Cada corrida usa el controlador TraCI de Freddy: guiado al puesto, peatones,
  emulador GPS con ruido, sesiones de cobro y KPIs del sistema. También usa la inferencia de Pablo,
  sin *mocks*.
- **Réplica.** La réplica independiente es la semilla. Los KPIs por vehículo se resumen con un IC
  95 % *bootstrap* jerárquico (se remuestrean semillas y, dentro de cada una, vehículos; 10 000
  remuestreos). Las falsas liberaciones usan un IC de Wilson, y los demás KPIs de sistema, t de
  Student entre semillas. Cada escenario se compara con la búsqueda a ciegas con Mann-Whitney U.
- **Sensibilidad (oráculo).** Cinco corridas más al `50 %` guían con la ocupación real de SUMO en
  lugar del mapa del sistema. No es algo que la app pueda hacer: es la cota superior de lo que
  ganaría con información perfecta de ocupación.

Las corridas de las semillas 1–3 se reutilizan de la matriz de S3, porque su configuración, red,
demanda y modelo tienen el mismo hash. `kpis/resultados/final/manifiesto.json` guarda el commit, la
versión de SUMO (1.12), los SHA-256 del modelo y de cada demanda, y los comandos para repetir todo.

### Resultados

*KPIs de búsqueda por escenario (media e IC 95 %; Δ frente a la búsqueda a ciegas; p de Mann-Whitney U).*

{{tabla:KPIs de búsqueda}}

<!-- fuente: kpis/resultados/final/resumen.md -->

![](figuras/tyrone/f01_kpis_vs_penetracion.png)
*KPIs de búsqueda y ocupación frente a la penetración de la app, con el umbral, con `rf_final` y con el oráculo al 50 %.*

**Búsqueda con el sistema real.**
- La búsqueda a ciegas dura en media {{ciegas.busqueda_media|0}} s (IC 95 %
  [{{ciegas.busqueda_ic_lo|0}}; {{ciegas.busqueda_ic_hi|0}}] s) y recorre {{ciegas.distancia_media|0}} m.
  <!-- fuente: kpis/resultados/final/resumen.csv -->
- Con `rf_final`, el cambio frente a la búsqueda a ciegas es de {{p20_rf_final.busqueda_cambio_pct|1|sig}} %,
  {{p50_rf_final.busqueda_cambio_pct|1|sig}} % y {{p80_rf_final.busqueda_cambio_pct|1|sig}} % al `20`, `50` y
  `80 %`. <!-- fuente: kpis/resultados/final/resumen.csv -->
- La distancia y el CO₂ siguen el mismo patrón: al `50 %`, {{p50_rf_final.distancia_cambio_pct|1|sig}} % y
  {{p50_rf_final.co2_cambio_pct|1|sig}} %. <!-- fuente: kpis/resultados/final/resumen.csv -->

Ninguna de estas variaciones es una mejora: son de pocos puntos porcentuales y los IC de los
escenarios se solapan con el de la línea base. Si algo, la búsqueda tiende a subir con la
penetración: al `80 %` la diferencia con la búsqueda a ciegas tiene p = {{p80_rf_final.busqueda_mw_p|3}}
(Mann-Whitney U). <!-- fuente: kpis/resultados/final/resumen.csv -->

Los autos con app no ganan frente a los que no la tienen. Al `50 %` buscan en media
{{p50_rf_final.busqueda_con_app_media|0}} s, frente a {{p50_rf_final.busqueda_sin_app_media|0}} s
de los demás en la misma corrida. <!-- fuente: kpis/resultados/final/resumen.csv -->

**El clasificador no cambia la búsqueda.** A igual penetración y semilla, el umbral y `rf_final`
producen exactamente la misma búsqueda, porque ninguna decisión del guiado cambia entre ellos.

**Por qué el guiado no ayuda.**
- El guiado recomienda el puesto libre más cercano al destino según el **mapa del sistema**.
- Ese mapa solo conoce las sesiones de los usuarios de la app. Al `50 %` y con
  {{p50_rf_final.ocupacion_media|1|pct}} % de ocupación real, casi todos los puestos ocupados lo están por
  autos sin app, que el mapa no ve. <!-- fuente: kpis/resultados/final/resumen.csv -->
- El guiado manda al conductor a un puesto que el sistema cree libre pero que está lleno; al
  llegar, busca como cualquier otro.
- Por la misma razón, la precisión del mapa queda en {{p50_rf_final.precision_mapa|1|pct}} % al `50 %`.
  <!-- fuente: kpis/resultados/final/resumen.csv -->
- Una falsa liberación suma un libre en un mapa que ya ve ese puesto libre, así que nunca cambia una
  recomendación.

**Cota superior: el oráculo.** Con la ocupación real, el guiado sí reduce la búsqueda:
- al `50 %`, la media baja a {{p50_oraculo.busqueda_media|0}} s, un cambio de
  {{p50_oraculo.busqueda_cambio_pct|1|sig}} % frente a la búsqueda a ciegas;
- los autos con app buscan {{p50_oraculo.busqueda_con_app_media|0}} s y los sin app
  {{p50_oraculo.busqueda_sin_app_media|0}} s;
- el CO₂ de búsqueda por vehículo cambia {{p50_oraculo.co2_cambio_pct|1|sig}} %.

<!-- fuente: kpis/resultados/final/resumen.csv -->

La diferencia entre el oráculo y el sistema real mide el valor de la información de ocupación que
falta, no la calidad del clasificador.

*Umbral frente a `rf_final` por penetración: falsas liberaciones (Wilson 95 %), retardo de cierre, error de facturación y precisión del mapa.*

{{tabla:Umbral frente a rf_final}}

<!-- fuente: kpis/resultados/final/resumen.md -->

![](figuras/tyrone/f04_falsas_liberaciones.png)
*Falsas liberaciones por 100 sesiones con el umbral y con `rf_final` (IC de Wilson 95 %).*

**El clasificador sí importa para el cobro.**
- Con el umbral, {{p50_umbral.falsas_100|1}} de cada 100 sesiones se cierran antes de que el
  conductor vuelva (IC de Wilson [{{p50_umbral.falsas_100_wilson_lo|1}};
  {{p50_umbral.falsas_100_wilson_hi|1}}] al `50 %`). Con `rf_final` son
  {{p50_rf_final.falsas_100|1}} ([{{p50_rf_final.falsas_100_wilson_lo|1}};
  {{p50_rf_final.falsas_100_wilson_hi|1}}]). <!-- fuente: kpis/resultados/final/resumen.csv -->
- El umbral confunde caminar despacio por el centro con el inicio de la conducción. Cada falsa
  liberación cierra la sesión y cobra de menos: el error de facturación medio es de
  {{p50_umbral.error_fact_usd|3}} USD por sesión con el umbral, frente a
  {{p50_rf_final.error_fact_usd|3}} USD con `rf_final`.
  <!-- fuente: kpis/resultados/final/resumen.csv -->
- El retardo mediano de cierre con `rf_final` es de {{p50_rf_final.retardo_cierre_s|1}} s desde que
  el conductor arranca. <!-- fuente: kpis/resultados/final/resumen.csv -->

![](figuras/tyrone/f05_precision_mapa.png)
*Precisión del mapa de ocupación frente a la penetración de la app.*

### Controles de cordura

{{seccion:Controles de cordura}}

<!-- fuente: kpis/resultados/final/controles.json -->

### Discusión

Los resultados separan dos preguntas que el proyecto había juntado.

**¿El clasificador detecta bien la llegada y la salida?** Sí. `rf_final` lleva las falsas
liberaciones prácticamente a cero, y con ellas el error de cobro. El cobro por tiempo real frente a
la tarjeta SERT solo tiene sentido con un clasificador así: con el umbral, la mayoría de las
sesiones se cerrarían antes de tiempo.

**¿La app reduce la búsqueda?** No con la información que tiene. Un mapa construido solo con las
sesiones de sus usuarios no conoce la ocupación real cuando la zona está casi llena, que es justo
cuando buscar cuesta. El oráculo muestra que el guiado funcionaría con información completa. Para
acercarse a esa cota hace falta una fuente de ocupación que no dependa de los usuarios, por ejemplo
los registros de la propia tarjeta SERT o sensores en las calles más demandadas. Queda como trabajo
futuro, fuera del alcance acordado.

### Limitaciones

- **Todo es simulado.** No hay pruebas de campo; el GPS es un modelo de ruido sobre las
  trayectorias de SUMO y el teléfono de la demo solo refleja un auto simulado.
- **El clasificador** se entrenó con GeoLife (Pekín) y no con trazas de Cuenca. Su desempeño en
  calles empedradas y estrechas puede ser distinto.
- **Un solo escenario temporal:** una hora pico, una red recortada al Centro Histórico y una tasa de
  llegadas calibrada. No se modelan días ni horarios distintos.
- **Cinco semillas por escenario:** los IC jerárquicos son anchos frente a diferencias de pocos
  puntos porcentuales.
- **El oráculo no es implementable:** solo acota el beneficio posible.
