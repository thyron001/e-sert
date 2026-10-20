---
semana: S2
tipo: unificacion
titulo: Unificación de S2 y primera integración backend, TraCI y app
hora: "domingo 09:00"
---
# S2 · Unificación del domingo 1 de noviembre de 2026 (09:00, hora de Ecuador)

## Contexto
Eres Claude Code ejecutado por una **tarea programada, sin ninguna persona presente**. Nadie
va a responder preguntas: si algo te bloquea, decide de forma conservadora, documéntalo y
sigue. Lee primero `CLAUDE.md`, `docs/EQUIPO.md`, `docs/CONTRATO.md` (v1) y `docs/PLAN.md`,
y el resultado anterior `semanas/S1/unificacion-resultado.md` (riesgos y pedidos abiertos).

- Semana: **S2** (26 oct – 1 nov). Plazo de commits: **sábado 31 de octubre, 23:59
  (UTC−5)**, es decir `2026-10-31T23:59:59-05:00`.
- Ramas a unificar: `origin/tyrone/s2`, `origin/freddy/s2`, `origin/pablo/s2`,
  `origin/miguel/s2`.
- **Lo propio de S2:** esta unificación deja en `main` la **primera integración
  backend ↔ TraCI ↔ app**: el backend FastAPI de Freddy, el controlador TraCI con guiado y
  sesiones, `rf_v1` de Pablo, la app de Miguel con el flujo de sesión y la billetera, y el
  visor de Tyrone. Debes comprobar que se hablan de verdad (paso 6.4).

Reglas firmes: nunca hagas `push --force`, nunca reescribas ni borres ramas de personas,
nunca edites `semanas/S2/<Nombre>/` y nunca subas `.env` ni credenciales (Payphone en modo de
prueba incluido). Escribe todo en español.

## Paso 1 · Ramas y plazos
1. `git fetch --all --prune` y `git status` (árbol limpio; si no, `git stash` y anótalo).
2. Para cada persona, comprueba si existe `origin/<nombre>/s2`. Si no existe, regístrala como
   **sin push** y sigue.
3. Para cada rama: commits nuevos (`git rev-list --count origin/main..origin/<nombre>/s2`),
   último commit (`git log -1 --format=%cI`) y commits posteriores al plazo
   (`git log --format="%h %cI %s" --since=2026-10-31T23:59:59-05:00 origin/<nombre>/s2`).
   Compara con `datetime.fromisoformat`. Último commit posterior al plazo: **tardía**, pero
   **se incluye**.

## Paso 2 · Auditoría en paralelo (subagentes)
Lanza **cuatro subagentes en paralelo, uno por persona**, de solo lectura, con este encargo:
"Audita `origin/<nombre>/s2` sin modificar nada. Devuelve en Markdown: (a) archivos tocados
fuera de `semanas/S2/<Nombre>/` y `bitacoras/<nombre>.md`; (b) `estado.json` (sesiones
hechas, parciales y bloqueadas; criterios); (c) evidencias declaradas en el *frontmatter* de
cada `sesion-K.md` frente a los PNG que existen, y si existe `resumen_S2_<Nombre>.pdf`;
(d) archivos de `entrega` que faltan; (e) líneas de 'Pedidos a otros' de sus entradas S2;
(f) archivos de más de 50 MB o que parezcan secretos; (g) cualquier uso de campos, rutas o
mensajes que **no estén en `docs/CONTRATO.md` v1**." Usa sus reportes.

## Paso 3 · Rama de unificación y fusiones
1. `git switch -c unificacion/s2 origin/main` (si `origin/unificacion/s2` ya existe, usa
   `unificacion/s2-r<HHMM>` y anótalo).
2. Fusiona en orden: freddy, tyrone, pablo, miguel, cada una con
   `git merge --no-ff origin/<nombre>/s2 -m "[S2-U] Fusiona <nombre>/s2"`.
