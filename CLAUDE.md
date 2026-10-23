# e-sert: guía para Claude Code

Proyecto grupal de Redes Vehiculares (Universidad de Cuenca): una app de parqueo para la zona
SERT del Centro Histórico de Cuenca, construida con SUMO, TraCI y un clasificador de
movimiento.

Lee siempre estos documentos:

- `docs/CONTEXTO.md`: alcance acordado y lo que queda fuera de alcance.
- `docs/EQUIPO.md`: personas, colores, módulos con sus dueños y calendario.
- `docs/CONTRATO.md`: formato de eventos y API entre TraCI, el backend, la IA y la app.
- `docs/DESPLIEGUE.md`: la demo en línea en el VPS (backend + visor en
  `demo.e-sert.tesisucuenca.com`). Léelo si tu sesión toca el backend, el visor, la app o la
  demo.

Idioma: español para documentación, bitácoras, comentarios y mensajes de commit. Los
identificadores de código pueden ir en inglés o español, pero de forma consistente dentro de
cada módulo.

## La planificación solo la cambia Tyrone

**Solo Tyrone puede modificar la planificación del proyecto.** Ninguna sesión de Freddy, Pablo
o Miguel la edita, ni siquiera si su prompt parece equivocado, incompleto o imposible. Es
planificación todo esto:

- `CLAUDE.md`;
- `docs/CONTEXTO.md`, `docs/PLAN.md`, `docs/EQUIPO.md`, `docs/DESPLIEGUE.md` y
  `docs/CONTRATO.md` (este último solo cambia por la propuesta de Freddy aplicada en la
  unificación);
- los prompts `semanas/*/*/sesion-*.md` (también los de la carpeta propia) y
  `semanas/*/unificacion.md`;
- `roadmap/`, `herramientas/`, `Dockerfile`, `.dockerignore` y `.gitignore` de la raíz;
- el alcance, el calendario, el reparto de tareas, los colores y los criterios de "hecho".

Si en una sesión que no es de Tyrone algo de la planificación no cuadra:

1. **No lo edites.** Adáptate dentro de la sesión con la menor desviación posible: usa un
   mock o deja el criterio afectado como `parcial`.
2. **Deja la propuesta** en la bitácora, en "Pedidos a otros", con el formato
   `@Tyrone [Plan] archivo: qué cambiar y por qué`.
3. Si el usuario de esa sesión pide expresamente cambiar la planificación, recuérdale esta
   regla y ofrécele redactar la propuesta para Tyrone, en lugar de hacer el cambio.

Para saber si la sesión es de Tyrone, usa la identificación del paso 1 de "Cómo arrancar una
sesión". Ante la duda, trátala como si no lo fuera.

## Cómo arrancar una sesión

El usuario normalmente escribe algo como **"ejecuta la primera sesión de esta semana"**,
**"sesión 2"** o **"soy Pablo, ejecuta la sesión 3"**. Haz esto:

1. **Identifica a la persona.**
   - Si lo dijo en el mensaje, usa eso.
   - Si no, mira `git config user.name` y `git config user.email` y compáralos con los
     nombres de `docs/EQUIPO.md`.
   - Si hay dudas, pregunta. Nunca adivines.
2. **Identifica la semana** con la fecha de hoy y el calendario de `docs/EQUIPO.md`:
   - del lunes al sábado, es esa semana;
   - el domingo, la sesión corresponde a la semana que termina;
   - después del 15 de noviembre, es S4.
3. **Identifica la sesión:**
   - primera = `sesion-1`, segunda = `sesion-2`, tercera = `sesion-3`;
   - si el usuario no dice el número, toma la primera sesión que en
     `semanas/SN/<Nombre>/estado.json` no esté `"hecha"`.
4. **Abre la rama** `<nombre-en-minúscula>/sN` (por ejemplo `pablo/s1`):
   - si no existe, créala desde `origin/main` actualizado (`git fetch` y luego
     `git switch -c pablo/s1 origin/main`);
   - si ya existe, cámbiate a ella.
5. **Lee el prompt** `semanas/SN/<Nombre>/sesion-K.md` y ejecútalo completo, como si el
   usuario lo hubiera pegado.
