---
semana: S3
tipo: unificacion
titulo: Unificación de S3 y resultados de experimentos
hora: "domingo 09:00"
---
# S3 · Unificación del domingo 8 de noviembre de 2026 (09:00, hora de Ecuador)

## Contexto
Eres Claude Code ejecutado por una **tarea programada, sin ninguna persona presente**. Nadie
va a responder preguntas: si algo te bloquea, decide de forma conservadora, documéntalo y
sigue. Lee primero `CLAUDE.md`, `docs/EQUIPO.md`, `docs/CONTRATO.md`, `docs/PLAN.md` y
`semanas/S2/unificacion-resultado.md` (riesgos y pedidos abiertos).

- Semana: **S3** (2–8 nov). Plazo de commits: **sábado 7 de noviembre, 23:59 (UTC−5)**, es
  decir `2026-11-07T23:59:59-05:00`.
- Ramas a unificar: `origin/tyrone/s3`, `origin/freddy/s3`, `origin/pablo/s3`,
  `origin/miguel/s3`.
- **Lo propio de S3:** esta unificación deja en `main` los **resultados de los
  experimentos** (penetración × clasificador × semillas) con los KPIs de búsqueda y de
  sistema, las figuras finales de Tyrone, el servicio de inferencia robusto de Pablo, el
  modo espejo del backend (candidatos, `WS /ws/espejo/{veh_id}`, recibo y `espejos` en el
  snapshot), el cierre automático con recibo en la app, y el primer borrador del informe
  (`informe/pablo.md`). La semana que viene es la última: todo lo que falte hoy es riesgo
  directo para la entrega del lunes 16.

Reglas firmes: nunca hagas `push --force`, nunca reescribas ni borres ramas de personas,
nunca edites `semanas/S3/<Nombre>/` y nunca subas `.env` ni credenciales. **No vuelvas a
correr la matriz de experimentos completa** (tarda horas): solo verificas lo que existe.
Escribe todo en español.

## Paso 1 · Ramas y plazos
1. `git fetch --all --prune` y `git status` (árbol limpio; si no, `git stash` y anótalo).
2. Para cada persona, comprueba si existe `origin/<nombre>/s3`; si no, **sin push**.
3. Para cada rama: commits nuevos (`git rev-list --count origin/main..origin/<nombre>/s3`),
   último commit (`git log -1 --format=%cI`) y commits posteriores al plazo
   (`git log --format="%h %cI %s" --since=2026-11-07T23:59:59-05:00 origin/<nombre>/s3`).
   Compara con `datetime.fromisoformat`. Posterior al plazo: **tardía**, pero **se incluye**.

## Paso 2 · Auditoría en paralelo (subagentes)
Lanza **cuatro subagentes en paralelo, uno por persona**, de solo lectura: "Audita
`origin/<nombre>/s3` sin modificar nada. Devuelve en Markdown: (a) archivos fuera de
`semanas/S3/<Nombre>/` y `bitacoras/<nombre>.md`; (b) `estado.json`; (c) evidencias
declaradas frente a PNG existentes y si existe `resumen_S3_<Nombre>.pdf`; (d) archivos de
`entrega` que faltan; (e) 'Pedidos a otros' de sus entradas S3; (f) archivos de más de 50 MB
o posibles secretos; (g) desvíos respecto de `docs/CONTRATO.md`; (h) para Tyrone y Freddy:
qué resultados de experimentos hay (CSV, JSON, figuras) y qué combinaciones de penetración,
clasificador y semilla cubren." Usa sus reportes.

## Paso 3 · Rama de unificación y fusiones
1. `git switch -c unificacion/s3 origin/main` (si `origin/unificacion/s3` ya existe,
   `unificacion/s3-r<HHMM>`).
2. Fusiona en orden freddy, tyrone, pablo, miguel con
   `git merge --no-ff origin/<nombre>/s3 -m "[S3-U] Fusiona <nombre>/s3"`.
