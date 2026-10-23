# Datos caseros · Miguel 🔴

Grabaciones caseras **opcionales** (caminando, quieto o en auto, donde sea, **sin ir al Centro**)
hechas con la pestaña **Grabador** de la app. Pablo las puede usar como validación extra del
clasificador. La evaluación principal sigue siendo GeoLife más los escenarios de SUMO.

## Formato

`<fecha>_<persona>_<telefono>.csv`:
- Primero van las 7 columnas del contrato, en orden: `usuario_id,t,lat,lon,precision_m,velocidad_mps,modo_real`.
- Después, las columnas extra `escenario,telefono,persona`.
- `usuario_id` sigue el formato `casa_<persona>_<n>`.
- `t` está en segundos Unix UTC.
- La etiqueta `vehiculo_lento` se escribe como `modo_real=vehiculo` con `escenario=trafico_lento`.
- `<base>_acel.csv` guarda el acelerómetro a 10 Hz (`t,ax,ay,az`, en g) por si se usa luego.
- En iOS también queda `<base>_meta.json`, con los instantes exactos de los cambios de etiqueta.

## Privacidad

Antes de subir una grabación al repo, **anonimízala**: la traza se traslada para que empiece
en el Parque Calderón, y se conservan distancias, tiempos, velocidades y etiquetas. El
original queda solo en la computadora de quien grabó.

```bash
python herramientas/anonimizar_grabacion.py ~/mi_grabacion.csv --salida grabaciones/<base>_anon.csv
```

## Herramientas

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python herramientas/graficar_grabacion.py grabaciones/<base>.csv --salida figura.png
.venv/bin/python herramientas/unir_capturas.py salida.png "rótulo=captura1.jpeg" "rótulo=captura2.jpeg"
```

- `graficar_grabacion.py` valida el CSV contra el contrato y sale con código 1 si hay errores. Después dibuja la traza coloreada por etiqueta y la velocidad en el tiempo, e informa la duración por etiqueta, la precisión media y los cambios de etiqueta.
- `ejemplos/sintetica_muestra.csv` es una grabación sintética (5 min a pie y 5 min quieto) para probar el script. Se genera con `SALIDA_CSV=1 npx tsx src/sensores/pruebas/formato.prueba.ts`, desde `app/`.

## Grabaciones

| Archivo | Teléfono | Contenido |
|---|---|---|
| `grabaciones/2026-10-22T21-55-49_miguel_android_anon.csv` (+ `_acel.csv`) | Android real | 5:53 a pie y 5:17 quieto, con el cambio en caliente. Anonimizada |
| `grabaciones/2026-10-22T21-27-10_miguel_ios.csv` (+ `_meta.json`) | Simulador de iPhone | 3:01 a pie y 2:00 quieto, con ubicación simulada. Prueba técnica; no sirve como dato real |
