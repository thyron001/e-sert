# Resumen S2 · Tyrone 🔵

## Sesión 1 · KPIs de la línea base (búsqueda, distancia, CO₂ y ocupación)

El módulo `kpis/` convierte las salidas XML de SUMO en los indicadores del proyecto, con
definiciones fijas escritas en el docstring de `kpis.py`. La búsqueda empieza al entrar a
300 m del destino (o al edge del puesto objetivo) y termina al estacionar.

- Línea base (1800 veh/h, 2 semillas, 2196 buscadores):
  - búsqueda media de **356 s** (IC 95 % 347–365);
  - **1280 m** recorridos;
  - **680 g de CO₂** por búsqueda.
- Ocupación media en la hora pico: 87,0 % y 87,7 %.
- Con radio 0 se reproducen exactamente los 230 y 246 s provisionales de S1-3. La diferencia
  es solo de definición.
- 13 tests con XML sintéticos; cada semilla se calcula en 5–8 s.

```bash
cd semanas/S2/Tyrone/codigo
python -m kpis.kpis --salidas sumo/salidas/base_1 --escenario base --semilla 1
```

![KPIs de la línea base](evidencias/s1_kpis-base.png)

## Sesión 2 · Visor web Leaflet y servidor WS de prueba

`visor/` es una página estática (sin build) con Leaflet 1.9 en canvas, alimentada por
`/ws/estado`:
- puestos en verde si tienen lugar y en rojo si están llenos;
- autos coloreados por estado, con borde grueso si tienen app;
- halo amarillo en el vehículo que sigue un teléfono espejo;
- panel con conteos, KPIs y estado de la conexión;
- reconexión automática (1, 2, 4… hasta 30 s).

- `grabar_snapshots.py` (TraCI) grabó 15 min de hora pico: 900 snapshots que validan contra
  el contrato. En git va una muestra de 60.
- `servidor_prueba.py` los reproduce y manda los KPIs de S2-1. El visor funciona también
  servido por el backend real de Freddy en `/visor/`, con el WS del mismo origen.
- 54 FPS con ~1200 marcadores, 169 cambios de color de puestos en 15 min y 9 tests.

```bash
cd semanas/S2/Tyrone/codigo
python -m visor.servidor_prueba --puerto 8001 --velocidad 5   # http://localhost:8001/visor/
```

![Visor Leaflet](evidencias/s2_visor-leaflet.png)
