# Sesión VPS · cierre del proyecto: desplegar `main` final en `esert-demo` y comprobar la demo en línea

> **Quién la ejecuta:** la sesión de Claude Code de **Tyrone** conectada al VPS (Dokploy).
> Es la única con acceso al VPS, al DNS y a Payphone (`docs/DESPLIEGUE.md`).
> **Cuándo:** después de la unificación final del 2026-11-17 (`[S4-U][final]` en `main`).
> **Lee antes:** `CLAUDE.md`, `docs/DESPLIEGUE.md`, `docs/CONTRATO.md` (v1.4) y la entrada
> «S4 · Cierre · 2026-11-17» de `bitacoras/tyrone.md`.

## Reglas de esta sesión

- **Nunca imprimas, copies ni subas un secreto**: ni el token, ni las claves de Payphone, ni
  `ANTHROPIC_API_KEY`. Para saber si una variable existe, mira su *nombre* en Dokploy o comprueba
  su efecto (por ejemplo, un 401). Si hace falta compararlo, compara su SHA-256, no el valor.
- No cambies código de la app ni del backend en el VPS. Si algo falla por código, arréglalo en el
  repo, directamente en `main`, con pruebas; el push redespliega.
- Todo lo que se pruebe con dinero va en **modo de pruebas** de Payphone: nada de dinero real.
- Al terminar, aplica el protocolo de cierre de `CLAUDE.md`: bitácora, commit y push. En vez de
  `estado.json` de una sesión del plan, añade una entrada en `bitacoras/tyrone.md`.

## Qué cambió en `main` y obliga a redesplegar

1. **El asistente queda montado:** `POST /api/v1/asistente/interpretar` hoy da 404 en el VPS.
   - La imagen copia `proyecto/sumo/demanda/destinos.csv` a `/srv/datos/destinos.csv` (`ESERT_DESTINOS_CSV`).
   - Instala además `anthropic`, `python-dotenv` y `rapidfuzz` (`requirements-servidor.txt`).
2. **Mapa estimado del controlador** (contrato v1.4 §4.4, campo opcional `puestos` en
   `/sim/paso`): el visor dejaba la ocupación en 0/610 durante toda la demo. Ahora el backend suma
   el mapa que manda el controlador.
3. **RF en el contenedor sin `scikit-learn`:** `proyecto/ia/modelos/rf_final.plano.npz`
   (SHA-256 `e0db6d5e84de4036a22631d6c6786953cd59e5dcd85522aeaf37e4ca7ed0dabf`) está versionado.
   - La demo y las corridas lo usan dentro de `van3twin`, en la laptop.
   - **El VPS no clasifica**: el backend no importa `ia/`. Por eso **no hace falta** añadir
     `scikit-learn` ni `validacion.py`/`bosque_plano.py` a la imagen (pedidos 1 y 2 de Pablo en
     `bitacoras/pablo.md`, cerrados como «no aplica»).

## Pasos

### 1. Estado de partida (solo lectura)

- `git fetch origin && git log -1 --format='%h %s' origin/main`: anota el commit que se va a
  desplegar.
- En Dokploy, app `esert-demo`, comprueba que:
  - sigue la rama `main` con **Autodeploy On Push**;
  - usa el Dockerfile `proyecto/backend/Dockerfile` con contexto en la raíz del repo;
  - tiene el dominio `demo.e-sert.tesisucuenca.com` con HTTPS.
- Anota el commit desplegado ahora y el estado del contenedor (`healthy` o no).

### 2. Variables y volumen (Dokploy → Environment / Volumes)

| Variable | Valor esperado | Cómo comprobar sin ver el valor |
|---|---|---|
| `ESERT_TOKEN_SIM` | token largo y aleatorio (ya existe: `pytest -m vps` dio 401 sin token el 2026-11-17) | el nombre existe; paso 4 |
| `ESERT_DB_URL` | `sqlite:////data/esert.db` | el nombre y el valor (no es secreto) |
| volumen `/data` | montado y persistente | paso 6 (persistencia) |
| `PAYPHONE_MODO` | `pruebas` | no es secreto |
| `PAYPHONE_TOKEN`, `PAYPHONE_STORE_ID` | credenciales **de pruebas** | existen los nombres |
| `ANTHROPIC_API_KEY` | opcional: con ella el asistente usa el LLM; sin ella, reglas | existe o no; paso 5 |
| `ESERT_CORS_ORIGENES` | la que ya esté (la app usa el mismo origen) | — |

