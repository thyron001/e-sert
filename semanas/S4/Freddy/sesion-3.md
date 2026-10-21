---
semana: S4
persona: Freddy
sesion: 3
titulo: Sección backend y TraCI del informe y ensayo de la demo
horas: 3-4
modulo: informe
depende: [S4-Freddy-1, S4-Freddy-2, S4-Tyrone-1, S4-Pablo-1]
entrega: [informe/freddy.md, informe/figuras/freddy/, comun/docs/ensayo_demo_freddy.md]
evidencias: [s3_ensayo-demo-freddy.png]
---
# S4 · Sesión 3 · Freddy 🍅: Sección backend y TraCI del informe y ensayo de la demo

## Contexto
Lee `CLAUDE.md`, `informe/GUIA_ESTILO.md` de Pablo (en `origin/pablo/s4`), tu
`comun/docs/arquitectura.md` y `decisiones.md` (sesión 2) y los resultados de la suite e2e
(sesión 1). Pablo integra el informe el sábado; tu sección tiene que estar en `freddy/s4`
**antes del sábado 14 a las 18:00** para que alcance a integrarla, y en todo caso antes de
las 23:59, que es el plazo real. La unificación final es el domingo 15 a las 09:00.

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
- El controlador TraCI corre en el contenedor, junto a SUMO, y el backend en la computadora
  (`--host 0.0.0.0`). Desde el contenedor, la URL del backend usa `host.docker.internal` o la
  puerta de enlace, como explica `CLAUDE.md`.

## Objetivo
Escribir `informe/freddy.md` con cifras reales medidas y ensayar la demo de Tyrone desde tu
lado (backend y controlador), dejando registradas las fallas y su arreglo.

## Pasos
1. Escribe `informe/freddy.md` (1 500–2 500 palabras), con el formato de la guía de estilo:
   - **Arquitectura:** resumen y figura de componentes (copia el PNG a
     `informe/figuras/freddy/`).
   - **Controlador TraCI:** bucle, suscripciones, *hooks*, peatones que hacen diligencias y
     rendimiento (ms por paso con 0/20/50/80 % de penetración, medido ahora).
   - **Emulador GPS:** el proceso AR(1) en LaTeX,
     `e_t = ρ e_{t-1} + sqrt(1-ρ²) σ ε_t` con los valores de `ia/calibracion/ruido_literatura.json`
     (σ de 3 a 15 m en cañón urbano, tomados de la literatura, y el análisis de sensibilidad de
     Pablo), pérdidas de muestra y velocidad derivada como en un teléfono; una figura de traza verdadera frente a ruidosa.
   - **Máquina de estados:** tabla de transiciones con umbrales y por qué el puesto **sigue
     ocupado** en `A_PIE`; figura `estados_sesion`.
   - **Guiado:** recomendación con ocupación actual, `setParkingAreaStop` /
     `rerouteParkingArea`, y qué pasa si el puesto se llena en el camino.
   - **Backend:** núcleo sin HTTP, billetera como libro (`disponible = saldo − retenido`),
     un ejemplo numérico de cobro de 47 min y la comparación con la tarjeta SERT.
   - **KPIs de sistema:** definición formal de falsas liberaciones por 100 sesiones, retardo
     de cierre, error de facturación y precisión del mapa (fórmulas) y sus valores finales
     (tómalos de `origin/tyrone/s4:.../kpis/resultados/final/resumen.csv`).
   - **Pruebas:** número de tests unitarios y e2e, cobertura del núcleo (`pytest --cov`) y
     duración de la suite.
   - **Limitaciones.**
   Cada cifra lleva `<!-- fuente: ... -->` con el archivo o comando de donde sale.
2. Revisa tu sección con un subagente independiente: "lee `informe/freddy.md` como el
   profesor; marca afirmaciones sin cifra o sin fuente, contradicciones con
   `docs/CONTRATO.md` y figuras enlazadas que no existen". Corrige.
3. **Ensayo de la demo** desde tu lado. La demo de Tyrone aún no está en `proyecto/`:
   extráela de `origin/tyrone/s4` con `git archive` a una carpeta temporal y córrela
   **sin editarla**. Prueba:
   - arranque en frío y tiempo hasta el primer `snapshot`;
   - reiniciar el backend en medio de la demo: ¿el controlador reintenta o se cae?;
   - el teléfono espejo pierde el WS y se reconecta: retoma el mismo vehículo, la sesión sigue
     abierta y el recibo no se duplica;
   - 80 % de penetración con GUI: ¿se mantiene fluido? (ms por paso);
   - Ctrl+C: ¿quedan procesos o puertos ocupados?
   Lo que falle en `traci/` o `backend/` lo arreglas en tu copia y vuelves a ensayar; lo que
   falle en `demo/` va como pedido a Tyrone con los pasos para reproducirlo.
4. Escribe `comun/docs/ensayo_demo_freddy.md`: una tabla con prueba, resultado, causa,
   arreglo y responsable, más los tiempos medidos.
5. **Evidencia** `evidencias/s3_ensayo-demo-freddy.png`: línea de tiempo del ensayo (eventos
   del log del controlador y del backend en el eje x, y los incidentes marcados en rojo) junto
   a una captura del visor durante la demo.

## Dónde escribir
`semanas/S4/Freddy/codigo/informe/freddy.md`, `semanas/S4/Freddy/codigo/informe/figuras/freddy/`,
`semanas/S4/Freddy/codigo/comun/docs/` y `evidencias/`. No escribas en el informe de los
demás ni en `informe/informe.md` (lo integra Pablo).

## Hecho cuando
- [ ] `informe/freddy.md` existe, sin `TODO` ni `MOCK`, y todas sus figuras enlazadas existen.
- [ ] El revisor independiente no encuentra cifras sin fuente.
- [ ] Las cinco pruebas del ensayo están registradas con su resultado.
- [ ] Los fallos de `traci/` o `backend/` encontrados en el ensayo están arreglados y
  `pytest -m e2e` sigue pasando.
- [ ] Existen la evidencia `s3_ensayo-demo-freddy.png` y el **PDF semanal**
  (`python herramientas/resumen_pdf.py S4 Freddy`).
- [ ] Todo está en `freddy/s4` antes del sábado 14 a las 23:59.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 3, Freddy), **incluido el PDF
semanal**. En "Pedidos a otros": @Pablo, la sección está lista y en qué commit; @Tyrone, los
fallos de `demo/` encontrados en el ensayo.