3. Conflictos **triviales** (`.gitignore`, `.gitattributes`): unión de líneas sin
   duplicados. **No triviales**: `git merge --abort`, anota los archivos y trae solo la
   carpeta de la persona con
   `git checkout origin/<nombre>/s2 -- semanas/S2/<Nombre>/ bitacoras/<nombre>.md`.
4. Archivos que un auditor reportó fuera de la carpeta de la persona (salvo `.gitignore`):
   devuélvelos a `origin/main` y repórtalos.

## Paso 4 · Copia a `proyecto/` (solo módulos propios)
Copia `semanas/S2/<Nombre>/codigo/<ruta>` a `proyecto/<ruta>` **solo** si la ruta pertenece
a esa persona según `docs/EQUIPO.md`:

| Persona | Rutas permitidas dentro de `codigo/` |
|---|---|
| Tyrone | `sumo/`, `kpis/`, `visor/`, `demo/`, `informe/tyrone.md`, `informe/figuras/tyrone/` |
| Freddy | `traci/`, `backend/` (salvo `backend/pagos/` y `backend/asistente/`), `comun/` (salvo `comun/CONTRATO.propuesto.md`), `informe/freddy.md`, `informe/figuras/freddy/` |
| Pablo | `ia/`, `informe/` (salvo las secciones y figuras de los otros tres) |
| Miguel | `app/`, `datos/`, `backend/pagos/`, `backend/asistente/`, `informe/miguel.md`, `informe/figuras/miguel/` |

- Solo archivos versionados (`git ls-files semanas/S2/<Nombre>/codigo`), con un script Python
  temporal **fuera del repo**. Nunca `.venv/`, `node_modules/`, `__pycache__/`, `.env*`,
  `salidas/`, `logs/` ni archivos de más de 50 MB.
- Sobrescribe; **no borres** nada de `proyecto/` (lista las posibles eliminaciones).
- Lo que esté fuera de los módulos de su dueño **no se copia**: se reporta.
- Atención especial: `backend/pagos/` de Miguel y el resto de `backend/` de Freddy conviven
  en la misma carpeta; comprueba que ninguno pisó al otro.
- Commit: `[S2-U] Copia módulos de S2 a proyecto/`.

## Paso 5 · Contrato
Si existe `semanas/S2/Freddy/codigo/comun/CONTRATO.propuesto.md`, compáralo con
`docs/CONTRATO.md` (`git diff --no-index`) y verifica cada cambio contra el código ya copiado
de los demás (rutas de la app, CSV de trazas, firma de `clasificar`, `puestos.csv`, mensajes
WS del visor). Aplícalo **solo si es coherente**, sube la versión (v1.1, v1.2…) con la fecha
en el encabezado y lista los cambios. Si rompe el código de alguien, no lo apliques: deja la
diferencia como pedido. Commit: `[S2-U] Contrato v1.x`.

## Paso 6 · Verificaciones
1. Para cada módulo con `requirements.txt`, crea `proyecto/<m>/.venv` e instala. Si falla por
   red, el módulo queda **no verificable**.
2. `python -m pytest -q` en cada módulo con tests (`comun/`, `backend/` incluido
   `backend/pagos/`, `traci/`, `ia/`, `kpis/`), con `PYTHONPATH=proyecto` y sin las pruebas
   marcadas `e2e`. Registra pasados, fallados, saltados y duración.
3. Si hay SUMO, `sumo -c proyecto/sumo/centro_base.sumocfg --end 60 --no-step-log` debe salir
   con 0; si no hay, **no verificable en este entorno**.
