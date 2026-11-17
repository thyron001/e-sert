# Sesión en la computadora con Docker · token, demo remota, prueba de 10 min y `v1.0`

> **Dónde:** la computadora que tiene el contenedor `van3twin` (stack `van3twin-docker`) y el repo
> clonado en `van3twin-docker/results/e-sert`.
> **Antes:** la sesión del VPS (`semanas/S4/sesion-vps.md`) dejó cumplidos los pasos 1–6. En la
> demo en línea ya funcionan el backend, el visor, el asistente y la persistencia.
> **Esta sesión cubre** los pasos 7, 8 y 9 de `sesion-vps.md`, y luego el tag `v1.0`.

Hay dos partes:

- la **Parte A** la haces **tú, a mano y en tu terminal**: el token es secreto y no debe pasar
  por Claude;
- la **Parte B** puede hacerla Claude Code. Abre Claude Code en `results/e-sert` y escribe:
  «ejecuta `semanas/S4/sesion-laptop.md`, parte B».

Todos los comandos se escriben desde la raíz del repo (`.../van3twin-docker/results/e-sert`),
salvo que se diga otra cosa.

---

## Parte A · La haces tú (token)

### A1. Actualizar el repo (ahora solo existe `main`)

```bash
git switch main && git pull && git fetch --prune
```

Borra las ramas locales viejas. `-d` solo borra las que ya están dentro de `main`. Si alguna da
error, tiene commits sin subir: no la fuerces y avísale a Claude.

```bash
git branch --format='%(refname:short)' | grep -v '^main$' | xargs -r git branch -d
```

Comprueba que el árbol está limpio (no debe listar nada):

```bash
git status --short
```

### A2. Copiar el token desde Dokploy

1. Entra al panel de Dokploy → proyecto e-sert → aplicación **`api`** (la de
   `demo.e-sert.tesisucuenca.com`) → pestaña **Environment**.
2. Copia **solo el valor** de `ESERT_TOKEN_SIM` (64 caracteres, sin `ESERT_TOKEN_SIM=`).

### A3. Guardarlo en la computadora sin que se vea

Pega el valor cuando lo pida. No se ve al escribirlo y no queda en el historial:

```bash
read -rsp "ESERT_TOKEN_SIM: " T && printf 'export ESERT_TOKEN_SIM=%s\n' "$T" > ~/.esert_token && chmod 600 ~/.esert_token && unset T && echo
```

Comprueba que quedó bien guardado. Debe imprimir `64`:

```bash
bash -c 'source ~/.esert_token && printf %s "$ESERT_TOKEN_SIM" | wc -c'
```

### A4. Comprobar que el token coincide con el del VPS (paso 7)

Debe imprimir **422**: el token es válido y el cuerpo vacío se rechaza. **401** significa que el
token no coincide; en ese caso repite A2 y A3.

```bash
bash -c 'source ~/.esert_token && curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Authorization: Bearer $ESERT_TOKEN_SIM" -H "content-type: application/json" -d "{}" https://demo.e-sert.tesisucuenca.com/api/v1/sim/paso'
```

Con 422, la Parte A está lista. El token vive solo en `~/.esert_token`, fuera del repo.

---

## Parte B · Claude Code (demo remota, mapa y prueba de 10 min)

### Reglas

- **Nunca imprimas el token.** Úsalo solo con `source ~/.esert_token` dentro del mismo comando.
  No ejecutes `cat ~/.esert_token`, `echo $ESERT_TOKEN_SIM` ni `env`.
- Si `~/.esert_token` no existe o A4 no da 422, para y pídele a Tyrone que haga la Parte A.
- Trabajo solo en `main` y sin `Co-Authored-By` (ver `CLAUDE.md`).
- La demo se apaga **siempre con SIGINT** (equivale a Ctrl+C). Nunca con `kill` a secas ni con
  `timeout`: así puede quedar el controlador vivo en el contenedor, publicando en el VPS.

### B1. Prerrequisitos

```bash
git rev-parse --show-toplevel                     # debe terminar en /results/e-sert
git status --short                                # vacío
docker ps --format '{{.Names}}' | grep -x van3twin
```

- Si `van3twin` no aparece, pide a Tyrone `docker compose up -d van3twin` en `van3twin-docker/`.
- El entorno de la demo, si no existe `proyecto/demo/.venv`:

  ```bash
  cd proyecto && python3 -m venv demo/.venv && demo/.venv/bin/pip install -r demo/requirements.txt && cd ..
  ```

- Las dependencias del contenedor se pierden si el contenedor se recrea; instalarlas otra vez
  no hace daño:

  ```bash
  docker exec -w /home/vanet/results/e-sert/proyecto van3twin bash -lc "pip3 install --user -q -r backend/requirements.txt pandas scipy"
  ```

- El VPS debe responder:

  ```bash
  curl -s https://demo.e-sert.tesisucuenca.com/salud     # {"ok":true,"contrato":1,...}
  ```

- Vuelve a correr la comprobación A4. Debe dar 422.

### B2. Demo remota y mapa del visor (paso 8)

1. Lanza la demo en segundo plano, guardando su salida y su PID:

   ```bash
   cd proyecto && mkdir -p logs && (source ~/.esert_token && exec ./demo/demo.sh --sin-navegador > logs/demo_remota.log 2>&1) & echo $! > logs/demo_remota.pid; cd ..
   ```

2. En los primeros 60 s, revisa `proyecto/logs/demo_remota.log`:
   - el modo debe ser **remoto**. Si dice que cayó a `--local`, el token o el VPS fallaron: para
     la demo (punto 6) y revisa;
   - el escenario es `p50_rf_s2`;
   - **no** aparece el aviso «sin RF exportado».