3. Conflictos **triviales** (`.gitignore`, `.gitattributes`): unión de líneas. **No
   triviales**: `git merge --abort`, anota los archivos y trae solo la carpeta de la persona
   (`git checkout origin/<nombre>/s3 -- semanas/S3/<Nombre>/ bitacoras/<nombre>.md`).
4. Archivos fuera de la carpeta de la persona (salvo `.gitignore`): devuélvelos a
   `origin/main` y repórtalos.

## Paso 4 · Copia a `proyecto/` (solo módulos propios)
Copia `semanas/S3/<Nombre>/codigo/<ruta>` a `proyecto/<ruta>` **solo** si la ruta pertenece
a esa persona según `docs/EQUIPO.md`:

| Persona | Rutas permitidas dentro de `codigo/` |
|---|---|
| Tyrone | `sumo/`, `kpis/`, `visor/`, `demo/`, `informe/tyrone.md`, `informe/figuras/tyrone/` |
| Freddy | `traci/`, `backend/` (salvo `backend/pagos/` y `backend/asistente/`), `comun/` (salvo `comun/CONTRATO.propuesto.md`), `informe/freddy.md`, `informe/figuras/freddy/` |
| Pablo | `ia/`, `informe/` (salvo las secciones y figuras de los otros tres) |
| Miguel | `app/`, `datos/`, `backend/pagos/`, `backend/asistente/`, `informe/miguel.md`, `informe/figuras/miguel/` |

- Solo archivos versionados (`git ls-files`), con un script Python temporal **fuera del
  repo**. Nunca `.venv/`, `node_modules/`, `__pycache__/`, `.env*`, `logs/` ni archivos de
  más de 50 MB. De los resultados de experimentos se copian los agregados versionados
  (CSV, JSON y figuras), nunca las salidas crudas de SUMO.
- Sobrescribe; **no borres** nada de `proyecto/` (lista posibles eliminaciones).
- Lo que esté fuera de los módulos de su dueño **no se copia**: se reporta.
- Commit: `[S3-U] Copia módulos de S3 a proyecto/`.

## Paso 5 · Contrato
Si existe `semanas/S3/Freddy/codigo/comun/CONTRATO.propuesto.md`, compáralo con
`docs/CONTRATO.md` y verifica cada cambio contra el código ya copiado de los demás
(mensajes `kpi` y `verdad` del WS que consume el visor, avisos que muestra la app, campos de
`ResultadoModo`). Aplícalo **solo si es coherente**, con versión y fecha en el encabezado.
Si rompe el código de alguien, no lo apliques y deja el pedido. Commit: `[S3-U] Contrato v1.x`.

## Paso 6 · Verificaciones
1. Para cada módulo con `requirements.txt`, crea `proyecto/<m>/.venv` e instala. Si falla por
   red, **no verificable**.
2. `python -m pytest -q` en cada módulo con tests (`comun/`, `backend/`, `traci/`, `ia/`,
   `kpis/`), con `PYTHONPATH=proyecto` y sin las pruebas `e2e`.
3. Si hay SUMO, `sumo -c proyecto/sumo/centro_base.sumocfg --end 60 --no-step-log` debe salir
   con 0; si no, **no verificable en este entorno**.
4. **Resultados de experimentos** (lo propio de S3):
   - localiza los agregados en `proyecto/kpis/` (por ejemplo `resultados/`) y construye la
     tabla de cobertura: penetración {0, 20, 50, 80} % × clasificador {umbral, rf} × semillas;
     marca las combinaciones faltantes y si hay al menos **2 semillas** por escenario;
   - comprueba que están los KPIs del alcance: tiempo y distancia de búsqueda, CO₂, falsas
     liberaciones por 100 sesiones, retardo de cierre, error de facturación y precisión del
     mapa;
   - si existe el script de figuras de Tyrone, ejecútalo sobre los agregados (sin correr
     SUMO) y comprueba que regenera las figuras sin error;
   - si hay SUMO, una corrida corta del ejecutor (una combinación, `--end 60` o equivalente)
     para confirmar que funciona con el código unificado;
   - registra las cifras principales (búsqueda y falsas liberaciones al 50 %) para
     compararlas el próximo domingo.
