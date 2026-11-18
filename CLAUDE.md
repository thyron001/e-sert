# e-sert: guía para Claude Code

App de parqueo para la zona SERT del Centro Histórico de Cuenca (Redes Vehiculares,
Universidad de Cuenca), construida con SUMO, TraCI y un clasificador de movimiento.

## Forma de trabajo (desde el 2026-11-17)

El trabajo en equipo terminó con la unificación final. Desde ahora:

- **Una sola persona (Tyrone), una sola computadora (el VPS) y una sola sesión de Claude Code.**
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

## Todo corre en el VPS (desde el 2026-11-18)

La única computadora es el **VPS** (Dokploy, 1 vCPU, 3,8 GiB de RAM + 2 GiB de swap). Claude
Code trabaja ahí, y ahí corren el backend, el visor, SUMO, las pruebas y los experimentos.

| Qué | Dónde |
|---|---|
| Repo (clon de trabajo) | `/root/van3twin-docker/results/e-sert` |
| SUMO para desarrollo, pruebas y experimentos | contenedor `van3twin` del VPS |
| Demo en línea | servicios `api`, `visor` y `sim` del proyecto `e-sert` de Dokploy, `https://demo.e-sert.tesisucuenca.com` |
| Clave del botón de la demo | `/root/.esert_clave_demo` (no la imprimas) |
| `sumo-gui` de la demo en el navegador | `https://sumo.tesisucuenca.com` (contraseña en `/root/.esert_clave_vnc`) |

### Contenedor `van3twin` del VPS

Reemplaza al `van3twin` de la materia con la misma interfaz: **SUMO 1.12**
(`SUMO_HOME=/usr/share/sumo`), **Python 3.10** y la carpeta `results/` montada en
`/home/vanet/results/`. Además trae **Node 20** y todas las dependencias del proyecto
(`proyecto/backend/requirements-*.txt`). Lo crea `herramientas/van3twin_vps.sh`, con la etapa
`dev` de `proyecto/sim/Dockerfile`. Si cambian las dependencias, vuelve a correr ese script.

| En el VPS | Dentro del contenedor |
|---|---|
| `/root/van3twin-docker/results/` | `/home/vanet/results/` |
| `/root/van3twin-docker/results/e-sert/` (este repo) | `/home/vanet/results/e-sert/` |

- **Todo lo que sea Python o Node del proyecto se ejecuta dentro del contenedor** (el VPS no
  tiene los paquetes del proyecto): SUMO, `netconvert`, `duarouter`, scripts con `traci` o
  `sumolib`, `pytest`, `node --test`, gráficas, experimentos. Desde la raíz del repo y con rutas
  relativas:

  ```bash
  docker exec -w /home/vanet/results/e-sert/<carpeta-relativa> van3twin bash -lc "<comando>"
  ```

  Por ejemplo, las pruebas del backend:
  `docker exec -w /home/vanet/results/e-sert/proyecto van3twin bash -lc "python3 -m pytest -q backend"`.
- `git` y la edición de archivos se hacen en el VPS (fuera del contenedor).
- Si `docker ps` no muestra `van3twin`: `herramientas/van3twin_vps.sh`.
- **No hay `sumo-gui` ni VNC**: usa `--sin-gui` en `demo.py`. Para ver la simulación, el visor;
  para evidencias, gráficas con matplotlib. `libsumo` sí está (wheel 1.12.0 de PyPI), así que
  `--libsumo` y `libsumo: true` funcionan como en el `van3twin` de la materia.
- **Recursos:** el contenedor está limitado a 1,5 GiB y 0,9 CPU, y el VPS comparte la CPU con
  otras apps (tesis, n8n…). Las corridas largas van en segundo plano y los experimentos con
  `--procesos 1`. No lances experimentos mientras corre la demo en línea.
- El código que corre con SUMO debe ser compatible con Python 3.10. Los archivos que escribe
  el contenedor son de `root`.
- Las salidas de SUMO van en carpetas `sumo/salidas/` (ignoradas por git) y nunca se suben.
- **Peatones:** por defecto solo bajan del auto los conductores de la app web. Los resultados del
  proyecto (KPIs, informe) ya están hechos con todos los peatones y no se regeneran; para
  reproducirlos, `--todos-los-peatones`.

### Demo en línea

- Cuatro servicios en Dokploy, cada uno con **Watch Paths** (detalle en `docs/DESPLIEGUE.md`):
  `api` (backend, `proyecto/backend/Dockerfile`, ligero), `visor` (nginx,
  `proyecto/visor/Dockerfile`), `sim` (SUMO + `sumo-gui` + noVNC, `proyecto/sim/Dockerfile`,
  pesado) y `Frontend` (roadmap). Un push solo redespliega los servicios cuyas carpetas
  cambiaron; **`sim` solo se reconstruye si cambian `proyecto/sim/`, `traci/`, `kpis/`, `sumo/`,
  `ia/`, `backend/nucleo/`, `backend/simulador/` o `comun/`**, y eso corta una simulación en curso.
- La demo se arranca y se detiene desde el visor (sección «Simulación en el servidor»), o con
  `POST /api/v1/demo/iniciar` y `/detener` con la cabecera `X-Clave-Demo`. El backend le pasa la
  orden a `sim` (`ESERT_URL_SIM`). Su `sumo-gui` se ve y se controla en
  `https://sumo.tesisucuenca.com`, por noVNC.
- **App web** en `https://demo.e-sert.tesisucuenca.com/app/` (QR en el visor): `visor/app/`,
  `backend/web/` y `traci/autos_web.py`. Tarifa: $0,25 por bloque de 30 min, prepago de 30 a
  120 min, con renovación automática (`docs/DESPLIEGUE.md`, «App web»).
- **Antes de un push que redespliegue `sim` o `api`**, comprueba que no haya una demo en curso:
  `curl -s https://demo.e-sert.tesisucuenca.com/api/v1/demo/estado` (fase `inactiva`).
- La API de Dokploy se usa con la clave de `/root/.dokploy_api_key` (cabecera `x-api-key`,
  `http://127.0.0.1:3000/api/...`); no la imprimas.

## Entorno

- Python 3.10 y Node 20 del contenedor `van3twin` para todo el proyecto.
- Las dependencias van en `requirements.txt` dentro de cada módulo; las de las imágenes, en
  `proyecto/backend/requirements-servidor.txt` y `proyecto/sim/requirements-{sim,dev}.txt`.
- App: Expo SDK estable, probada con Expo Go (`EXPO_PUBLIC_API_URL` apuntando al VPS).
- Usa `pathlib` y nunca rutas absolutas en el código.
