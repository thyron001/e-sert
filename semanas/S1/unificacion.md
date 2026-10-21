---
semana: S1
tipo: unificacion
titulo: Unificación de S1 y congelamiento del contrato v1
hora: "domingo 09:00"
---
# S1 · Unificación del domingo 25 de octubre de 2026 (09:00, hora de Ecuador)

## Contexto
> **Planificación:** solo Tyrone la cambia. Aplica la "Regla de planificación en la unificación" de
> `CLAUDE.md`: los cambios de Freddy, Pablo o Miguel a archivos de planificación (incluidos sus
> `sesion-*.md`) se descartan y se reportan en "Cambios a la planificación descartados".

Eres Claude Code ejecutado por una **tarea programada, sin ninguna persona presente**. Nadie
va a responder preguntas: si algo te bloquea, decide de forma conservadora, documéntalo y
sigue. Lee primero `CLAUDE.md`, `docs/EQUIPO.md`, `docs/CONTRATO.md` y `docs/PLAN.md`.

- Semana: **S1** (19–25 oct). Plazo de commits: **sábado 24 de octubre, 23:59 (UTC−5)**,
  es decir `2026-10-24T23:59:59-05:00`.
- Ramas a unificar: `origin/tyrone/s1`, `origin/freddy/s1`, `origin/pablo/s1`,
  `origin/miguel/s1`.
- **Lo propio de S1:** esta unificación **congela el contrato v1**. Es el paso más importante
  de la semana: desde mañana las cuatro personas trabajan contra `docs/CONTRATO.md` v1.

Reglas firmes: nunca hagas `push --force`, nunca reescribas ni borres ramas de personas,
nunca edites `semanas/S1/<Nombre>/` (es el trabajo de cada uno) y nunca subas `.env` ni
credenciales. Escribe todo en español.

## Paso 1 · Ramas y plazos
1. `git fetch --all --prune` y `git status` (el árbol debe estar limpio; si no, `git stash`
   y anótalo).
2. Para cada persona, comprueba si existe `origin/<nombre>/s1` (`git rev-parse --verify`).
   Si no existe, regístrala como **sin push** y sigue con las demás.
3. Para cada rama que exista, registra: número de commits nuevos
   (`git rev-list --count origin/main..origin/<nombre>/s1`), fecha del último commit
   (`git log -1 --format=%cI`) y la lista de commits posteriores al plazo
   (`git log --format="%h %cI %s" --since=2026-10-24T23:59:59-05:00 origin/<nombre>/s1`).
   Compara fechas con `datetime.fromisoformat` en Python, no como texto. Si el último commit
   es posterior al plazo, la rama se marca **tardía**, pero **se incluye igual**.

## Paso 2 · Auditoría en paralelo (subagentes)
Lanza **cuatro subagentes en paralelo, uno por persona**, de solo lectura. Encargo para cada
uno: "Audita la rama `origin/<nombre>/s1` sin modificar nada (usa `git show`, `git log`,
`git diff --name-only origin/main...origin/<nombre>/s1`). Devuelve en Markdown:
(a) archivos tocados **fuera** de `semanas/S1/<Nombre>/` y `bitacoras/<nombre>.md`;
(b) el contenido de `semanas/S1/<Nombre>/estado.json` (sesiones hechas, parciales y
bloqueadas; criterios cumplidos/total);
(c) por cada `sesion-K.md`, las evidencias declaradas en su *frontmatter* frente a los PNG
que existen en `evidencias/`, y si existe `resumen_S1_<Nombre>.pdf`;
(d) los archivos de `entrega` del *frontmatter* que faltan en `codigo/`;
(e) las líneas de 'Pedidos a otros' de sus entradas S1 en `bitacoras/<nombre>.md`;
(f) los archivos de más de 50 MB o que parezcan secretos (`.env`, claves, tokens)."
Usa sus reportes; no repitas tú la auditoría.

## Paso 3 · Rama de unificación y fusiones
1. `git switch -c unificacion/s1 origin/main`. Si `origin/unificacion/s1` ya existe (es una
   reejecución), usa `unificacion/s1-r<HHMM>` y anótalo.
2. Fusiona en este orden (Freddy primero, porque trae el contrato):
   `git merge --no-ff origin/freddy/s1 -m "[S1-U] Fusiona freddy/s1"`, luego tyrone, pablo y
   miguel.