- La **URL de respuesta** de la app de Payphone debe ser
  `https://demo.e-sert.tesisucuenca.com/api/v1/pagos/retorno`, con Dominio Web
  `https://demo.e-sert.tesisucuenca.com` (pedido de Miguel, `bitacoras/miguel.md`).
- Si falta algo, créalo o corrígelo y anótalo, sin el valor.

### 3. Redesplegar `main`

- Lanza el deploy de `esert-demo`, o confirma que el autodeploy ya tomó el commit del paso 1.
- En el log de build deben aparecer `anthropic` y `rapidfuzz` instalados, y la copia de
  `destinos.csv` sin error.
- Espera a que el contenedor quede `healthy` (healthcheck `GET /salud`).
- Si el build falla, copia el error en la bitácora, corrige en el repo y repite.

### 4. Comprobaciones desde fuera

Corre esto desde `proyecto/` en la computadora de la demo. En la de Tyrone, con ROS instalado,
antepone `env -u PYTHONPATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.

```bash
curl -s https://demo.e-sert.tesisucuenca.com/salud                          # {"ok":true,"contrato":1,...}
curl -s -o /dev/null -w '%{http_code}\n' -L https://demo.e-sert.tesisucuenca.com/visor   # 200
ESERT_URL_PUBLICA=https://demo.e-sert.tesisucuenca.com python -m pytest -c backend/pytest.ini --rootdir . backend/tests -m vps -q   # 6 passed
curl -s -X POST -H 'content-type: application/json' \
  -d '{"texto":"cerca de la Catedral Nueva una hora"}' \
  https://demo.e-sert.tesisucuenca.com/api/v1/asistente/interpretar         # 200, destino Catedral Nueva, 60 min
curl -s -o /dev/null -w '%{http_code}\n' https://demo.e-sert.tesisucuenca.com/api/v1/pagos/no-existe   # 404 (ruta montada)
```

- **WebSocket del espejo a través de Traefik** (pedido de Freddy y de Miguel): con `websockets`
  de Python, conecta a `wss://demo.e-sert.tesisucuenca.com/ws/espejo/x`. Debe responder
  `espejo_fin` con motivo `no_existe` y cerrar con el código **4404**.

### 5. Asistente con LLM (opcional)

- Si existe `ANTHROPIC_API_KEY`, la respuesta del paso 4 debe traer `"fuente": "llm"`; si no
  existe, `"reglas"`. Las dos son válidas para la demo.
- El modelo por defecto es `claude-haiku-5-5` (`ASISTENTE_MODELO` lo cambia).

### 6. Persistencia del libro (pedido VPS-2 de Freddy)

- Usa un usuario de prueba, por ejemplo `sim_vps_prueba_<fecha>` (el contrato exige el prefijo `sim_` o `app_<uuid>`).
  - Con `POST /api/v1/billetera/vps_prueba_<fecha>/recarga {"monto": 5}`, el saldo sube a 5.
- Reinicia el contenedor desde Dokploy (no redespliegues) y consulta
  `GET /api/v1/billetera/vps_prueba_<fecha>`.
  - **El saldo debe seguir en 5.** Si vuelve a 0, el volumen `/data` no está montado:
    corrígelo y repite.

### 7. Token en la computadora de la demo

- En la laptop de la demo, guarda el **mismo** valor de Dokploy fuera del repo, sin que se vea:

  ```bash
  read -rsp "ESERT_TOKEN_SIM: " T && printf 'export ESERT_TOKEN_SIM=%s\n' "$T" > ~/.esert_token && chmod 600 ~/.esert_token && unset T
  ```

- Comprueba que coincide sin mostrarlo: un `POST /api/v1/sim/paso` con
  `Authorization: Bearer $ESERT_TOKEN_SIM` y cuerpo inválido (`{}`) debe dar **422**. Un 401
  significa que el token no coincide.

### 8. Demo guiada en línea y mapa (el antiguo «0/610»)

- Requisitos:
  - la carpeta del repo está en `main` (`git status` limpio; el video del plan B no debe estar
    dentro del repo);
  - el contenedor `van3twin` está arriba;
  - `demo/.venv` está creado (`demo/README.md`).
