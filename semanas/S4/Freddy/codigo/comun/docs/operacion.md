# Guía de operación de e-sert

Esta guía explica cómo levantar cada pieza por separado, cómo configurarla y qué hacer cuando
algo falla. Las rutas son relativas a `proyecto/`, la versión unificada. Para la demo en línea,
consulta también `docs/DESPLIEGUE.md`.

## 1. Piezas y dónde corren

| Pieza | Dónde corre | Puerto | Archivo principal |
|---|---|---|---|
| Backend FastAPI (API, WS y visor estático) | computadora o VPS | 8000 | `backend/api/main.py` |
| SUMO y controlador TraCI | contenedor `van3twin` | TraCI interno; VNC 5901 para `sumo-gui` | `traci/correr_kpis.py`, `traci/correr_guiado.py` |
| IA (clasificador de modo) | importada por el controlador | — | `ia/inferencia.py` |
| Visor | servido por el backend en `/visor` | 8000 | `visor/` |
| App Expo | teléfono con Expo Go | 8081 (Metro) | `app/` |
| Pagos (Payphone) | dentro del backend, si existe `backend/pagos/` | 8000 | `backend/pagos/rutas.py` |

## 2. Levantar cada pieza

### Backend

```bash
cd proyecto
python -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

Para comprobar que responde:

- `curl http://localhost:8000/salud`, que debe devolver `{"ok":true,"contrato":1,...}`;
- la documentación interactiva en `http://localhost:8000/docs`;
- el visor en `http://localhost:8000/visor/`.

### SUMO y controlador (dentro del contenedor)

```bash
cd van3twin-docker && docker compose up -d van3twin          # una vez
docker exec van3twin pip3 install --user -r e-sert/proyecto/traci/requirements.txt \
    -r e-sert/proyecto/backend/requirements-servidor.txt     # tras recrear el contenedor
docker exec -w /home/vanet/results/e-sert/proyecto -e ESERT_TOKEN_SIM=$ESERT_TOKEN_SIM van3twin \
  bash -lc "python3 -m traci.correr_kpis --id p50_rf_s1 --hasta 1800 --publicar http://$HOST:8000 --ritmo 1"
```

- `$HOST` es la computadora vista desde el contenedor. Se obtiene así:
  `docker exec van3twin bash -lc "getent hosts host.docker.internal || ip route | awk '/default/{print \$3}'"`.
- Para la demo en línea se usa `--publicar https://demo.e-sert.tesisucuenca.com`.
- `--ritmo 1` corre en tiempo real; sin esa opción, SUMO va lo más rápido que puede.
- Para ver `sumo-gui`, usa un cliente VNC en `127.0.0.1:5901`.

### App

```bash
cd proyecto/app && npm install
EXPO_PUBLIC_API_URL=http://<ip-de-la-computadora>:8000 npx expo start
```

Escanea el QR con Expo Go. El teléfono debe estar en la misma red que la computadora, o se
usa la URL pública de la demo.

### Pruebas

```bash
cd proyecto
backend/.venv/bin/python -m pytest backend/tests -q                 # rápidas, menos de 60 s
backend/.venv/bin/python -m pytest -c backend/pytest.ini backend/tests traci/tests -m e2e
backend/.venv/bin/python -m pytest backend/tests -m vps             # humo contra la demo
backend/.venv/bin/python comun/docs/verificar_contrato_api.py       # API contra el contrato
```

## 3. Variables de entorno

Todas van en `.env` o en el entorno del proceso. **Nunca en el repo**: `.env` está en
`.gitignore`, y en Dokploy se cargan en Environment.

| Variable | Pieza | Por defecto | Para qué |
|---|---|---|---|
| `ESERT_DB_URL` | backend | `sqlite:///./e-sert.db` | Base de datos; en el VPS, `sqlite:////data/esert.db` |
| `ESERT_PUESTOS_CSV` | backend | `proyecto/sumo/parqueos/puestos.csv`, o un mock de 20 puestos | Puestos SERT |
| `ESERT_TOKEN_SIM` | backend y controlador | sin token, **las rutas 🔒 quedan abiertas** | Protege `/interno/snapshot`, `/sim/*` y `/sesiones/{id}/transicion` |
| `ESERT_CORS_ORIGENES` | backend | `*` | Orígenes permitidos, separados por comas |
| `ESERT_VISOR_DIR` | backend | `proyecto/visor` si existe | Carpeta que se sirve en `/visor` |
| `PAYPHONE_MODO` | pagos | `mock` (`backend/pagos/payphone.py`) | `mock` (formulario simulado) o `pruebas` |
| `PAYPHONE_TOKEN`, `PAYPHONE_STORE_ID` | pagos | — | Credenciales de Payphone, solo en `.env` o Dokploy |
| `ESERT_URL_PUBLICA` | pagos y pruebas `vps` | `https://demo.e-sert.tesisucuenca.com` | Base de la `responseUrl` y de la prueba de humo |
| `ESERT_IA_DIR` | controlador | si falta: `traci/escenario/pablo` (copia de Pablo, si existe) y luego `proyecto/` | Dónde buscar el paquete `ia` (`traci/clasificacion.py:buscar_ia`) |
| `ESERT_CLASIFICADOR` | IA | lo fija `correr_kpis` según el id (`rf` o `umbral`) | Fuerza el umbral |
| `ESERT_E2E_HASTA` | pruebas e2e | `1800` | Segundos simulados de `test_simulacion_completa` |
| `EXPO_PUBLIC_API_URL` | app | — | URL del backend |
| `SUMO_HOME` | contenedor | `/usr/share/sumo` | Herramientas de SUMO (`traci`, `sumolib`) |

