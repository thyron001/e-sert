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

## Entorno

- Python 3.11 o superior con un entorno virtual por módulo (`proyecto/<modulo>/.venv`, que
  está en `.gitignore`).
- Las dependencias van en `requirements.txt` dentro de cada módulo.
- SUMO 1.20 o superior, con la variable `SUMO_HOME` configurada. Usa `sumolib` y `traci` de
  `$SUMO_HOME/tools`.
- App: Node 20 LTS y Expo SDK estable, probada con Expo Go.
- Los scripts deben funcionar en Windows y en Linux. Usa `pathlib` y nunca rutas absolutas.
