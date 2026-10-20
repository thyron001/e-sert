---
semana: S1
persona: Tyrone
sesion: 3
titulo: Demanda y búsqueda a ciegas (línea base)
horas: 3-4
modulo: sumo
depende: [S1-Tyrone-2]
entrega: [sumo/demanda/generar_demanda.py, sumo/demanda/destinos.csv, sumo/centro_base.sumocfg]
evidencias: [s3_escenario-base.png, s3_busqueda-histograma.png]
---
# S1 · Sesión 3 · Tyrone 🔵: Demanda y búsqueda a ciegas (línea base)

## Contexto
Lee `CLAUDE.md` y `docs/CONTEXTO.md` (en especial la sección de escenarios). La **línea base**
es lo que demuestra que el sistema mejora algo: son los mismos autos llegando al Centro, pero
buscando parqueo a ciegas (dan vueltas hasta encontrar). Sin línea base no hay KPIs.

## Objetivo
Generar una demanda realista de hora pico, con autos que buscan parqueo a ciegas, y tener el
escenario base corriendo y produciendo las salidas que luego usarán los KPIs.

## Pasos
1. Crea `sumo/demanda/destinos.csv` con las columnas `nombre,lat,lon,peso`. Usa unos 12
   destinos reales, con pesos por atractivo:
   - Parque Calderón (peso 3)
   - Catedral Nueva
   - Mercado 10 de Agosto (2)
   - Mercado 9 de Octubre (2)
   - Plaza San Francisco
   - Municipio (Bolívar y Borrero)
   - Plaza de las Flores
   - Museo Pumapungo (borde sur)
   - Plaza del Otorongo
   - Santo Domingo
   - San Sebastián
   - Banco/agencia en la Gran Colombia

   Busca las coordenadas en OSM y documenta la fuente en el CSV.
2. Crea `sumo/demanda/generar_demanda.py`, con los parámetros `--veh-hora`, `--porc-paso`,
   `--duracion-s` y `--semilla`:
   - **Entradas:** *edges* del borde de la red que entran a la zona. Detéctalos como los
     *edges* sin predecesores dentro de la red o en el perímetro del bbox.
   - **Autos que buscan parqueo:**
     - destino elegido según el peso;
     - parada en el `parkingArea` más cercano al destino;
     - duración de la estadía con distribución lognormal (media de 45 min, recortada a
       10–120 min);
     - después salen por un *edge* de borde.
   - **Tráfico de paso** (`--porc-paso`, 40 % por defecto): cruzan sin estacionar, para
     tener una congestión realista.
   - Llegadas Poisson con la tasa `--veh-hora`. Por defecto, 600 autos/h durante 1 h, más un
     *warm-up* de 15 min.
   - Usa `vType` `auto` con `emissionClass="HBEFA4/PC_petrol_Euro-4"` y añade
     `<param key="con_app" value="0"/>` a cada vehículo. Así Freddy lo cambia en S2.
3. **Búsqueda a ciegas:** genera `sumo/demanda/rerouters.add.xml`. Para cada `parkingArea`,
   añade un `<rerouter>` con `<parkingAreaReroute>` que liste como alternativas los
   `parkingArea` a menos de 400 m, con `visible="false"`: el conductor solo ve si hay lugar
   al llegar. Ajusta los parámetros `parking.distance.weight` y `parking.probability.weight`
   para que el comportamiento sea "busca lo más cerca del destino".
4. Crea `sumo/centro_base.sumocfg`, que carga la red, los parqueos, la demanda y los
   rerouters, con:
   - `--device.emissions.probability 1`
   - `--tripinfo-output`, `--stop-output`, `--emission-output` (con `--device.emissions.period 10`) y `--statistic-output`
   - `--seed`
   - salidas en `sumo/salidas/<escenario>_<semilla>/`, en `.gitignore`.
5. Corre 1 h + *warm-up* con 2 semillas. **Calibra** `--veh-hora` hasta que la ocupación
   promedio de los puestos en la hora pico quede entre **85 y 95 %**. Por debajo de eso nadie
   busca y la mejora no se vería. Documenta el valor elegido.
6. Calcula rápido, con un script provisional, el **tiempo de búsqueda** por vehículo: desde
   que llega por primera vez a su `parkingArea` objetivo hasta que estaciona (usa
   `stop-output` y `vehroute` o los reroutes). El cálculo formal es de S2.
7. **Evidencias:**
   - `s3_escenario-base.png`: captura de `sumo-gui` en la hora pico o, si no hay GUI, mapa
     de calor de la ocupación.
   - `s3_busqueda-histograma.png`: histograma del tiempo de búsqueda de las 2 semillas.

## Dónde escribir
`semanas/S1/Tyrone/codigo/sumo/demanda/`, `semanas/S1/Tyrone/codigo/sumo/*.sumocfg` y
`evidencias/`.

## Hecho cuando
- [ ] `python generar_demanda.py --semilla 1` y `sumo -c centro_base.sumocfg` corren 75 min
  simulados sin errores.
- [ ] Menos del 1 % de los vehículos tiene teletransportes.
- [ ] La ocupación en la hora pico está entre 85 y 95 %, con el valor de `--veh-hora`
  documentado.
- [ ] Cada vehículo lleva `param con_app` y hay al menos 2 semillas corridas.
- [ ] Existen las dos evidencias PNG.
- [ ] El PDF semanal está generado (paso 6 del protocolo).

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 3, Tyrone), **incluido el PDF
semanal**. En "Pedidos a otros": @Freddy, el `param con_app` es tu interruptor para guiar a
un vehículo.