3. Como cada persona escribe en carpetas propias, no debería haber conflictos. Si los hay:
   - **triviales** (`.gitignore`, `.gitattributes`, líneas añadidas por ambos): resuélvelos
     conservando la unión de líneas sin duplicados;
   - **no triviales**: `git merge --abort`, anota los archivos en conflicto y trae solo la
     carpeta propia de esa persona, que nadie más toca:
     `git checkout origin/<nombre>/s1 -- semanas/S1/<Nombre>/ bitacoras/<nombre>.md` y commit
     `[S1-U] Trae carpeta de <Nombre> (merge con conflicto)`.
4. Si un auditor reportó archivos fuera de la carpeta de la persona (salvo `.gitignore`),
   devuélvelos a su versión de `origin/main` (`git checkout origin/main -- <ruta>`, o
   `git rm` si no existían) y repórtalos.

## Paso 4 · Copia a `proyecto/` (solo módulos propios)
Copia `semanas/S1/<Nombre>/codigo/<ruta>` a `proyecto/<ruta>` **solo** si la ruta pertenece
a esa persona según `docs/EQUIPO.md`:

| Persona | Rutas permitidas dentro de `codigo/` |
|---|---|
| Tyrone | `sumo/`, `kpis/`, `visor/`, `demo/`, `informe/tyrone.md`, `informe/figuras/tyrone/` |
| Freddy | `traci/`, `backend/` (salvo `backend/pagos/` y `backend/asistente/`), `comun/` (salvo `comun/CONTRATO.propuesto.md`), `informe/freddy.md`, `informe/figuras/freddy/` |
| Pablo | `ia/`, `informe/` (salvo las secciones y figuras de los otros tres) |
| Miguel | `app/`, `datos/`, `backend/pagos/`, `backend/asistente/`, `informe/miguel.md`, `informe/figuras/miguel/` |

- Copia solo archivos versionados (`git ls-files semanas/S1/<Nombre>/codigo`), con un script
  Python temporal **fuera del repo** (`pathlib` y `shutil.copy2`). Nunca copies `.venv/`,
  `node_modules/`, `__pycache__/`, `.env*`, `salidas/`, `logs/` ni archivos de más de 50 MB.
- Sobrescribe lo que exista. **No borres** nada de `proyecto/`: si un archivo existe en
  `proyecto/` y no en la copia, lístalo como "posible eliminación, no aplicada".
- Los archivos fuera de los módulos de su dueño **no se copian**: lístalos con persona, ruta y
  dueño correcto.
- Commit: `[S1-U] Copia módulos de S1 a proyecto/`.

## Paso 5 · Contrato v1 (obligatorio en S1)
1. Lee `semanas/S1/Freddy/codigo/comun/CONTRATO.propuesto.md`. Comprueba que esté completo y
   autocontenido (sin "ver v0") y que tenga la sección "Cambios respecto a v0".
2. Comprueba la coherencia con el código de los demás y anota cada diferencia:
   - `proyecto/sumo/parqueos/puestos.csv`: columnas e IDs `pa_<edgeId>_<n>`;
   - el CSV de trazas de Pablo y de Freddy: encabezado exacto de la sección de trazas;
   - `proyecto/ia/inferencia.py`: firma de `clasificar` y valores de `modo` y `fuente`;
   - el cliente API de la app (`proyecto/app/`): rutas y nombres de campos;
   - `proyecto/comun/tarifa.json` frente a la sección de tarifa y la tarifa SERT que verificó
     Miguel.
3. Aplica: reemplaza `docs/CONTRATO.md` por el propuesto y cambia el encabezado a
   "Contrato de interfaces (v1, congelado el 2026-10-25 en la unificación de S1)". Las
   incoherencias no impiden congelarlo: el v1 manda, y cada diferencia se convierte en un
   pedido a su dueño para S2.
4. Si el propuesto **no existe** o está vacío, deja `docs/CONTRATO.md` como v0 y escribe la
   alerta **"CONTRATO v1 NO CONGELADO"** en la primera línea del resultado (riesgo crítico).
5. Commit: `[S1-U] Congela el contrato v1`.

## Paso 6 · Verificaciones
1. Para cada módulo de `proyecto/` con `requirements.txt`, crea `proyecto/<m>/.venv` (en
   `.gitignore`) e instala dependencias. Si falla por red, el módulo queda **no verificable**.
2. Corre `python -m pytest -q` en cada módulo Python que tenga tests (`comun/tests`,
   `backend/tests`, `traci/tests`, `ia/tests`, `kpis/tests` si existen), con
   `PYTHONPATH=proyecto`. Si el módulo trae su propio comando en un README, úsalo. Registra
   pasados, fallados, saltados y duración. Un módulo sin tests es "sin tests", no un fallo.