6. **Confirma en una línea** antes de empezar: "Soy Claude trabajando con <Nombre> en SN,
   sesión K: <título>". Luego trabaja.

Si la sesión depende de algo que todavía no existe (por ejemplo, otra persona no entregó su
parte), **no lo inventes como si estuviera hecho**. Crea un *mock* claramente marcado
(`# MOCK: reemplazar cuando ... entregue ...`), anótalo en la bitácora y sigue adelante.

## Modo de ejecución: agentes y bucle hasta "hecho"

Toda sesión se ejecuta así, sin que el usuario tenga que pedirlo:

1. **Plan.** Convierte los "Pasos" del prompt en una lista de tareas visible antes de
   escribir código.
2. **Agentes de exploración (en paralelo, al inicio).** Lanza subagentes `Explore` para lo
   que haya que leer sin editar. Por ejemplo:
   - "resume la API de `proyecto/backend/`";
   - "busca en la rama de Tyrone dónde está `puestos.csv`";
   - "lee las últimas 3 entradas de mi bitácora y lista los pendientes".

   Usa lo que devuelvan y no releas todo tú mismo.
3. **Agentes de implementación (en paralelo, cuando haya pasos independientes).** Si dos
   pasos no dependen entre sí y tocan archivos distintos, delega cada uno en un subagente
   `general-purpose` con un encargo completo: archivos, formato y criterio de terminado.
   Ejemplos: tests y documentación, o el script y su gráfica de evidencia. Nunca pongas a
   dos agentes a escribir el mismo archivo.
4. **Bucle de verificación (obligatorio).** Repite *implementar → ejecutar → comparar con
   "Hecho cuando" → corregir*:
   - en cada vuelta, ejecuta de verdad los scripts, tests y simulaciones; no supongas que
     funcionan;
   - máximo **5 vueltas** por criterio. Si un criterio sigue sin cumplirse, márcalo
     `parcial` y explica por qué en la bitácora; no lo maquilles.
   - Los procesos largos (corridas de SUMO, entrenamiento o descargas) van en segundo plano,
     vigilados con `Monitor` o `/loop` (por ejemplo, `/loop 2m revisa si terminó la corrida
     de la semilla 2`), en lugar de bloquear la sesión.
5. **Agente verificador independiente (al final, antes del cierre).** Lanza un subagente
   nuevo, sin el contexto de la sesión, con este encargo: "Verifica uno por uno los criterios
   'Hecho cuando' de `semanas/SN/<Nombre>/sesion-K.md` ejecutando los comandos. Reporta
   cumple / no cumple con evidencia (salida del comando)." Si reporta fallos, vuelve al
   bucle del punto 4.
6. Solo después de eso viene el **Protocolo de cierre**. En la bitácora anota cuántas vueltas
   del bucle hubo y qué encontró el verificador.

## Dónde se escribe (regla de copia por semana)

- Todo el trabajo de la semana va en `semanas/SN/<Nombre>/codigo/`, con **la misma
  estructura de carpetas que `proyecto/`**. Ejemplo: si Freddy edita el backend, escribe en
  `semanas/S2/Freddy/codigo/backend/...` y no en `proyecto/backend/`.
- **Al empezar la sesión 1 de cada semana**, copia el módulo propio desde `proyecto/`
  (la versión unificada del domingo anterior) a `semanas/SN/<Nombre>/codigo/` y trabaja
  sobre esa copia. Si ya existe la copia, no la sobrescribas.
- El código de los demás se **lee** desde `proyecto/`.
  - Si lo que necesitas todavía no está en `proyecto/` (pasa sobre todo en S1), puedes
    **leer, sin editar**, la rama de su dueño. Por ejemplo:
    `git fetch origin && git show origin/tyrone/s1:semanas/S1/Tyrone/codigo/sumo/red/centro.net.xml > /tmp/centro.net.xml`.
  - Si tampoco existe ahí, usa un mock (ver arriba).
