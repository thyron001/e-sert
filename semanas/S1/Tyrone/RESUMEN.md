# Resumen S1 · Tyrone 🔵

## Sesión 1 · Red vial OSM del Centro Histórico en SUMO

`construir_red.py` descarga el OSM del Centro Histórico (Overpass), genera la red SUMO para
autos y peatones (veredas, cruces, semáforos, UTM 17S) y los edificios de fondo. Después la
valida automáticamente.

- 985 edges de autos y 1824 peatonales, 775 cruces, 129 semáforos y 90,66 km.
- La red de autos es una sola componente fuertemente conexa, tras podar 160 edges del borde.
- `sumo --end 10` termina con código 0, y los 20 peatones de prueba llegan sin teletransporte.

Comando:

```bash
docker exec -w /home/vanet/results/e-sert/semanas/S1/Tyrone/codigo/sumo/red van3twin bash -lc "python3 construir_red.py"
```

![Red del Centro](evidencias/s1_red-centro.png)

![Edges podados](evidencias/s1_componentes-podadas.png)

![Captura de sumo-gui](evidencias/s1_red-centro-gui.png)

Explicación: [explicaciones/s1_explicacion.pdf](explicaciones/s1_explicacion.pdf)

## Sesión 2 · Generación automática de puestos SERT (parkingArea)

`generar_parkingareas.py` coloca los puestos SERT sobre las calles tarifadas, con las reglas
de `calles_sert.yaml`: tipos de vía, avenidas excluidas, 5,5 m por puesto, 8 m de margen en
las esquinas y recorte a la bbox del Centro.

- 610 `parkingArea` y 6194 puestos en 103 calles.
- Salidas: `parqueos.add.xml` para SUMO y `puestos.csv` para el contrato, con IDs `pa_<edge>_0`.
- SUMO los carga sin advertencias, los 10 autos de prueba estacionan y la salida es determinista.

Comando:

```bash
docker exec -w /home/vanet/results/e-sert/semanas/S1/Tyrone/codigo/sumo/parqueos van3twin bash -lc "python3 generar_parkingareas.py"
```

![Puestos SERT](evidencias/s2_puestos-sert.png)

Explicación: [explicaciones/s2_explicacion.pdf](explicaciones/s2_explicacion.pdf)

## Sesión 3 · Demanda y búsqueda a ciegas (línea base)

`generar_demanda.py` crea la demanda de hora pico con tres clases de autos:

- **Buscadores:** van a 12 destinos reales de `destinos.csv`, elegidos por peso, con estadía lognormal de 45 min.
- **Tráfico de paso:** el 40 % de las llegadas, que cruzan sin estacionar.
- **Autos de fondo:** ocupan el 80 % de los puestos desde el inicio, como larga estadía.

`rerouters.add.xml` modela la búsqueda a ciegas: alternativas a menos de 400 m, invisibles hasta llegar.

- **Calibración:** `--veh-hora` = **1800** da una ocupación media en la hora pico de 87,0 % y 87,7 % (semillas 1 y 2).
- **Teletransportes:** 0 de unos 7000 vehículos.
- **Búsqueda:** media de 230 y 246 s; mediana de 188 y 193 s.
- **`con_app`:** cada vehículo lleva `<param key="con_app" value="0"/>`, que es el interruptor de Freddy en S2.

Comandos:

```bash
docker exec -w /home/vanet/results/e-sert/semanas/S1/Tyrone/codigo/sumo/demanda van3twin bash -lc "python3 generar_demanda.py --semilla 1 && python3 correr_base.py --semillas 1 2"
```

![Escenario base en sumo-gui](evidencias/s3_escenario-base.png)

![Tiempo de búsqueda](evidencias/s3_busqueda-histograma.png)

![Ocupación](evidencias/s3_ocupacion-base.png)

Explicación: [explicaciones/s3_explicacion.pdf](explicaciones/s3_explicacion.pdf)
