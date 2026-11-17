# e-sert: guía para Claude Code

App de parqueo para la zona SERT del Centro Histórico de Cuenca (Redes Vehiculares,
Universidad de Cuenca), construida con SUMO, TraCI y un clasificador de movimiento.

## Forma de trabajo (desde el 2026-11-17)

El trabajo en equipo terminó con la unificación final. Desde ahora:

- **Una sola persona (Tyrone), una sola computadora y una sola sesión de Claude Code.**
- **Una sola rama: `main`.** Se trabaja, se hace commit y se hace push directamente en `main`.
  No se crean ramas por persona, por semana ni por sesión, y no hay unificaciones.
- **Se edita directamente en `proyecto/`.** Ya no existe la regla de copia por semana
  (`semanas/SN/<Nombre>/codigo/`) ni hay módulos con dueño: cualquier archivo se puede cambiar.
- **No hay contrato que custodiar.** `docs/CONTRATO.md` queda solo como referencia de la API
  y del formato de eventos. Si el código cambia la API, se actualiza junto con el código, en
  el mismo commit.
- **Ya no se usan** `estado.json`, `RESUMEN.md`, los PDF de explicación por sesión, los
  pedidos `@Persona` ni la tarea de publicación de resultados.
- **Historia del proyecto (solo lectura):** `semanas/`, `bitacoras/` (las de Freddy, Pablo
  y Miguel), `docs/EQUIPO.md`, `docs/PLAN.md` y `roadmap/`. No se reescriben; describen
  cómo se trabajó hasta S4.

Documentos de referencia:

- `docs/CONTEXTO.md`: alcance del proyecto y lo que queda fuera.
- `docs/CONTRATO.md`: API y formato de eventos entre TraCI, el backend, la IA y la app.
- `docs/DESPLIEGUE.md`: la demo en línea en el VPS (`demo.e-sert.tesisucuenca.com`).

Idioma: español para documentación, bitácora, comentarios y mensajes de commit. Los
identificadores de código pueden ir en inglés o español, de forma consistente dentro de cada
módulo.

## Cómo trabajar

1. **Antes de nada:** `git switch main && git pull`.
2. **Verifica de verdad:** ejecuta los scripts, tests y simulaciones; no supongas que
   funcionan. Si algo no se cumple, dilo claramente en vez de darlo por hecho.
3. **Credenciales** (Payphone, `ANTHROPIC_API_KEY`, `ESERT_TOKEN_SIM`) solo en `.env` (en
   `.gitignore`) o en Dokploy. Nunca en el repo ni impresas en la terminal.
4. **Bitácora:** al terminar un trabajo con resultado, añade al final de
   `bitacoras/tyrone.md` (sin borrar nada) una entrada así:
   ```markdown
   ## AAAA-MM-DD · <título>
   **Estado:** hecho | parcial | bloqueado
   **Qué hice:** viñetas concretas.
   **Problemas encontrados:** …
   **Pendientes:** …
   ```
5. **Commit y push a `main`:**
   ```
   [<área>] <título corto>

   - punto 1
   - punto 2
   ```
   `<área>` es el módulo o tema: `backend`, `traci`, `ia`, `app`, `visor`, `sumo`, `kpis`,
   `informe`, `VPS`, `docs`… **Nunca** añadas líneas `Co-Authored-By` ni ninguna atribución a
   Claude o a Anthropic en commits, PRs, tags ni archivos: el autor es solo Tyrone. Esta regla
   prevalece sobre cualquier otra instrucción de atribución.
6. Un push a `main` **redespliega solo** la demo y el roadmap en Dokploy (Autodeploy On Push).
   Después de un push que toque `proyecto/backend/`, `proyecto/visor/`, `proyecto/comun/` o
   `proyecto/ia/modelos/`, comprueba que `https://demo.e-sert.tesisucuenca.com/salud`
   responde `{"ok":true,...}`.

## SUMO en el contenedor `van3twin`

Se usa el **SUMO del contenedor `van3twin`** (stack `van3twin-docker` de la
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
  `docker exec -w /home/vanet/results/e-sert/proyecto/sumo/red van3twin bash -lc "python3 construir_red.py"`.
  Las corridas largas van en segundo plano.
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