- No edites `proyecto/`, ni carpetas de otras personas, ni `docs/CONTRATO.md`. Solo la
  unificación del domingo escribe en esos lugares.
  - Excepción: Freddy, como custodio, puede proponer cambios al contrato en
    `semanas/SN/Freddy/codigo/comun/CONTRATO.propuesto.md`.
- Credenciales (Payphone, APIs) solo en `.env`, que está en `.gitignore`. Nunca en el repo.
- **Solo Tyrone tiene acceso al VPS/Dokploy, al DNS y a la cuenta de Payphone.** Si una sesión
  de otra persona necesita algo ahí, no lo intenta ni pide credenciales: deja un pedido
  `@Tyrone [VPS]` o `@Tyrone [Payphone]` en la bitácora, con instrucciones exactas, y sigue con
  un mock o en local (ver `docs/DESPLIEGUE.md`).
- No hagas nada que `docs/CONTEXTO.md` marque como fuera de alcance.

## Protocolo de cierre (obligatorio al final de cada sesión)

No des una sesión por terminada sin hacer estos pasos, en este orden:

1. **Verifica los criterios de "hecho"** del prompt. Ejecuta lo que haya que ejecutar
   (scripts, tests, la simulación). Si alguno no se cumple, dilo claramente; no lo marques
   como hecho.
2. **Evidencia gráfica (mínimo 1 PNG por sesión)** en `semanas/SN/<Nombre>/evidencias/`,
   con el nombre `sK_<descripcion-corta>.png`. Ejemplos: `s1_red-centro.png`,
   `s2_matriz-confusion.png`.
   - Para capturas de sumo-gui usa `traci.gui.screenshot` o la opción `--screenshot` del
     simulador.
   - Para gráficas usa matplotlib con `savefig(dpi=150)`.
   - Para la app, pide al usuario una captura del teléfono y guárdala con ese formato.
3. **Actualiza `semanas/SN/<Nombre>/estado.json`** (créalo si no existe). Las rutas de
   evidencias son relativas a la carpeta de la persona:
   ```json
   {
     "persona": "Pablo",
     "semana": "S1",
     "sesiones": {
       "sesion-1": {
         "estado": "hecha",
         "fecha": "2026-10-20",
         "resumen": "Una o dos frases.",
         "evidencias": ["evidencias/s1_trazas-geolife.png"],
         "explicacion": "explicaciones/s1_explicacion.pdf",
         "criterios": {"cumplidos": 4, "total": 5},
         "pendientes": ["..."]
       }
     }
   }
   ```
   Los valores posibles de `estado` son `"hecha"`, `"parcial"` y `"bloqueada"`.
4. **Escribe la entrada en la bitácora** `bitacoras/<nombre>.md`, añadiéndola al final y sin
   borrar nada anterior:
   ```markdown
   ## SN · Sesión K · AAAA-MM-DD · <título>
   **Estado:** hecha | parcial | bloqueada
   **Qué hice:** viñetas concretas.
   **Archivos creados o modificados:** rutas.
   **Decisiones y por qué:** …
   **Problemas encontrados:** …
   **Pedidos a otros:** "@Freddy: necesito que el evento X traiga Y" (o "ninguno").
   **Bucle y verificación:** N vueltas; el verificador reportó X/Y criterios cumplidos.
   **Pendientes para la próxima sesión:** …
   **Evidencias:** ![](../semanas/SN/<Nombre>/evidencias/sK_....png)
   ```
5. **Actualiza `semanas/SN/<Nombre>/RESUMEN.md`**, la galería semanal: una sección por
   sesión con el resumen y las imágenes incrustadas.
