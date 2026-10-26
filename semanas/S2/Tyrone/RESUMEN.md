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
