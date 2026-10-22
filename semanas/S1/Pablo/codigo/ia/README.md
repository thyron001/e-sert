# Módulo IA — Clasificador de movimiento

Clasificador de movimiento GPS para el proyecto e-sert. Distingue tres clases:
`a_pie`, `quieto` y `vehiculo`.

## Regla de derivación de `quieto`

GeoLife no etiqueta la clase `quieto`. Se deriva automáticamente durante el
ventaneo con la siguiente regla:

> Una ventana originalmente etiquetada `a_pie` o `vehiculo` se reetiqueta como
> `quieto` si cumple **ambas** condiciones:
>
> 1. **Velocidad efectiva < 0,3 m/s**: calculada como desplazamiento neto
>    (haversine entre el primer y el último punto) dividido por la duración de
>    la ventana. Esto es más robusto al ruido GPS que la mediana de velocidades
>    instantáneas.
> 2. **Desplazamiento neto < 10 m**: el dispositivo no se movió
>    significativamente durante la ventana.

**Por qué esta regla:**
- Un peatón detenido en un semáforo o un auto en un atasco tienen GPS con ruido
  que genera velocidades instantáneas aparentes de 1–5 m/s. La velocidad
  efectiva (desplazamiento/duración) filtra ese ruido.
- El umbral de 0,3 m/s equivale a ~1 km/h, muy por debajo de una caminata
  lenta (~3,5 km/h).
- El desplazamiento de 10 m descarta ventanas donde el dispositivo se movió
  poco pero de forma sostenida.

## Estructura

```
ia/
├── ventanas.py           # remuestrear() y ventanear() — librería genérica
├── caracteristicas.py    # extraer(ventana) → dict con ~18 features
├── datos/
│   ├── descargar_geolife.py
│   ├── ingesta_geolife.py
│   ├── construir_ventanas.py
│   ├── evidencias_geolife.py
│   ├── geolife_info.json
│   └── procesados/         # parquets (gitignored)
├── tests/
│   ├── test_ingesta.py
│   └── test_ventanas.py
└── requirements.txt
```

## Ventana y características

- **Ventana:** 30 s de GPS a 1 Hz, paso de 5 s, cobertura mínima 80%, pureza 80%.
- **Características (18):** vel_media, vel_mediana, vel_p10, vel_p85, vel_max,
  vel_std, acc_media_abs, acc_std, jerk_medio_abs, tasa_rumbo_media,
  prop_giros_30, prop_detenido, prop_lento, rectitud, distancia_total,
  precision_media, n_paradas_arranques, desplazamiento_neto.
