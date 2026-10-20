---
semana: S1
persona: Pablo
sesion: 2
titulo: Remuestreo, ventanas y características
horas: 3-4
modulo: ia
depende: [S1-Pablo-1]
entrega: [ia/ventanas.py, ia/caracteristicas.py, ia/datos/procesados/ventanas_geolife.parquet, ia/tests/test_ventanas.py]
evidencias: [s2_caracteristicas-por-clase.png]
---
# S1 · Sesión 2 · Pablo 🟢: Remuestreo, ventanas y características

## Contexto
Lee `CLAUDE.md` y `docs/CONTRATO.md` (sección 2: ventanas de 30 s a 1 Hz con paso de 5 s).
**El mismo código de ventanas y características se usará en entrenamiento y en inferencia
en vivo** (TraCI y teléfonos reales). Por eso debe ser una librería limpia, sin nada
específico de GeoLife.

## Objetivo
Convertir trazas GPS de cualquier fuente (GeoLife, SUMO o teléfono) en ventanas etiquetadas
con un vector de características robusto, y derivar la clase `quieto`, que GeoLife no trae.

## Pasos
1. `ia/ventanas.py`:
   - `remuestrear(df, hz=1, max_hueco_s=10)`: interpola lat/lon linealmente dentro de cada
     segmento y **parte el segmento** cuando hay huecos mayores que `max_hueco_s`. No inventa
     datos en huecos largos.
   - `ventanear(df, largo_s=30, paso_s=5, min_cobertura=0.8)`: genera ventanas. Descarta las
     que tengan menos del 80 % de las muestras esperadas. La etiqueta es la **mayoritaria**
     de la ventana, y se descartan las ventanas con menos del 80 % de pureza.
   - **Derivar `quieto`:** una ventana etiquetada `a_pie` o `vehiculo` con velocidad mediana
     menor a 0,3 m/s y desplazamiento neto menor a 10 m se reetiqueta como `quieto`.
     Documenta la regla y cuenta cuántas ventanas cambian.
2. `ia/caracteristicas.py`, `extraer(ventana) -> dict`, con unas 18 características:
   - velocidad: media, mediana, p10, p85, máx y desviación estándar;
   - aceleración: media absoluta y desviación estándar; *jerk* medio absoluto;
   - rumbo: tasa media de cambio de rumbo (°/s) y proporción de giros mayores de 30°;
   - `prop_detenido` (velocidad menor a 0,5 m/s) y `prop_lento` (0,5–2 m/s);
   - `rectitud` = desplazamiento neto / distancia recorrida;
   - `distancia_total`;
   - `precision_media`, con valor NaN permitido; el modelo lo manejará;
   - número de "paradas y arranques".

   Todas deben ser **robustas al ruido GPS**: calcula la velocidad sobre una posición
   suavizada (mediana móvil de 3 muestras).
3. `ia/datos/construir_ventanas.py`: aplica todo a GeoLife y guarda
   `ventanas_geolife.parquet` con `usuario_id`, `fuente`, `t_inicio`, las características y
   `modo_real`. Paraleliza por usuario con `joblib.Parallel`.
4. **Tests** (`ia/tests/test_ventanas.py`) con trazas sintéticas:
   - línea recta a 1,4 m/s → `a_pie`, velocidad media ≈ 1,4 ± 0,1;
   - un punto fijo con ruido de σ=5 m → clase `quieto` (prueba la regla) y `rectitud` baja;
   - 10 m/s constantes → velocidad ≈ 10;
   - un hueco de 20 s parte la ventana;
   - el resultado no depende del orden de las filas.
5. **Evidencia** `evidencias/s2_caracteristicas-por-clase.png`: cuadrícula de *boxplots* (6
   características clave × 3 clases) y, en el título, el número de ventanas por clase.

## Dónde escribir
`semanas/S1/Pablo/codigo/ia/` y `evidencias/`.

## Hecho cuando
- [ ] `python -m ia.datos.construir_ventanas` genera el parquet con las 3 clases.
- [ ] Cada clase tiene al menos 2 000 ventanas, o el número real queda documentado.
- [ ] Los tests pasan y `extraer()` funciona igual con una ventana de SUMO (usa la muestra
  de Freddy si está en su rama; si no, una sintética).
- [ ] La regla de `quieto` está documentada en `ia/README.md`.
- [ ] Existe la evidencia PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 2, Pablo).
