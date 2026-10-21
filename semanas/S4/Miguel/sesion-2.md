---
semana: S4
persona: Miguel
sesion: 2
titulo: Ensayo general de la demo con el teléfono espejo y video de respaldo
horas: 3-4
modulo: app
depende: [S4-Miguel-1, S4-Tyrone-1, S3-Freddy-3]
entrega: [app/ensayo/guion_demo.md, app/ensayo/checklist_previa.md, app/ensayo/registro_ensayo.md, app/ensayo/latencias/, app/ensayo/analizar_ensayo.py, app/ensayo/resultados_ensayo.json, app/plan_b/crudo/LEEME.md]
evidencias: [s2_ensayo-montaje.png, s2_latencias-ensayo.png]
---
# S4 · Sesión 2 · Miguel 🔴: Ensayo general de la demo con el teléfono espejo y video de respaldo

## Contexto
Lee `CLAUDE.md`, `docs/CONTRATO.md` (secciones 3 y 6b), `docs/DESPLIEGUE.md` y tu `app/MANUAL.md`
(S4-1). **Todo es simulado: no hay pruebas de campo.** La demo es `sumo-gui` en la laptop, el visor
en el proyector y el teléfono espejo en la mano siguiendo a un auto simulado. La demo de Tyrone
(`demo/demo.py --remoto | --local`) está en `proyecto/demo/` o en `origin/tyrone/s4`: tráela con
`git archive` a una carpeta temporal y córrela **sin editarla**. Solo Tyrone toca el VPS: si algo
falla ahí, `@Tyrone [VPS]` con el síntoma exacto. Plazo: sábado 14, 23:59.

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
Ensayar la demo completa dos veces (VPS y local) con un guion cronometrado, medir lo que ve el
público y grabar el video de respaldo crudo que S4-3 edita.

## Pasos
1. **Guion** `app/ensayo/guion_demo.md`, cronometrado (tabla toma / duración / quién / qué se ve /
   qué se dice), 6–7 min en total:
   1. problema SERT y app (30 s);
   2. `demo.py --remoto` arrancando: sumo-gui y visor con puestos verdes y rojos (45 s);
   3. el teléfono abre el selector y elige un candidato; el visor lo resalta (`espejos`) (45 s);
   4. GUIADO: ruta y puesto en el teléfono frente al auto en sumo-gui (60 s);
   5. ESTACIONADO → A_PIE: el peatón se aleja y **el puesto sigue rojo** (falsa liberación evitada) (60 s);
   6. REGRESANDO → SALIENDO → CERRADA: notificación y recibo frente a la tarjeta SERT (60 s);
   7. KPIs en vivo y cierre (45 s).
   Con `EXPO_PUBLIC_ESCALA_TIEMPO` o la velocidad de sumo-gui, ajusta para que el recorrido del auto
   elegido quepa en las tomas 4–6; anota el `--seed` y el vehículo que mejor funciona.
2. **Checklist previa** `app/ensayo/checklist_previa.md` (casillas): `curl /salud` del VPS responde,
   Expo Go actualizado y la app abierta en primer plano, brillo al máximo, "No molestar" activado
   con excepción para Expo Go, notificaciones permitidas, batería ≥ 80 %, `Ajustes de demo` con la
   URL correcta, datos móviles y Wi-Fi probados, `demo.py --local` probado sin internet, IP de la
   laptop anotada, video de respaldo copiado en la laptop y en USB.
3. **Ensayo A, contra el VPS**: `demo.py --remoto`, visor público en el proyector, teléfono con
   `EXPO_PUBLIC_API_URL=https://demo.e-sert.tesisucuenca.com`. Sigue el guion con cronómetro y
   registra en `registro_ensayo.md` cada desviación con su hora (toma, tiempo previsto, real,
   incidencia).
4. **Ensayo B, en local** (plan B): `demo.py --local`, teléfono y laptop en el *hotspot* de un
   teléfono, URL `http://<ip-laptop>:8000` desde Ajustes de demo. Provoca a propósito una caída
   (apaga el Wi-Fi del teléfono 15 s) y verifica que la reconexión exponencial de S2-3 recupera el
   espejo sin reiniciar la app.
5. **Latencias**: exporta en cada ensayo el CSV de `latencia.ts` (S2-3) a
   `app/ensayo/latencias/<modo>.csv`. Crea `app/ensayo/analizar_ensayo.py` (pandas): p50/p95 de
   evento → pantalla por modo, número de reconexiones, tiempo de recuperación, duración real de cada
   toma frente al guion y si el recibo cuadra con `tarifa.json` (±$0,01). Escribe
   `resultados_ensayo.json`.
6. **Video de respaldo crudo**: durante el mejor ensayo, graba la pantalla de la laptop con OBS
   (escena con sumo-gui y visor, 1080p 30 fps) y el teléfono con la grabación de pantalla de iOS o
   Android, empezando ambos con una palmada visible para sincronizar. Combina con `ffmpeg`
   (`-filter_complex "[1:v]scale=-2:1080[t];[0:v][t]hstack"`) en `app/plan_b/crudo/` (en
   `.gitignore`; el video **nunca** va en git). En `crudo/LEEME.md` anota la ubicación, la duración y
   el desfase de sincronización; la edición final, subtítulos y enlace son de S4-3.
7. Un subagente escribe `analizar_ensayo.py` y la gráfica mientras tú diriges el ensayo; otro
   revisa el guion contra CONTRATO 6b (los estados y avisos que se nombran existen de verdad).
8. **Evidencias**: `s2_ensayo-montaje.png` (un fotograma del video combinado: laptop y teléfono con
   el mismo vehículo) y `s2_latencias-ensayo.png` (cajas de latencia VPS frente a local, `dpi=150`).

## VPS (demo en línea)
El ensayo A va contra `https://demo.e-sert.tesisucuenca.com`. Si `/salud` no responde o el espejo
falla en el VPS, no intentes arreglarlo tú: deja `@Tyrone [VPS]` con la hora, la URL y la respuesta,
haz el ensayo completo en local y marca el criterio del VPS como `parcial`.

## Dónde escribir
`semanas/S4/Miguel/codigo/app/ensayo/`, `semanas/S4/Miguel/codigo/app/plan_b/crudo/LEEME.md` y
`evidencias/`. Comprueba con `git ls-files "*.mp4"` que no hay videos versionados.

## Hecho cuando
- [ ] `guion_demo.md` y `checklist_previa.md` existen y el guion se cumplió con ±30 s en total.
- [ ] Hubo un ensayo completo contra el VPS (o queda documentado por qué no) y otro en local.
- [ ] La caída provocada se recupera sola y su tiempo queda en `resultados_ensayo.json`.
- [ ] `python app/ensayo/analizar_ensayo.py` genera `resultados_ensayo.json` con latencias por modo.
- [ ] El video crudo existe fuera de git y `crudo/LEEME.md` lo describe.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 2, Miguel). En "Pedidos a otros":
@Tyrone, problemas de `demo.py` y del visor en el ensayo (y `[VPS]` si aplica); @Freddy, cualquier
mensaje espejo inválido o recibo descuadrado con su `veh_id`.