5. Informativo: `ia/inferencia.py` cumple la latencia de menos de 5 ms (si Pablo dejó una
   prueba o *benchmark*, córrelo); `npx tsc --noEmit` en `proyecto/app/` si hay Node;
   `proyecto/informe/pablo.md` existe.
6. **Las pruebas pasan** si ningún pytest falla y SUMO (si está) sale con 0. La cobertura
   incompleta de experimentos **no bloquea** la fusión, pero encabeza los riesgos.

## Paso 7 · Resultado y bitácora
Escribe `semanas/S3/unificacion-resultado.md`:
- **Primera línea:** `**Estado:** fusionado en main` o `**Estado:** NO fusionado en main:
  <motivo>`. Segunda línea: cobertura de experimentos (N de M combinaciones).
- **Tabla por persona:** rama, commits, último commit, tardía, sesiones según `estado.json`,
  evidencias encontradas / declaradas, criterios, PDF semanal.
- **Conflictos**, archivos revertidos, **archivos no copiados**, posibles eliminaciones.
- **Tests**, SUMO y la **tabla de cobertura de experimentos** con las cifras principales.
- **Contrato:** aplicado o no y versión.
- **Pedidos cruzados** de las bitácoras (de, para, pedido, sesión), con los abiertos de S1 y
  S2.
- **Riesgos para S4**, que es la semana final (plazo real: sábado 14 a las 23:59): el modelo
  final congelado de Pablo (S4-1), del que depende la corrida final de Tyrone (S4-2); la
  demo en un comando de Tyrone (S4-1), que necesita backend y controlador estables; las
  pruebas e2e de Freddy (S4-1); las cuatro secciones del informe y la integración de Pablo
  (S4-3); el ensayo con el teléfono espejo contra el VPS y el video de plan B de Miguel (no hay
  pruebas de campo: todo es simulado). Indica qué falta hoy.

Agrega al final de `bitacoras/unificacion.md`:
```markdown
## S3 · Unificación · 2026-11-08
**Resultado:** fusionado en main | no fusionado (motivo)
**Ramas:** tyrone (N commits), freddy (…), pablo (…), miguel (…); tardías: …; sin push: …
**Conflictos:** … · **No copiados:** … · **Contrato:** …
**Tests:** … · **SUMO:** … · **Experimentos:** N/M combinaciones, búsqueda al 50 %: …
**Riesgos para S4:** …
```
Commit: `[S3-U] Resultado de la unificación de S3`.

## Paso 8 · Verificador independiente
Lanza un subagente nuevo, sin el contexto de esta ejecución: "En `unificacion/s3`, verifica
cada afirmación de `semanas/S3/unificacion-resultado.md` ejecutando los comandos (conteos,
archivos, evidencias, rutas copiadas frente a `docs/EQUIPO.md`, tests, SUMO, tabla de
cobertura de experimentos y cifras principales leídas de los CSV). Reporta cumple / no cumple
con la salida de cada comando." Si hay diferencias, corrige y repite (máximo 3 vueltas).

## Paso 9 · Publicación
- **Si las pruebas pasan:** `git switch main`, `git merge --ff-only origin/main`,
  `git merge --no-ff unificacion/s3 -m "[S3-U] Unificación de S3 en main"` y
  `git push origin main unificacion/s3`.
- **Si fallan:** `git push origin unificacion/s3` sin tocar `main`, con el motivo en la
  primera línea del resultado.
- Si el *push* falla, deja todo commiteado en local y regístralo.
- Termina con un resumen de 5 líneas: estado, tardíos o sin push, cobertura de
  experimentos, tests y el riesgo principal para la última semana.
