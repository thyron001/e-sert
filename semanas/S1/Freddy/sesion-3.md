---
semana: S1
persona: Freddy
sesion: 3
titulo: Controlador TraCI base y emulador de GPS
horas: 3-4
modulo: traci
depende: [S1-Tyrone-1]
entrega: [traci/controlador.py, traci/gps.py, traci/tests/, traci/trazas/]
evidencias: [s3_trazas-gps.png, s3_ruido-gps.png]
---
# S1 · Sesión 3 · Freddy 🍅: Controlador TraCI base y emulador de GPS

## Contexto
Lee `CLAUDE.md` y `docs/CONTRATO.md` (secciones 2 y 7). La red de Tyrone todavía no está en
`proyecto/`, así que léela de su rama:
`git show origin/tyrone/s1:semanas/S1/Tyrone/codigo/sumo/red/centro.net.xml`. Si aún no
existe, usa un mock: una red pequeña generada con `netgenerate --grid` y veredas, marcada
como `# MOCK`. **Pablo depende de estas trazas en S2** para entrenar con datos de SUMO.

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
Tener el bucle TraCI funcionando y un emulador de GPS realista que, para cada vehículo o
peatón, genere trazas con ruido en el formato CSV del contrato y con la **etiqueta
verdadera** del modo.

## Pasos
1. Crea `traci/controlador.py` con una clase `Controlador(config)`:
   - arranca `sumo` o `sumo-gui` con `traci.start`;
   - hace `paso()` y `correr(hasta)`;
   - usa suscripciones (`traci.vehicle.subscribe` para posición y velocidad) en lugar de
     llamadas sueltas, por rendimiento;
   - registra *hooks* `on_paso` para que S2 enchufe la máquina de estados y el guiado sin
     tocar el bucle.
   - CLI: `python -m traci.controlador --cfg ... --gui --hasta 600`.
2. Crea `traci/gps.py` con `EmuladorGPS(semilla, sigma_m=5.0, p_perdida=0.02, tasa_hz=1)`:
   - posición verdadera con `traci.vehicle.getPosition` o `traci.person.getPosition`,
     convertida con `traci.simulation.convertGeo`;
   - ruido gaussiano **correlacionado en el tiempo**, con un proceso AR(1) de ρ=0,8, no
     ruido blanco: así se comporta un GPS real en un cañón urbano;
   - pérdidas de muestra con probabilidad `p_perdida`;
   - `precision_m` reportada igual a `sigma_m × U(0,8; 1,5)`;
   - `velocidad_mps` calculada como la haría un teléfono (por diferencia de posiciones
     ruidosas), no la de SUMO.
   - Etiqueta verdadera `modo_real`:
     - `vehiculo` si el agente es un vehículo en movimiento o detenido en tráfico;
     - `quieto` si es un vehículo estacionado con la persona adentro, o una persona parada;
     - `a_pie` si es un peatón caminando.
3. **Generador de trazas de entrenamiento** `traci/generar_trazas.py`:
   - corre el escenario de Tyrone (o un mock con 200 autos y 150 peatones) durante 30 min;
   - incluye **casos difíciles**: autos en congestión (velocidad < 7 km/h) y peatones
     rápidos;
   - escribe `traci/trazas/sumo_semilla<N>.csv` en el formato exacto del contrato
     (sección 7).
   - Genera 3 semillas. Los CSV grandes van en `.gitignore`; publica solo una muestra de
     5 000 filas.
4. **Tests** (`traci/tests/`):
   - el ruido tiene la desviación estándar esperada (±10 %);
   - la autocorrelación con *lag* 1 ≈ 0,8;
   - el CSV valida con `comun/esquemas.py`. Si aún no está en `proyecto/`, léelo de tu
     carpeta S1.
5. **Evidencias:**
   - `s3_trazas-gps.png`: la ruta verdadera frente a la ruidosa de un auto y un peatón sobre
     la red.
   - `s3_ruido-gps.png`: histograma del error en metros y autocorrelación.

## Dónde escribir
`semanas/S1/Freddy/codigo/traci/` y `evidencias/`.

## Hecho cuando
- [ ] `python -m traci.controlador --cfg <escenario> --hasta 300` corre sin errores.
- [ ] Las 3 semillas de trazas están generadas, con las tres clases presentes y casos de
  tráfico lento.
- [ ] Los tests del emulador pasan.
- [ ] Existen las dos evidencias PNG y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 3, Freddy), **incluido el PDF
semanal**. En "Pedidos a otros": @Pablo, ruta y formato de las trazas; @Tyrone, qué
necesitas del escenario.