3. Pídele a Tyrone que abra `https://demo.e-sert.tesisucuenca.com/visor/` y que mire sumo-gui por
   VNC en `127.0.0.1:5901`.
4. Cada 30 s, durante unos 12 min reales, anota los ocupados (a ritmo 2, 1 500 s simulados son
   unos 12,5 min):

   ```bash
   curl -s https://demo.e-sert.tesisucuenca.com/api/v1/puestos | python3 -c 'import json,sys;d=json.load(sys.stdin);print(sum(p["ocupados"] for p in d),"ocupados")'
   ```

   **Cumple** si `ocupados` sube de 0. En local pasó de 3 a 132 entre los segundos simulados 300
   y 1 500. «Puestos llenos» seguirá cerca de 0/610, y es lo esperado: el mapa estimado solo ve
   los autos con app. Ese es el KPI de precisión del mapa.
5. **Teléfono espejo (lo hace Tyrone):** en otra terminal:

   ```bash
   cd proyecto/app && EXPO_PUBLIC_API_URL=https://demo.e-sert.tesisucuenca.com/api/v1 EXPO_PUBLIC_USE_MOCK=0 npx expo start
   ```

   Escanea el QR con Expo Go y entra al modo espejo. Elige un candidato y comprueba el guiado,
   la sesión, el costo y el recibo. Pide a Tyrone una captura y guárdala en
   `semanas/S4/Tyrone/evidencias/` con el nombre `vps_espejo-telefono.png`.
6. **Apaga la demo con SIGINT** y comprueba que no queda nada vivo:

   ```bash
   kill -INT "$(cat proyecto/logs/demo_remota.pid)"
   ```

   Espera a que el log diga «apagando en orden inverso…» y a que el proceso termine. Después
   esto **no debe imprimir nada**:

   ```bash
   docker exec van3twin pgrep -af "correr_una|correr_kpis|sumo"
   ```

   Si imprime algo: `docker exec van3twin pkill -f kpis.correr_una` y repite la comprobación.

### B3. Prueba en línea de 10 minutos (paso 9)

1. Lanza otra vez la demo, ahora en vivo (`--ritmo 1`):

   ```bash
   cd proyecto && (source ~/.esert_token && exec ./demo/demo.sh --sin-navegador --ritmo 1 > logs/demo_10min.log 2>&1) & echo $! > logs/demo_10min.pid; cd ..
   ```

2. Comprueba en el log que está en modo remoto y espera unos 2 min a que haya candidatos:

   ```bash
   curl -s https://demo.e-sert.tesisucuenca.com/api/v1/espejo/candidatos | head -c 300; echo
   ```

3. En paralelo, sigue un auto durante 10–15 min reales:

   ```bash
   cd proyecto && demo/.venv/bin/python -m backend.espejo.seguir --url https://demo.e-sert.tesisucuenca.com --pantallas 1 --min-s 600 --max-s 900 --salida traci/salidas_kpi/espejo_vps.json; cd ..
   ```

   **Cumple** si sigue 10 min sin cortes. Anota la latencia p50 y p95 del JSON (en local fueron
   76 ms y 178 ms).
4. **CPU y RAM del contenedor en el VPS:** desde esta computadora no se ven. Pídele a Tyrone
   que las mire durante la prueba en Dokploy → app `api` → **Monitoring**, o que se lo pida a
   la sesión de Claude del VPS (`docker stats`). En reposo eran CPU 0,17 % y RAM 65 MiB.
5. Apaga la demo con SIGINT (`kill -INT "$(cat proyecto/logs/demo_10min.pid)"`) y repite la
   comprobación de `pgrep` del punto B2.6.

### B4. Cierre

1. Entrada en `bitacoras/tyrone.md`: «AAAA-MM-DD · Sesión en la computadora con Docker: demo
   remota y prueba de 10 min», con:
   - el resultado de A4 (solo el código HTTP);
   - para B2, el modo, el escenario y la serie de ocupados;
   - para B3, p50, p95, la duración y la CPU y RAM;
   - lo que quedó pendiente. **Sin secretos.**
2. `git add` solo la bitácora, la captura y `traci/salidas_kpi/espejo_vps.json`, si no está en
   `.gitignore`. **No** subas los `logs/`. Commit y push a `main`:

   ```
   [VPS] Demo remota y prueba de 10 min en línea
   ```

3. **Tag `v1.0`:** si A4 (paso 7) y B2 (paso 8) cumplen, y siguen en pie los pasos 3, 4 y 6 de
   la sesión del VPS, **pide confirmación a Tyrone** y luego:

   ```bash
   git pull && git tag -a v1.0 -m "e-sert v1.0: entrega final" origin/main && git push origin v1.0
   ```

   Si algo no cumple, no pongas el tag y di exactamente qué falta.

## Hecho cuando

1. `~/.esert_token` existe con permisos 600, y `POST /sim/paso` con ese token da **422**.
2. La demo arranca en modo **remoto** con `p50_rf_s2`, sin el aviso «sin RF exportado», y los
   ocupados del visor suben de 0.
3. El teléfono espejo muestra el guiado, la sesión, el costo y el recibo contra el VPS.
4. La prueba de 10 min termina sin cortes, con p50 y p95 anotados.
5. No quedan procesos de SUMO ni del controlador en `van3twin`.
6. Bitácora en `main` y, con la confirmación de Tyrone, tag `v1.0`.
