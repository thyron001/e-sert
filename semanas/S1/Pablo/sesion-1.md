---
semana: S1
persona: Pablo
sesion: 1
titulo: Ingesta del dataset GeoLife
horas: 3-4
modulo: ia
depende: []
entrega: [ia/datos/descargar_geolife.py, ia/datos/ingesta_geolife.py, ia/datos/procesados/geolife_etiquetado.parquet, ia/datos/geolife_info.json]
evidencias: [s1_geolife-horas-por-modo.png, s1_geolife-trayectorias.png]
---
# S1 · Sesión 1 · Pablo 🟢: Ingesta del dataset GeoLife

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (sección IA) y `docs/CONTRATO.md` (secciones 2 y 7). El
clasificador de movimiento es **la IA evaluable del proyecto**. Distingue `a_pie`, `quieto` y
`vehiculo` con ventanas de GPS, y evita las *falsas liberaciones* de puesto. GeoLife
(Microsoft Research) da trazas GPS reales etiquetadas por modo de transporte. Es la base del
entrenamiento, junto con las trazas de SUMO (Freddy) y las grabaciones de Cuenca (Miguel).

## Objetivo
Descargar GeoLife 1.3, quedarte solo con las trayectorias etiquetadas, mapear los modos a las
clases del proyecto y dejar un archivo limpio en el formato CSV/Parquet del contrato.

## Pasos
1. `ia/datos/descargar_geolife.py`: descarga el ZIP oficial de "Geolife Trajectories 1.3"
   desde el sitio de Microsoft Research (unos 1,6 GB):
   - muestra una barra de progreso con `tqdm`;
   - verifica el tamaño y lo extrae a `ia/datos/crudos/`, que está en `.gitignore`;
   - es idempotente: si ya existe, no descarga.
   - **Lanza la descarga en segundo plano** y avanza con el paso 2 sobre un usuario de
     prueba mientras tanto.
2. `ia/datos/ingesta_geolife.py`:
   - Recorre solo los usuarios con `labels.txt` (unos 69).
   - Lee cada `.plt`: salta las 6 líneas de cabecera; las columnas son
     `lat, lon, 0, alt_ft, dias, fecha, hora`.
   - Convierte la hora a UTC. GeoLife viene en GMT; documéntalo.
   - Une cada punto con el intervalo de `labels.txt` (`Start Time`, `End Time`,
     `Transportation Mode`). Hazlo con `pd.merge_asof` o con un índice por intervalos;
     **evita bucles O(n²)**.
   - Mapea los modos:
     - `walk` → `a_pie`;
     - `car`, `taxi` y `bus` → `vehiculo`;
     - `bike`, `train`, `subway`, `airplane`, `boat`, `run` y `motorcycle` → se descartan
       (anota cuántos puntos se pierden).
   - Calcula la `velocidad_mps` por diferencia *haversine* entre puntos consecutivos del
     mismo segmento.
   - Columnas de salida según el contrato: `usuario_id,t,lat,lon,precision_m,velocidad_mps,modo_real`,
     más `segmento_id` y `fuente="geolife"`.
     - `usuario_id` = `geolife_<id>`.
     - `t` = segundos Unix.
     - `precision_m` vacía, porque GeoLife no la trae.
   - Filtra puntos imposibles: saltos de más de 50 m/s y coordenadas fuera de rango.
   - Guarda `ia/datos/procesados/geolife_etiquetado.parquet` (en `.gitignore`) y una muestra
     de 10 000 filas en `geolife_muestra.csv`, que sí va al repo.
3. Crea `ia/datos/geolife_info.json` con:
   - puntos, segmentos, usuarios y horas por clase;
   - la distribución de intervalos de muestreo (mediana, p90);
   - los puntos descartados por motivo.
4. **Tests** (`ia/tests/test_ingesta.py`) con un mini `.plt` y `labels.txt` sintéticos en
   `ia/tests/datos/`:
   - el mapeo de modos;
   - la unión con los intervalos (un punto en el borde del intervalo);
   - el filtro de saltos.
5. **Evidencias:**
   - `s1_geolife-horas-por-modo.png`: barras de horas por clase del proyecto, con el detalle
     del modo original apilado.
   - `s1_geolife-trayectorias.png`: 30 segmentos al azar, coloreados por clase, sobre
     lat/lon.

## Dónde escribir
`semanas/S1/Pablo/codigo/ia/` y `semanas/S1/Pablo/evidencias/`. Los datos crudos y los
parquet grandes **nunca** van a git.

## Hecho cuando
- [ ] La descarga y la ingesta corren de punta a punta, y repetir no duplica nada.
- [ ] El parquet tiene las columnas del contrato, y `geolife_info.json` tiene las horas por
  clase.
- [ ] Los tests pasan.
- [ ] La muestra CSV está en el repo y el parquet no.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 1, Pablo). Anota en
"Decisiones" por qué `bus` cuenta como `vehiculo`.