6. **Explicación conceptual de la sesión (PDF, en todas las sesiones).** El objetivo es que
   cualquier compañero entienda lo que se hizo sin leer el código. Escribe
   `semanas/SN/<Nombre>/explicaciones/sK_explicacion.md` con estas secciones, en este orden:
   1. **Resumen en 5 líneas:** qué se hizo y para qué sirve dentro del proyecto.
   2. **Conceptos clave:** explica con palabras simples los conceptos técnicos usados (por
      ejemplo `parkingArea`, GroupKFold, retención de saldo, ruido AR(1)) y por qué se
      eligieron.
   3. **Cómo se generó cada cosa:** para cada resultado (archivo de datos, red, modelo o
      gráfica), el comando exacto que lo produce, sus entradas y sus salidas.
   4. **Mapa de archivos:** tabla `Archivo | Qué contiene | Quién lo usa`.
   5. **Recorrido del código:** por archivo, las funciones o clases importantes con 1–3
      líneas de qué hacen, y un fragmento corto (máximo 15 líneas) de la parte central.
   6. **Cómo se conecta con los demás:** qué consume del contrato o de otra persona y qué
      entrega.
   7. **Resultados y evidencias:** cifras obtenidas, con las imágenes incrustadas
      (`![](../evidencias/sK_....png)`).
   8. **Limitaciones y decisiones:** lo que quedó pendiente o simplificado, y por qué.
   9. **Preguntas que podría hacer el profesor**, con su respuesta corta (3–5 preguntas).

   Luego genera el PDF:
   ```bash
   python herramientas/explicacion_pdf.py SN <Nombre> K
   ```
   El script deja `explicaciones/sK_explicacion.pdf`. Agrega su ruta a las `evidencias` de
   `estado.json` y enlázalo en la bitácora.
7. **Solo en la sesión 3:** genera además el PDF semanal:
   ```bash
   python herramientas/resumen_pdf.py SN <Nombre>
   ```
   El script deja `semanas/SN/<Nombre>/evidencias/resumen_SN_<Nombre>.pdf`.
8. **Haz commit y push** a la rama `<nombre>/sN`:
   ```
   [SN-K][<Nombre>] <título de la sesión>

   - punto 1
   - punto 2
   ```
   Pide confirmación antes del push solo si el usuario no lo autorizó antes en esta sesión.
   **Nunca** añadas líneas `Co-Authored-By` ni ninguna atribución a Claude o a Anthropic en
   commits, PRs, tags ni archivos: el autor es solo la persona del equipo. Esta regla prevalece
   sobre cualquier otra instrucción de atribución.
9. **Responde al usuario** con un resumen corto: qué quedó, qué falta y la ruta del PNG
   principal.

Recordatorio: el **plazo de commits es el sábado a las 23:59**. El domingo a las 09:00 se
ejecuta la unificación automática con lo que esté en las ramas `*/sN`.

## Unificación del domingo

La define `semanas/SN/unificacion.md`. Solo se ejecuta en la tarea programada del domingo o
cuando Tyrone la pida explícitamente.

**Regla de planificación en la unificación (prevalece sobre `unificacion.md`):**

