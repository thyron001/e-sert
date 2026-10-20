---
semana: S4
tipo: unificacion
titulo: Unificación final de S4 y versión de entrega v1.0
hora: "domingo 09:00"
---
# S4 · Unificación final del domingo 15 de noviembre de 2026 (09:00, hora de Ecuador)

## Contexto
Eres Claude Code ejecutado por una **tarea programada, sin ninguna persona presente**. Nadie
va a responder preguntas: si algo te bloquea, decide de forma conservadora, documéntalo y
sigue. Lee primero `CLAUDE.md`, `docs/EQUIPO.md`, `docs/CONTRATO.md`, `docs/PLAN.md` y
`semanas/S3/unificacion-resultado.md` (riesgos y pedidos abiertos).

- Semana: **S4** (9–15 nov). Plazo de commits: **sábado 14 de noviembre, 23:59 (UTC−5)**, es
  decir `2026-11-14T23:59:59-05:00`.
- Ramas a unificar: `origin/tyrone/s4`, `origin/freddy/s4`, `origin/pablo/s4`,
  `origin/miguel/s4`.
- **Lo propio de S4:** esta es la **versión final de entrega** (lunes 16 de noviembre). Deja
  en `main` la demo en un comando (`proyecto/demo/`), el modelo final congelado, las pruebas
  e2e, la documentación técnica, la app pulida y el **informe completo construido** en
  `proyecto/informe/`. Si todo pasa, `main` se marca con el tag **`v1.0`**.

Reglas firmes: nunca hagas `push --force`, nunca reescribas ni borres ramas de personas,
nunca edites `semanas/S4/<Nombre>/` y nunca subas `.env`, credenciales ni videos. Nunca
reentrenes el modelo ni corras la matriz completa de experimentos: solo verificas. Escribe
todo en español.

## Paso 1 · Ramas y plazos
1. `git fetch --all --prune --tags` y `git status` (árbol limpio; si no, `git stash` y
   anótalo). Si ya existe el tag `v1.0`, es una reejecución: no lo muevas (ver paso 9).
2. Para cada persona, comprueba si existe `origin/<nombre>/s4`; si no, **sin push**.
3. Para cada rama: commits nuevos (`git rev-list --count origin/main..origin/<nombre>/s4`),
   último commit (`git log -1 --format=%cI`) y commits posteriores al plazo
   (`git log --format="%h %cI %s" --since=2026-11-14T23:59:59-05:00 origin/<nombre>/s4`).
   Compara con `datetime.fromisoformat`. Posterior al plazo: **tardía**, pero **se incluye**.

## Paso 2 · Auditoría en paralelo (subagentes)
Lanza **cuatro subagentes en paralelo, uno por persona**, de solo lectura: "Audita
`origin/<nombre>/s4` sin modificar nada. Devuelve en Markdown: (a) archivos fuera de
`semanas/S4/<Nombre>/` y `bitacoras/<nombre>.md`; (b) `estado.json`; (c) evidencias
declaradas frente a PNG existentes y si existe `resumen_S4_<Nombre>.pdf`; (d) archivos de
`entrega` que faltan; (e) 'Pedidos a otros' de sus entradas S4 y cuáles de semanas
anteriores siguen abiertos; (f) archivos de más de 50 MB, videos (`*.mp4`, `*.mov`) o posibles
secretos; (g) si existe su sección del informe (`codigo/informe/<nombre>.md`), cuántas
palabras tiene y si contiene `TODO`, `PENDIENTE` o `MOCK`." Usa sus reportes.

## Paso 3 · Rama de unificación y fusiones
1. `git switch -c unificacion/s4 origin/main` (si `origin/unificacion/s4` ya existe,
   `unificacion/s4-r<HHMM>`).
2. Fusiona en orden freddy, tyrone, pablo, miguel con
   `git merge --no-ff origin/<nombre>/s4 -m "[S4-U] Fusiona <nombre>/s4"`.
3. Conflictos **triviales** (`.gitignore`, `.gitattributes`): unión de líneas. **No
   triviales**: `git merge --abort`, anota los archivos y trae solo la carpeta de la persona
   (`git checkout origin/<nombre>/s4 -- semanas/S4/<Nombre>/ bitacoras/<nombre>.md`).