4. **Humo de integración backend ↔ TraCI ↔ app** (lo propio de S2), con un script temporal
   fuera del repo:
   - arranca el backend de `proyecto/backend/` con `uvicorn` en un puerto libre y una SQLite
     temporal; espera a `GET /api/v1/puestos` y comprueba que devuelve tantos puestos como
     `proyecto/sumo/parqueos/puestos.csv`;
   - si hay SUMO, corre el controlador de `proyecto/traci/` sin GUI 120 s simulados contra
     ese backend (penetración 20 %, semilla 1, flags según su README);
   - un cliente WS en `/ws/estado` recibe `snapshot` y valida cada uno con
     `proyecto/comun/esquemas.py`;
   - un "teléfono" simulado por HTTP con los ejemplos de `proyecto/comun/ejemplos/`:
     recarga, `/guia`, `POST /sesiones`, `/eventos/ubicacion` con `origen: "app"`,
     `/eventos/modo`, `cerrar`; comprueba la billetera y que el teléfono aparece en
     `telefonos` del `snapshot`;
   - informativo: `npx tsc --noEmit` en `proyecto/app/` si hay Node, y que el visor tenga
     la URL del WS configurable.
   Registra cada sub-paso como ok, falla o no verificable.
5. **Las pruebas pasan** si ningún pytest falla y SUMO (si está) sale con 0. El humo de
   integración **no bloquea** la fusión (las piezas deben llegar a `main` para que S3
   trabaje sobre ellas), pero si falla encabeza la lista de riesgos y genera pedidos.

## Paso 7 · Resultado y bitácora
Escribe `semanas/S2/unificacion-resultado.md`:
- **Primera línea:** `**Estado:** fusionado en main` o `**Estado:** NO fusionado en main:
  <motivo>`. Segunda línea: estado del humo de integración.
- **Tabla por persona:** rama, commits, último commit, tardía, sesiones según `estado.json`,
  evidencias encontradas / declaradas, criterios cumplidos / total, PDF semanal.
- **Conflictos**, archivos revertidos, **archivos no copiados**, posibles eliminaciones.
- **Tests** (módulo / comando / resultado / duración), SUMO y la tabla del humo de
  integración paso a paso.
- **Contrato:** aplicado o no, versión y desvíos detectados por los auditores.
- **Pedidos cruzados** de las bitácoras (de, para, pedido, sesión), marcando los de S1 que
  siguen abiertos.
- **Riesgos para S3**, según `docs/PLAN.md`: el controlador con KPIs de sistema de Freddy
  (S3-1) que Tyrone necesita para el ejecutor de experimentos; `inferencia.py` robusto de
  Pablo para la clasificación en vivo (S3-3 de Freddy); el flujo de la app y la ubicación
  real para el cierre automático de Miguel (S3-1). Indica qué falta y qué mock se usará.

Agrega al final de `bitacoras/unificacion.md`:
```markdown
## S2 · Unificación · 2026-11-01
**Resultado:** fusionado en main | no fusionado (motivo)
**Ramas:** tyrone (N commits), freddy (…), pablo (…), miguel (…); tardías: …; sin push: …
**Conflictos:** … · **No copiados:** … · **Contrato:** sin cambios | v1.x aplicado
**Tests:** … · **SUMO:** … · **Integración backend↔TraCI↔app:** ok | parcial | falla
**Riesgos para S3:** …
```
Commit: `[S2-U] Resultado de la unificación de S2`.

## Paso 8 · Verificador independiente
Lanza un subagente nuevo, sin el contexto de esta ejecución: "En `unificacion/s2`, verifica
cada afirmación de `semanas/S2/unificacion-resultado.md` ejecutando los comandos (conteos,
archivos, evidencias, rutas copiadas frente a `docs/EQUIPO.md`, tests, SUMO y el humo de
integración). Reporta cumple / no cumple con la salida de cada comando." Si hay diferencias,
corrige y repite (máximo 3 vueltas).

## Paso 9 · Publicación
- **Si las pruebas pasan:** `git switch main`, `git merge --ff-only origin/main`,
  `git merge --no-ff unificacion/s2 -m "[S2-U] Unificación de S2 en main"` y
  `git push origin main unificacion/s2`.
- **Si fallan:** `git push origin unificacion/s2` sin tocar `main`, con el motivo en la
  primera línea del resultado.
- Si el *push* falla, deja todo commiteado en local y regístralo.
- Termina con un resumen de 5 líneas: estado, tardíos o sin push, integración, tests y el
  riesgo principal para S3.