## 4. Base de datos

- Es un archivo SQLite. Las tablas se crean solas al arrancar (`BaseDatos`), y los puestos se cargan desde el CSV.
- Para **empezar de cero en local**, para el backend y borra `e-sert.db`.
- En el VPS, la base está en el volumen `/data`, así que sobrevive a los redeploys.
- **Copia de seguridad:** `sqlite3 /data/esert.db ".backup /data/esert-$(date +%F).db"`.
- **Consulta rápida:** `sqlite3 e-sert.db "select tipo, count(*), sum(monto) from movimientos group by tipo"`. Los montos están en centavos.
- El controlador **no** usa esta base: tiene su propio núcleo en memoria (decisión D1).

## 5. Logs

| Pieza | Dónde | Qué mirar |
|---|---|---|
| Backend | salida estándar de `uvicorn`; en Dokploy, en la pestaña Logs | `e-sert API v… · BD … · N puestos · pagos sí/no` al arrancar; los 500 se registran con su traza |
| Controlador | salida estándar; cada 300 s simulados imprime el progreso | Al final, un JSON con `sesiones_maquina`, `kpis` y `publicador` (enviados y descartados) |
| Controlador (CSV) | `traci/salidas/` (ignorada por git) | `ventanas_*.csv` (modo clasificado frente al real), `transiciones_*.csv`, `falsas_liberaciones_*.csv`, `kpis_*` |
| Resumen de corrida | `traci/salidas_kpi/ejemplo_<id>.json` | KPIs que se suben al repo |
| Pruebas e2e | `--junitxml=e2e.xml` y el log del controlador en el `tmp_path` de pytest | Duración por test y mensajes de fallo |

## 6. Fallas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `docker: command not found` en WSL | Falta la integración WSL de Docker Desktop | Docker Desktop → Settings → Resources → WSL integration |
| `No such container: van3twin` | El contenedor no está creado | `docker compose up -d van3twin` en `van3twin-docker` |
| `ModuleNotFoundError: httpx` (o `pandas`, `pydantic`…) en el contenedor | Se recreó el contenedor | `pip3 install --user -r …/requirements.txt` (sección 2) |
| El contenedor no llega al backend (`urlopen` falla) | El backend escucha en `127.0.0.1`, o un firewall bloquea | Arrancar con `--host 0.0.0.0` y usar `host.docker.internal` o la puerta de enlace |
| `401 TOKEN_SIM_INVALIDO` al publicar | Tokens distintos en el backend y en el controlador | Usar el mismo `ESERT_TOKEN_SIM` en los dos |
| La demo acepta snapshots sin token | `ESERT_TOKEN_SIM` no está configurado en Dokploy | Configurarlo; `pytest -m vps` lo detecta |
| `400 CONTRATO_INCOMPATIBLE` | El cliente manda otra `X-Contrato-Version` | Actualizar el cliente al contrato 1 |
| El visor se queda congelado | El controlador se detuvo o el snapshot llega con un `t_sim` menor al último + 1 s | Relanzar el controlador; un `t_sim` menor reinicia el reloj |
| Casi todas las sesiones se cierran en falso | Falta `ia/modelos/rf_v1.joblib` y el umbral confunde caminar con ir en auto por el ruido del GPS | Publicar el modelo; para diagnosticar, `traci.tests.e2e.escenario_cierre --guardar DIR --sigma N` |
| `SUMO` se cae al arrancar (`malloc_consolidate`) | El `.sumocfg` tiene rutas relativas a una carpeta equivocada | Usar rutas absolutas en el `.sumocfg` generado |
| Un `inf` rompe el JSON del snapshot | Posición inválida (−2^30) de un auto que sale del parkingArea | Ya se filtra con la última posición válida (S3-3) |
| `sumo-gui` no se ve | Falta el cliente VNC | Conectarse a `127.0.0.1:5901`; las capturas funcionan igual |
| La app no conecta desde el teléfono | Usa `localhost`, o el teléfono está en otra red | `EXPO_PUBLIC_API_URL` con la IP de la computadora o la URL pública |
| No se renderizan los diagramas | No hay Node ≥ 18 ni Docker | `npm i -g @mermaid-js/mermaid-cli@10.9.1` o `docker pull minlag/mermaid-cli:10.9.1` |
