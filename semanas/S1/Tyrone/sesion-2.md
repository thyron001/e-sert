---
semana: S1
persona: Tyrone
sesion: 2
titulo: Generación automática de puestos SERT (parkingArea)
horas: 3-4
modulo: sumo
depende: [S1-Tyrone-1]
entrega: [sumo/parqueos/generar_parkingareas.py, sumo/parqueos/calles_sert.yaml, sumo/parqueos/parqueos.add.xml, sumo/parqueos/puestos.csv]
evidencias: [s2_puestos-sert.png]
---
# S1 · Sesión 2 · Tyrone 🔵: Generación automática de puestos SERT (`parkingArea`)

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` y `docs/CONTRATO.md` (sección 1, identificadores).
Los puestos SERT **no se digitalizan a mano**: se generan con un script sobre los bordes de
las calles tarifadas. El archivo `puestos.csv` es lo que usan el backend de Freddy y el mapa
de la app de Miguel, así que su formato es parte del contrato.

## SUMO en el contenedor
Esta sesión usa SUMO. Sigue la sección **"SUMO en el contenedor `van3twin`"** de `CLAUDE.md`:
- Antes de empezar, comprueba que el repo está clonado en `van3twin-docker/results/e-sert` y
  que `docker ps` muestra `van3twin`. Si no, avisa al usuario y no sigas con la parte de SUMO.
- `git` y la edición de archivos van en la computadora. `sumo`, `netconvert`, `randomTrips.py`
  y los scripts que importan `traci` o `sumolib` van dentro del contenedor:
  `docker exec -w /home/vanet/results/e-sert/<carpeta> van3twin bash -lc "<comando>"`.
- Es SUMO 1.12 con Python 3.10. Si algo de este prompt no existe en esa versión, adáptalo y
  anótalo en la bitácora.

## Objetivo
Crear el script que genera los `parkingArea` de SUMO para la zona tarifada, con una
configuración legible que cualquiera del grupo pueda ajustar.

## Pasos
1. Crea `sumo/parqueos/calles_sert.yaml`:
   ```yaml
   # Calles con estacionamiento tarifado SERT. Miguel verifica la lista contra la ordenanza (S1-3).
   incluir_tipos: [highway.residential, highway.tertiary, highway.secondary, highway.unclassified]
   excluir_nombres: ["Avenida Huayna Cápac", "Avenida Gaspar Sangurima"]   # avenidas sin parqueo en vía
   incluir_nombres: []          # si no está vacía, SOLO estas calles
   lado: derecho                # derecho | ambos (solo en calles anchas de doble sentido)
   largo_puesto_m: 5.5
   margen_esquina_m: 8.0        # sin parqueo cerca de las intersecciones
   largo_minimo_tramo_m: 12.0   # tramos más cortos no tienen puestos
   ```
2. Crea `sumo/parqueos/generar_parkingareas.py`:
   - Lee la red (`proyecto/sumo/red/centro.net.xml` o la de tu carpeta semanal) y el YAML.
   - Para cada *edge* que cumpla los filtros (tipo, nombre y que permita `passenger`),
     elige el **carril más a la derecha que permita `passenger`**. Ojo: con veredas, el
     carril 0 es la vereda.
   - Calcula `startPos = margen` y `endPos = largo − margen`, y luego
     `roadsideCapacity = floor((endPos − startPos) / largo_puesto)`.
   - Escribe `parqueos.add.xml` con
     `<parkingArea id="pa_<edgeId>_0" lane=... startPos=... endPos=... roadsideCapacity=... friendlyPos="true" name="<nombre de la calle>"/>`.
   - Escribe `puestos.csv` con las columnas
     `puesto_id,edge,lane,calle,capacidad,lat,lon,x,y`. La latitud y la longitud son las del
     punto medio del `parkingArea`, convertidas con `net.convertXY2LonLat`.
   - Imprime un resumen: número de `parkingArea`, capacidad total y capacidad por calle
     (las 10 mayores). Guárdalo en `parqueos_info.json`.
3. Crea `sumo/centro_parqueos.sumocfg`, que carga la red, los polígonos y
   `parqueos.add.xml`, y comprueba que `sumo --end 10` no da advertencias de posiciones.
4. **Prueba:** 10 vehículos con un `<stop parkingArea=... duration="60"/>` en
   `parkingArea` aleatorios. Todos deben estacionar. Usa `--stop-output` para comprobarlo.
5. **Evidencia** `evidencias/s2_puestos-sert.png`: la red en gris y cada `parkingArea` como
   un segmento coloreado por capacidad (barra de color *viridis*). El título debe llevar la
   capacidad total.

## Dónde escribir
`semanas/S1/Tyrone/codigo/sumo/parqueos/` y `semanas/S1/Tyrone/evidencias/`.

## Hecho cuando
- [ ] El script corre de punta a punta y es determinista: dos ejecuciones dan los mismos
  archivos.
- [ ] SUMO carga `parqueos.add.xml` sin errores, y los 10 vehículos de prueba estacionan.
- [ ] `puestos.csv` cumple exactamente el formato de arriba, con IDs `pa_<edge>_0`.
- [ ] Existe `parqueos_info.json` con la capacidad total.
- [ ] Existe la evidencia `s2_puestos-sert.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 2, Tyrone). En "Pedidos a
otros": @Miguel, verifica `calles_sert.yaml` contra la ordenanza SERT. @Freddy, `puestos.csv`
es tu fuente de puestos.