4. Archivos fuera de la carpeta de la persona (salvo `.gitignore`): devuélvelos a
   `origin/main` y repórtalos.

## Paso 4 · Copia a `proyecto/` (solo módulos propios)
Copia `semanas/S4/<Nombre>/codigo/<ruta>` a `proyecto/<ruta>` **solo** si la ruta pertenece
a esa persona según `docs/EQUIPO.md`:

| Persona | Rutas permitidas dentro de `codigo/` |
|---|---|
| Tyrone | `sumo/`, `kpis/`, `visor/`, `demo/`, `informe/tyrone.md`, `informe/figuras/tyrone/` |
| Freddy | `traci/`, `backend/` (salvo `backend/pagos/` y `backend/asistente/`), `comun/` (salvo `comun/CONTRATO.propuesto.md`), `informe/freddy.md`, `informe/figuras/freddy/` |
| Pablo | `ia/`, `informe/` (salvo las secciones y figuras de los otros tres) |
| Miguel | `app/`, `datos/`, `backend/pagos/`, `backend/asistente/`, `informe/miguel.md`, `informe/figuras/miguel/` |

- Solo archivos versionados (`git ls-files`), con un script Python temporal **fuera del
  repo**. Nunca `.venv/`, `node_modules/`, `__pycache__/`, `.env*`, `logs/`, `demo.db`,
  videos ni archivos de más de 50 MB (el modelo `ia/modelos/rf_final.joblib` sí se copia si
  está versionado y por debajo de ese tamaño).
- Sobrescribe; **no borres** nada de `proyecto/` (lista posibles eliminaciones).
- Lo que esté fuera de los módulos de su dueño **no se copia**: se reporta.
- Commit: `[S4-U] Copia módulos de S4 a proyecto/`.

## Paso 5 · Contrato
Si existe `semanas/S4/Freddy/codigo/comun/CONTRATO.propuesto.md`, compáralo con
`docs/CONTRATO.md`. En la versión final solo se aceptan cambios **compatibles** (aclaraciones
o campos opcionales nuevos) y coherentes con el código copiado de los demás; un cambio que
rompa a alguien no se aplica y queda documentado. Comprueba además que
`python proyecto/comun/docs/verificar_contrato_api.py` (si existe) sale con 0. Commit:
`[S4-U] Contrato v1.x final`.

## Paso 6 · Verificaciones
1. Para cada módulo con `requirements.txt`, crea `proyecto/<m>/.venv` e instala. Si falla por
   red, **no verificable**.
2. `python -m pytest -q` en cada módulo con tests (`comun/`, `backend/`, `traci/`, `ia/`,
   `kpis/`), con `PYTHONPATH=proyecto`.
3. Si hay SUMO:
   - `sumo -c proyecto/sumo/centro_base.sumocfg --end 60 --no-step-log` sale con 0;
   - `python -m pytest -m e2e -q` en `proyecto/backend/` y `proyecto/traci/`;
   - `python proyecto/demo/verificar_demo.py` (la demo sin GUI, unos 2 min) sale con 0.
   Si no hay SUMO, los tres quedan como **no verificables en este entorno**.
4. **Modelo final:** el SHA-256 de `proyecto/ia/modelos/rf_final.joblib` coincide con
   `rf_final.json` y con el citado en `proyecto/kpis/resultados/final/manifiesto.json`.
5. **Informe final** (lo propio de S4):
   - `python proyecto/informe/construir_informe.py --fuentes proyecto`, que debe producir
     `proyecto/informe/salida/informe_e-sert.pdf` (o el HTML si no hay `pandoc`, anotado);
   - `python proyecto/informe/verificar_informe.py`: las cuatro secciones presentes, sin
     `TODO`/`PENDIENTE`/`MOCK`, imágenes y citas resueltas, cifras coherentes;
   - commitea la salida: `[S4-U] Informe final construido`.
6. **Higiene de la entrega:** `git ls-files` no contiene `.env`, `*.mp4`, `*.mov` ni archivos
   de más de 50 MB; una búsqueda de patrones de secretos (`token`, `secret`, `api_key`,
   `Authorization`) no encuentra valores reales; existe `proyecto/demo/README.md` y
   `proyecto/app/plan_b/ENLACE_VIDEO.md` con un enlace.