- Lanza la demo:

  ```bash
  source ~/.esert_token && cd proyecto && ./demo/demo.sh          # modo remoto (por defecto)
  ```

- Debe arrancar con el escenario `p50_rf_s2`, **sin** el aviso «sin RF exportado».
- Abre `https://demo.e-sert.tesisucuenca.com/visor/`. En otra terminal, cada 30 s:

  ```bash
  curl -s https://demo.e-sert.tesisucuenca.com/api/v1/puestos | python3 -c 'import json,sys;d=json.load(sys.stdin);print(sum(p["ocupados"] for p in d),"ocupados")'
  ```

  `ocupados` debe **subir de 0** a los pocos minutos simulados. En local, con ritmo 30×, pasó de
  3 a 132 entre los segundos simulados 300 y 1 500.
- **Puestos llenos:** casi siempre seguirá en 0/610, y es lo esperado. El mapa estimado solo ve
  los autos con app, cerca del 2 % de las plazas, mientras la verdad de SUMO tiene 80 % de fondo
  y entre 99 y 219 puestos llenos. Esa diferencia es el KPI de precisión del mapa: en la
  exposición se explica, no es un fallo.
- Teléfono espejo: con Expo Go y `EXPO_PUBLIC_API_URL=https://demo.e-sert.tesisucuenca.com/api/v1`,
  elige un candidato y comprueba guiado, sesión, costo y recibo.
- Termina la demo **con Ctrl+C**. Comprueba que no quedan procesos con
  `docker exec van3twin pgrep -af "correr_una|correr_kpis|sumo"`, que no debe imprimir nada.
  - Matar el lanzador con `kill` o `timeout` puede dejar el controlador vivo en el contenedor y
    publicando en el VPS. En ese caso: `docker exec van3twin pkill -f kpis.correr_una`.

### 9. Prueba en línea de 10 minutos (criterio S3-3 de Freddy)

- Con la demo del paso 8 corriendo a `--ritmo 1`, en paralelo y desde `proyecto/`:

  ```bash
  python3 -m backend.espejo.seguir --url https://demo.e-sert.tesisucuenca.com --pantallas 1 --min-s 600 --max-s 900 --salida traci/salidas_kpi/espejo_vps.json
  ```

- Meta: 10 min sin cortes, con la latencia p50 y p95 del JSON. En local fue p50 76 ms y
  p95 178 ms.
- Durante la prueba, anota la CPU y la RAM del contenedor `esert-demo`, desde Dokploy o con
  `docker stats` en el VPS.

### 10. Límite de tasa de recargas (opcional, `DESPLIEGUE.md`)

- No está implementado y el contrato no tiene código de error para él.
- Para v1.0 basta con documentarlo como trabajo futuro, porque la billetera es solo de prueba.
- Si se quiere, la forma sin tocar el contrato es un *middleware* `rateLimit` de Traefik en
  Dokploy sobre la ruta `/api/v1/billetera/*/recarga` y `/api/v1/pagos/preparar`.

### 11. Cierre y tag

- Entrada en `bitacoras/tyrone.md`: «S4 · Sesión VPS · AAAA-MM-DD», con:
  - el resultado de cada paso (cumple o no, con la salida del comando, **sin secretos**);
  - el commit desplegado;
  - las latencias y el consumo de CPU y RAM;
  - lo que quedó pendiente.
- Commit y push directamente en `main`.
- **Tag `v1.0`:** si los pasos 3, 4, 6, 7 y 8 cumplen, pide confirmación a Tyrone y luego:

  ```bash
  git tag -a v1.0 -m "e-sert v1.0: entrega final" origin/main && git push origin v1.0
  ```

  Si algo no cumple, no pongas el tag y di exactamente qué falta.

## Hecho cuando

1. `esert-demo` corre el commit final de `main` y está `healthy`.
2. `pytest -m vps` da 6/6; `/asistente/interpretar` responde 200; `/ws/espejo/x` cierra con 4404.
3. El saldo de prueba sobrevive a un reinicio del contenedor.
4. La demo remota publica con el token de la laptop (sin 401) y el mapa del visor sube de 0
   ocupados.
5. La prueba de 10 min termina sin cortes, con latencias anotadas.
6. Bitácora escrita y, si 1–4 cumplen y Tyrone confirma, tag `v1.0` en `main`.