3. Si hay SUMO (en esta computadora, el del contenedor `van3twin`: los comandos de SUMO se
   ejecutan con `docker exec`, como explica la sección "SUMO en el contenedor `van3twin`" de
   `CLAUDE.md`), corre
   `sumo -c <cfg> --end 60 --no-step-log` con el primero que exista de
   `proyecto/sumo/centro_base.sumocfg`, `centro_parqueos.sumocfg` y `centro_red.sumocfg`; debe
   salir con código 0. Si no hay SUMO, anótalo como **no verificable en este entorno**.
4. Lo propio de S1, comprueba que existen en `proyecto/` los cimientos que S2 necesita:
   `sumo/red/centro.net.xml`, `sumo/parqueos/puestos.csv`, `comun/esquemas.py`,
   `comun/esquemas.ts`, la muestra de trazas de `traci/trazas/`, `ia/inferencia.py`,
   `app/package.json` y el protocolo de grabaciones caseras de `datos/` (las grabaciones son
   opcionales: su ausencia no es un riesgo).
5. **Las pruebas pasan** si ningún pytest falla y SUMO (si está) sale con 0. "No verificable"
   y "sin tests" no cuentan como fallo, pero se reportan.

## Paso 7 · Resultado y bitácora
Escribe `semanas/S1/unificacion-resultado.md`:
- **Primera línea:** `**Estado:** fusionado en main` o `**Estado:** NO fusionado en main:
  <motivo>` (y, si aplica, la alerta del contrato).
- **Tabla por persona:** rama, commits, último commit, tardía (sí/no), sesiones hechas /
  parciales / bloqueadas según `estado.json`, evidencias encontradas / declaradas, criterios
  cumplidos / total, PDF semanal (sí/no).
- **Conflictos** y cómo se resolvieron; **archivos fuera de carpeta** revertidos; **archivos
  no copiados** (persona, ruta, dueño); **posibles eliminaciones** no aplicadas.
- **Tests:** tabla módulo / comando / resultado / duración, más SUMO.
- **Contrato:** aplicado o no, versión y lista de incoherencias.
- **Pedidos cruzados** recogidos de las bitácoras: de, para, pedido, sesión.
- **Riesgos para S2**, revisando las dependencias críticas de `docs/PLAN.md`: red y puestos
  para Freddy (S2-2) y Pablo (S2-1); trazas de Freddy para Pablo (S2-1); las grabaciones
  caseras de Miguel son opcionales (todo es simulado) y no cuentan como riesgo; `inferencia.py` para Freddy (S2-2); la API que Miguel y el visor
  necesitan en S2. Indica cuáles faltan en `proyecto/` y cuál será el mock.

Agrega al final de `bitacoras/unificacion.md` (créalo si no existe):
```markdown
## S1 · Unificación · 2026-10-25
**Resultado:** fusionado en main | no fusionado (motivo)
**Ramas:** tyrone (N commits), freddy (…), pablo (…), miguel (…); tardías: …; sin push: …
**Conflictos:** … · **No copiados:** … · **Contrato:** v1 congelado | no congelado
**Tests:** … · **SUMO:** ok | falla | no verificable
**Riesgos para S2:** …
```
Commit: `[S1-U] Resultado de la unificación de S1`.

## Paso 8 · Verificador independiente
Lanza un subagente nuevo, sin el contexto de esta ejecución: "En la rama `unificacion/s1`,
verifica cada afirmación de `semanas/S1/unificacion-resultado.md` ejecutando los comandos
(conteos de commits, existencia de archivos y evidencias, copia de módulos, tests y SUMO).
Comprueba que `proyecto/` solo recibió rutas permitidas por `docs/EQUIPO.md` y que
`docs/CONTRATO.md` es el v1. Reporta cumple / no cumple con la salida de cada comando." Si
reporta diferencias, corrige el resultado o la unificación y repite (máximo 3 vueltas).

## Paso 9 · Publicación
- **Si las pruebas pasan:** `git switch main`, `git merge --ff-only origin/main`,
  `git merge --no-ff unificacion/s1 -m "[S1-U] Unificación de S1 en main"` y
  `git push origin main unificacion/s1`.
- **Si fallan:** `git push origin unificacion/s1` sin tocar `main`, con el motivo en la
  primera línea del resultado.
- Si el *push* falla (credenciales, rama protegida), deja todo commiteado en local y
  regístralo en el resultado y en la bitácora.
- Termina con un resumen de 5 líneas: estado, quién quedó tardío o sin push, contrato, tests
  y el riesgo principal para S2.