7. **Criterios:**
   - **Las pruebas pasan** (para fusionar en `main`) si ningún pytest falla y SUMO (si está)
     sale con 0.
   - **Todo pasa** (para el tag `v1.0`) si además pasan, o son no verificables por falta de
     SUMO, la suite e2e y `verificar_demo.py`, el hash del modelo coincide, el informe se
     construye con `verificar_informe.py` en 0 y la higiene está limpia.

## Paso 7 · Resultado y bitácora
Escribe `semanas/S4/unificacion-resultado.md`:
- **Primera línea:** `**Estado:** fusionado en main, tag v1.0` o `**Estado:** fusionado en
  main, sin tag v1.0: <qué falta>` o `**Estado:** NO fusionado en main: <motivo>`.
- **Tabla por persona:** rama, commits, último commit, tardía, sesiones según `estado.json`,
  evidencias encontradas / declaradas, criterios, PDF semanal y sección del informe
  (palabras).
- **Conflictos**, archivos revertidos, **archivos no copiados**, posibles eliminaciones.
- **Tests:** pytest por módulo, SUMO, e2e, `verificar_demo.py`, hash del modelo, informe e
  higiene, cada uno como ok, falla o no verificable.
- **Contrato:** versión final.
- **Pedidos cruzados** de las bitácoras, marcando cuáles quedaron sin resolver al cierre del
  proyecto.
- **Riesgos para la entrega y la exposición del lunes 16** (no hay semana siguiente):
  qué no se pudo verificar aquí y debe probarse a mano en la laptop de la demo (SUMO con
  GUI, el teléfono espejo contra el VPS y en la LAN para el plan B `--local`, Payphone en
  modo de prueba), secciones débiles del informe y el plan B (video). Termina con una lista de comprobación de 10 puntos para el lunes por la
  mañana.

Agrega al final de `bitacoras/unificacion.md`:
```markdown
## S4 · Unificación final · 2026-11-15
**Resultado:** fusionado en main, tag v1.0 | sin tag (qué falta) | no fusionado (motivo)
**Ramas:** tyrone (N commits), freddy (…), pablo (…), miguel (…); tardías: …; sin push: …
**Conflictos:** … · **No copiados:** … · **Contrato:** versión final …
**Tests:** … · **SUMO/e2e/demo:** … · **Informe:** construido | con fallas (…)
**Riesgos para el lunes 16:** …
```
Commit: `[S4-U] Resultado de la unificación final`.

## Paso 8 · Verificador independiente
Lanza un subagente nuevo, sin el contexto de esta ejecución: "En `unificacion/s4`, verifica
cada afirmación de `semanas/S4/unificacion-resultado.md` ejecutando los comandos (conteos,
archivos, evidencias, rutas copiadas frente a `docs/EQUIPO.md`, pytest, SUMO, e2e,
`verificar_demo.py`, hash del modelo, construcción y verificación del informe e higiene).
Abre el PDF del informe y confirma que tiene las cuatro secciones. Reporta cumple / no cumple
con la salida de cada comando." Si hay diferencias, corrige y repite (máximo 3 vueltas).

## Paso 9 · Publicación y tag
- **Si las pruebas pasan:** `git switch main`, `git merge --ff-only origin/main`,
  `git merge --no-ff unificacion/s4 -m "[S4-U] Versión final de entrega"` y
  `git push origin main unificacion/s4`.
  - **Si además todo pasa:** `git tag -a v1.0 -m "e-sert v1.0: entrega del 16 de noviembre
    de 2026"` sobre ese commit de `main` y `git push origin v1.0`. Si alguna verificación
    quedó como no verificable, dilo en el mensaje del tag.
  - **Si no todo pasa:** crea en su lugar `v1.0-rc1` (o el siguiente `rc` libre), haz push y
    deja en el resultado la lista exacta de lo que falta para que Tyrone ponga `v1.0` a mano.
  - Si `v1.0` ya existía (reejecución), no lo muevas: crea `v1.0.1` solo si `main` cambió y
    todo pasa.
- **Si fallan:** `git push origin unificacion/s4` sin tocar `main` ni crear tags, con el
  motivo en la primera línea del resultado.
- Si el *push* falla, deja todo commiteado en local y regístralo.
- Termina con un resumen de 5 líneas: estado y tag, tardíos o sin push, tests, informe y el
  riesgo principal para el lunes.