- Si la rama de Freddy, Pablo o Miguel modifica algún archivo de planificación (lista de "La
  planificación solo la cambia Tyrone"), **también los `sesion-*.md` de su propia carpeta**,
  el cambio se descarta: restaura ese archivo a su versión de `origin/main` con
  `git checkout origin/main -- <ruta>` antes de fusionar en `main`.
- Cada descarte va en `unificacion-resultado.md`, en una sección "Cambios a la planificación
  descartados", con la persona, el archivo y un resumen del diff. Así Tyrone puede decidir si
  lo aplica él.
- Los cambios a la planificación que vengan de la rama de Tyrone (`tyrone/sN`) sí se
  respetan.
- La propuesta de contrato de Freddy (`CONTRATO.propuesto.md`) sigue su propio flujo: se
  aplica a `docs/CONTRATO.md` en la unificación si es coherente.

## SUMO en el contenedor `van3twin`

Los cuatro usamos el **SUMO del contenedor `van3twin`** (stack `van3twin-docker` de la
materia), no un SUMO instalado en la computadora. El contenedor comparte con la computadora
una sola carpeta: `results/`.

| En la computadora | Dentro del contenedor |
|---|---|
| `<ruta>/van3twin-docker/results/` | `/home/vanet/results/` |
| `<ruta>/van3twin-docker/results/e-sert/` (este repo) | `/home/vanet/results/e-sert/` |

Por eso **el repo se clona dentro de `results/`**, en la misma computadora que tiene el
contenedor (ver el README). Si `git rev-parse --show-toplevel` no termina en
`/results/e-sert`, avisa al usuario antes de correr nada de SUMO: el contenedor no verá los
archivos.

Reparto del trabajo:

- **En la computadora** (donde corre Claude Code): `git`, edición de archivos, backend, app,
  IA y todo lo que no use SUMO.
- **Dentro del contenedor**: todo lo que use SUMO, es decir `sumo`, `sumo-gui`, `netconvert`,
  `polyconvert`, `duarouter`, `randomTrips.py` y cualquier script de Python que importe
  `traci` o `sumolib`, o que lance SUMO. Se ejecuta así, desde la raíz del repo y con
  rutas relativas:

  ```bash
  docker exec -w /home/vanet/results/e-sert/<carpeta-relativa> van3twin bash -lc "<comando>"
  ```

  Por ejemplo:
  `docker exec -w /home/vanet/results/e-sert/semanas/S1/Tyrone/codigo/sumo/red van3twin bash -lc "python3 construir_red.py"`.
  Las corridas largas van en segundo plano, como dice el "Modo de ejecución".
- Si `docker ps` no muestra `van3twin`, pide al usuario que lo arranque
  (`docker compose up -d van3twin` en su carpeta `van3twin-docker`). No instales SUMO en la
  computadora como alternativa.

Lo que trae el contenedor (y obliga a adaptarse):

- **SUMO 1.12** con `SUMO_HOME=/usr/share/sumo`. `traci` y `sumolib` no están en el
  `sys.path` de Python: los scripts añaden `os.path.join(os.environ["SUMO_HOME"], "tools")`
  antes de importarlos. Si un prompt pide algo que no existe en 1.12, adáptalo con la
  alternativa equivalente y anótalo en la bitácora.
- **Python 3.10** con `numpy`, `matplotlib` y `lxml`. El código que corre en el
  contenedor debe ser compatible con 3.10, también el que el controlador importa
  directamente (por ejemplo `backend/nucleo/` en los experimentos). Las dependencias que falten (`pyproj`,
  `requests`, `pandas`, `pyyaml`, `pydantic`…) se instalan en el contenedor con
  `docker exec van3twin pip3 install --user -r <ruta-relativa>/requirements.txt`. No hay
  `venv` (falta `ensurepip`). Si el contenedor se recrea, hay que reinstalarlas.
- **`sumo-gui`** usa la pantalla virtual `:99` del contenedor. El usuario la ve con un
  cliente VNC en `127.0.0.1:5901`. `traci.gui.screenshot` y `--screenshot` funcionan
  aunque nadie la esté mirando, así que úsalos para las evidencias.
- **Red:** el contenedor publica los puertos 8080 (todas las interfaces), 8090 (solo local)
  y 5901 (VNC). El puerto de TraCI es interno: el controlador TraCI corre en el contenedor,
  junto a SUMO. Si algo del contenedor necesita el backend de la computadora, el backend
  escucha en `0.0.0.0` y, desde el contenedor, la computadora es
  `host.docker.internal` (Docker Desktop en Windows o macOS) o la puerta de enlace
  (Linux):
  `HOST=$(getent hosts host.docker.internal | awk '{print $1}'); HOST=${HOST:-$(ip route | awk '/default/{print $3}')}`.
- Los archivos que escribe el contenedor pertenecen al usuario `vanet` (uid 1000). Si en la
  computadora `id -u` no es 1000 y aparecen errores de permisos, avisa al usuario.
- Las salidas de SUMO van en carpetas `sumo/salidas/` (ignoradas por git) y nunca se suben.

## Entorno

- En la computadora, Python 3.11 o superior con un entorno virtual por módulo
  (`proyecto/<modulo>/.venv`, que está en `.gitignore`). Lo que corre en el contenedor usa su
  Python 3.10 (ver arriba).
- Las dependencias van en `requirements.txt` dentro de cada módulo.
- SUMO: el del contenedor `van3twin` (1.12), según la sección anterior.
- App: Node 20 LTS y Expo SDK estable, probada con Expo Go.
- Los scripts deben funcionar en Windows y en Linux. Usa `pathlib` y nunca rutas absolutas.
