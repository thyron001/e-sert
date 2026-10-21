---
semana: S1
persona: Tyrone
sesion: 1
titulo: Red vial OSM del Centro Histórico en SUMO
horas: 3-4
modulo: sumo
depende: []
entrega: [sumo/red/centro.net.xml, sumo/red/centro.poly.xml, sumo/red/construir_red.py]
evidencias: [s1_red-centro.png]
---
# S1 · Sesión 1 · Tyrone 🔵: Red vial OSM del Centro Histórico en SUMO

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` y `docs/EQUIPO.md`. Esta es la primera pieza del
proyecto: **todo lo demás corre sobre esta red**. Freddy (TraCI) y Pablo (trazas GPS de
SUMO) la van a usar la próxima semana, así que debe ser estable, reproducible y tener
veredas y cruces peatonales.

## SUMO en el contenedor
Esta sesión usa SUMO. Sigue la sección **"SUMO en el contenedor `van3twin`"** de `CLAUDE.md`:
- Antes de empezar, comprueba que el repo está clonado en `van3twin-docker/results/e-sert` y
  que `docker ps` muestra `van3twin`. Si no, avisa al usuario y no sigas con la parte de SUMO.
- `git` y la edición de archivos van en la computadora. `sumo`, `netconvert`, `randomTrips.py`
  y los scripts que importan `traci` o `sumolib` van dentro del contenedor:
  `docker exec -w /home/vanet/results/e-sert/<carpeta> van3twin bash -lc "<comando>"`.
- Es SUMO 1.12 con Python 3.10. Si algo de este prompt no existe en esa versión, adáptalo y
  anótalo en la bitácora.
- `sumo-gui` se abre en la pantalla virtual del contenedor y el usuario lo ve por VNC en
  `127.0.0.1:5901`. Las capturas se hacen con `traci.gui.screenshot` o `--screenshot`.

## Objetivo
Crear un script reproducible que descargue el OpenStreetMap del Centro Histórico de Cuenca y
lo convierta en una red SUMO lista para autos **y peatones**, con edificios como fondo
visual.

## Pasos
1. Crea `semanas/S1/Tyrone/codigo/sumo/red/construir_red.py`, que se ejecuta como
   `python construir_red.py [--bbox S,W,N,E] [--sin-descarga]`.
   - **Bbox por defecto:** `-2.9050,-79.0130,-2.8895,-78.9945`. Abarca del río Tomebamba
     (Calle Larga) a la Av. Gaspar Sangurima, y de la Av. Huayna Cápac a la calle Coronel
     Talbot.
   - Descarga el OSM con la API Overpass usando `requests` y guarda `centro.osm.xml`.
     Este archivo va en `.gitignore`, pero su suma SHA-256 queda en `red_info.json`.
   - Si existe `--sin-descarga`, usa el `.osm.xml` local.
2. Ejecuta `netconvert` desde Python con `subprocess` y estas opciones:
   - `--osm-files`
   - `--output.street-names true` y `--output.original-names true`
   - `--geometry.remove`, `--roundabouts.guess`, `--ramps.guess false`
   - `--junctions.join` y `--junctions.corner-detail 5`
   - `--tls.guess-signals --tls.discard-simple --tls.join`
   - `--sidewalks.guess --crossings.guess --walkingareas`
   - `--keep-edges.by-vclass passenger,pedestrian`
   - `--remove-edges.isolated` y `--proj.utm`
   - Salida: `centro.net.xml`. Guarda el comando completo en `red_info.json`.
3. Ejecuta `polyconvert` para los edificios (`--type-file
   $SUMO_HOME/data/typemap/osmPolyconvert.typ.xml`). Salida: `centro.poly.xml`.
4. Crea `sumo/centro_red.sumocfg`, que solo carga la red y los polígonos y no tiene
   demanda.
5. **Validación automática** al final del script:
   - Carga la red con `sumolib.net.readNet(..., withPedestrianConnections=True)`.
   - Imprime y guarda en `red_info.json`:
     - número de *edges* con `passenger` y número con `pedestrian`;
     - número de semáforos;
     - longitud total en km;
     - número de componentes conexas para autos (debe ser 1, o reportar cuántos *edges*
       quedan fuera).
   - Lanza `sumo -c centro_red.sumocfg --end 10`. Debe terminar sin errores.
6. **Prueba peatonal:** genera con `randomTrips.py --pedestrians` 20 peatones y comprueba con
   `sumo` que ninguno queda teletransportado (`--duration-log.statistics`).
7. **Gráfica de evidencia** con matplotlib y sumolib, en `evidencias/s1_red-centro.png`:
   - *edges* de autos en gris oscuro y veredas en gris claro;
   - semáforos como puntos rojos;
   - título con las cifras de `red_info.json`.
   - Si `sumo-gui` está disponible, guarda también `s1_red-centro-gui.png` con
     `--start --quit-on-end` y `traci.gui.screenshot`.

## Dónde escribir
Solo en `semanas/S1/Tyrone/codigo/sumo/red/` y `semanas/S1/Tyrone/evidencias/`. Añade
`*.osm.xml` al `.gitignore` de la raíz si aún no está.

## Hecho cuando
- [ ] `python construir_red.py` funciona desde cero en una máquina con SUMO y regenera
  todo.
- [ ] `sumo -c centro_red.sumocfg --end 10` termina con código 0.
- [ ] La red tiene veredas y cruces peatonales, y los 20 peatones de prueba llegan sin
  teletransporte.
- [ ] La red de autos es una sola componente conexa, o lo que falte está documentado.
- [ ] `red_info.json` existe y tiene las cifras.
- [ ] Existe la evidencia `s1_red-centro.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 1, Tyrone). En "Pedidos a
otros", avisa a Freddy y a Pablo de la ruta y de la proyección (UTM) de la red.
