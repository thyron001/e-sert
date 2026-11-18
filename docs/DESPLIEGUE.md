# Despliegue en el VPS (Dokploy)

El grupo tiene un VPS con Dokploy, el mismo de `tesisucuenca.com`. Hay dos aplicaciones:

| App en Dokploy | Dominio | Qué sirve | Dockerfile | Dueño |
|---|---|---|---|---|
| `esert-roadmap` | `e-sert.tesisucuenca.com` | Roadmap del equipo (ya funciona) | `Dockerfile` (raíz) | Tyrone |
| `esert-demo` | `demo.e-sert.tesisucuenca.com` | Backend FastAPI (`/api/v1`, `/ws/estado`) + visor (`/visor`) | `proyecto/backend/Dockerfile` | Tyrone |

## Accesos

Tyrone es la única persona del proyecto y tiene acceso al VPS, al panel de Dokploy, al DNS y a
la cuenta de Payphone (modo de pruebas). En Dokploy la app de la demo se llama `api`
(`esert-api-ya3sai`) y la del roadmap `Frontend` (`esert-frontend-klfae6`); las dos siguen
`main` con Autodeploy On Push. Las credenciales van en Dokploy → Environment o en un `.env`
local, nunca en el repo.

## Por qué el backend va en el VPS

1. **El teléfono espejo se conecta sin depender del Wi-Fi del aula**, sin túneles (`ngrok`,
   `expo --tunnel`) ni estar en la misma red que la laptop: le basta con datos móviles o
   cualquier Wi-Fi. La app usa `EXPO_PUBLIC_API_URL=https://demo.e-sert.tesisucuenca.com`.
   El teléfono **no se mueve**: sigue a un auto simulado (modo espejo, `CONTRATO.md` 6b).
2. **Payphone necesita una URL pública HTTPS** de retorno (*responseUrl*) para confirmar la
   recarga de prueba. En local no existe.
3. **El visor queda en línea**: el proyector, el profesor o cualquier teléfono abre
   `https://demo.e-sert.tesisucuenca.com/visor` y ve en vivo los autos y peatones de SUMO, los
   puestos y el auto que sigue el teléfono espejo, resaltado. Con un QR (solo un enlace
   abreviado) el profesor lo abre en su celular sin escribir la URL.

## Direcciones (desde el 2026-11-18)

- `https://e-sert.tesisucuenca.com/` → **visor** (servicio `visor`); `/api` y `/ws` del mismo dominio
  van al backend, así el visor funciona en la raíz.
- `https://e-sert.tesisucuenca.com/roadmap` → roadmap (servicio `Frontend`; Traefik quita el
  prefijo y Flask genera los enlaces con `ProxyFix`).
- `https://e-sert.tesisucuenca.com/app` → app web (QR del visor).
- `https://demo.e-sert.tesisucuenca.com/…` sigue funcionando igual (backend, `/visor`, `/app`).

## Visor 3D y elección del puesto (2026-11-18)

- El visor abre en **3D** (three.js, `visor/js/vista3d.js`): edificios de OpenStreetMap extruidos (2 o 3
  pisos), calles, parques, puestos punteados, autos estacionados y en movimiento, y el nombre de cada
  usuario de la app sobre su auto (clic en el nombre para seguirlo). Los botones 3D/2D de arriba a la
  derecha cambian al mapa 2D; `?vista=2d` abre en 2D. La escena sale de
  `sumo/red/exportar_3d.py` → `visor/datos/escena3d.json` (se regenera si cambia la red).
- La app web elige el puesto libre con la **ruta de manejo más corta** (`traci/autos_web.py`): compara
  por `findRoute` los 25 libres más cercanos en línea recta y prueba también el carril contrario. Antes
  tomaba el más cercano en línea recta y en calles de un solo sentido el auto daba vueltas
  (`informe_ieee/comparar_rutas.py`: de 478 m a 230 m de media).

## App web (`https://e-sert.tesisucuenca.com/app/`, 2026-11-18)

Pestañas, con la estética de la app Expo anterior (negro y rojo): **Buscar** (mapa y sesión, con la
línea de progreso Buscando → Guiado → Estacionado → A pie → Regresando → Saliendo), **Historial**,
**Billetera** (saldo, movimientos y «Recargar con Payphone», que vuelve a la app), **Probar IA** (el
GPS real del teléfono clasificado por el RF cada 5 s) y **Usuario** (los siete perfiles, $10 cada
uno). Al terminar una sesión la app vuelve a la pantalla inicial; el punto azul y el botón «Mi
posición» solo aparecen en el puesto. En `sumo-gui` (`traci/colores_gui.py`) los autos de la app van
en amarillo y resaltados, los que buscan en naranja/violeta/azul, el resto en gris, y los peatones de
la app en azul.


Reemplaza a la app Expo para la demo (la app Expo queda en `proyecto/app/` como historia). El
visor muestra su QR; quien lo escanea la abre en el navegador del teléfono. Todo es simulado:

- **Usuario:** cada navegador es un usuario `app_<uuid>` con **$5 de prueba**.
- **Buscar parqueadero cercano:** toca el mapa para poner su ubicación simulada; el backend ordena
  crear un auto propio en SUMO, que va por la **ruta real** al puesto libre más cercano (ocupación
  real de SUMO + reservas de otros usuarios web). El auto se ve en amarillo con su ruta.
- **Ya estacioné:** el número del puesto (o tocarlo en el mapa): el auto aparece estacionado ahí y
  el puesto queda reservado.
- **La IA:** el conductor del auto lleva el GPS emulado y el clasificador RF decide cuándo
  estacionó y se bajó (la app pide el tiempo) y cuándo volvió a manejar tras «Me voy» (se cierra).
- **Tarifa:** $0,25 por bloque de 30 min, prepago: 30, 60, 90 o 120 min, debitado al elegir. A 5
  min del final, alerta; en 0, se renueva sola (+30 min, +$0,25) hasta 120 min; en el máximo, el
  conductor vuelve y se va. Si no elige en 5 min simulados, se cobran 30 min.
- **El temporizador corre en tiempo simulado**: a ritmo 2, 30 min son 15 min reales.
- **Ritmo en vivo:** el selector del visor (1×, 2×, 5×, 10×) cambia la velocidad en plena corrida
  (`POST /api/v1/demo/ritmo`; viaja al controlador en `RespuestaSnapshot.ritmo`). Medido con
  `sumo-gui`: 1× → 1,0×, 5× → 4,5×, **10× → 6,2× real** (tope de la CPU del VPS).
- **Peatones solo de la app (en todo el proyecto, desde el 2026-11-18):** solo bajan del auto los
  conductores de la app web; los demás se quedan dentro y se van al terminar su estadía (la IA
  sigue con su teléfono en el auto y cierra con ESTACIONADO → SALIENDO). Vale para la demo en
  línea, la demo local y los experimentos. Los resultados del proyecto ya se generaron con todos
  los peatones; `--todos-los-peatones` (en `kpis.correr_una` y `traci.correr_kpis`) los reproduce.
- **Mi posición:** en la app, el teléfono del conductor es un punto azul que late; el botón
  flotante alterna el centro del mapa entre «Mi vehículo» y «Mi posición».
- La simulación tiene que estar corriendo (botón «Iniciar» del visor).
- Código: `proyecto/visor/app/` (página), `proyecto/backend/web/` (API `/api/v1/web/*`),
  `proyecto/traci/autos_web.py` (autos en SUMO). Mapa compartido con el visor:
  `proyecto/visor/js/mapa_esert.js` (satélite, nombres de calles de la red de SUMO, puestos en
  líneas punteadas, autos estacionados en sus plazas y autos orientados). La geometría sale de
  `sumo/parqueos/exportar_puestos_geo.py` → `visor/datos/{puestos,calles}_geo.json`.

## Arquitectura de la demo (desde el 2026-11-18: servicios separados en el VPS)

El proyecto `e-sert` de Dokploy (entorno `production`) tiene cuatro servicios. Cada uno tiene
**Watch Paths**: un push a `main` solo redespliega el servicio cuyas carpetas cambiaron.

| Servicio (appName) | Qué hace | Imagen | Dominio | Se redespliega si cambia |
|---|---|---|---|---|
| `api` (`esert-api-ya3sai`) | Backend FastAPI: API, WebSocket, billetera, pagos, asistente; SQLite en el volumen `/data` | `proyecto/backend/Dockerfile` (python:3.11-slim, ~230 MB) | `demo.e-sert.tesisucuenca.com` | `proyecto/backend/**`, `proyecto/comun/**`, `puestos.csv`, `destinos.csv` |
| `visor` (`esert-visor-p5kz4t`) | Visor web y app web, estáticos (nginx) | `proyecto/visor/Dockerfile` (~55 MB) | `demo.e-sert.tesisucuenca.com/visor` y `/app` | `proyecto/visor/**` |
| `sim` (`esert-sim-ygqubj`) | SUMO 1.12 + controlador TraCI + `sumo-gui` (Xvfb + noVNC) + servicio de control en :8100 | `proyecto/sim/Dockerfile` (Ubuntu 22.04, ~1,5 GB) | `sumo.tesisucuenca.com` (puerto 6080) | `proyecto/sim/**`, `traci/**`, `kpis/**`, `sumo/**`, `ia/**`, `backend/nucleo/**`, `backend/simulador/**`, `comun/**` |
| `Frontend` (`esert-frontend-klfae6`) | Roadmap | `Dockerfile` (raíz) | `e-sert.tesisucuenca.com` | `Dockerfile`, `roadmap/**`, `docs/**`, `bitacoras/**`, `semanas/**` |

```
 Navegador ── /visor ──────────────────────► visor (nginx)
          └─ /api/v1, /ws ─────────────────► api (FastAPI + SQLite)
             «Iniciar» (X-Clave-Demo) ──► api ── POST http://esert-sim-ygqubj:8100/iniciar (token) ──► sim
                                                                    sim: correr_una + sumo-gui en :99
             api ◄── POST /api/v1/sim/paso (token, red interna http://esert-api-ya3sai:8000) ── sim
 sumo.tesisucuenca.com ── noVNC (:6080, contraseña VNC) ───────────────────────────────────► sim
 Teléfono espejo / Payphone ──────────► api
```

- **El botón del visor no cambió:** `/api/v1/demo/{estado,iniciar,detener}` siguen en el backend,
  que comprueba `ESERT_CLAVE_DEMO` y le pasa la orden a `sim` por la red interna
  (`ESERT_URL_SIM`, autenticado con `ESERT_TOKEN_SIM`). Sin `ESERT_URL_SIM` (desarrollo), el
  backend lanza SUMO en su propio proceso (`GestorSimulacion`).
- **`sim`** (`backend/simulador/servicio.py` + `proyecto/sim/arranque.sh`): levanta la pantalla
  virtual (Xvfb :99 + fluxbox + x11vnc + noVNC en :6080) y el servicio de control en :8100, que
  solo se usa dentro de Dokploy. El controlador publica en el backend con `ESERT_URL_BACKEND`.
- La clave del botón está en `/root/.esert_clave_demo` (`cat` solo en tu terminal). Sin
  simulación corriendo, SUMO no gasta CPU; `sim` en reposo usa ~100 MiB.
- **`sumo-gui` en el navegador: `https://sumo.tesisucuenca.com`**, maximizado y con la cámara en
  la zona SERT (`sumo/demanda/vista_vps.xml`). Tiene **control completo** (pausar, cambiar el
  retardo, mover la cámara, inspeccionar autos) y pide la contraseña `ESERT_CLAVE_VNC`
  (8 caracteres; en el VPS está en `/root/.esert_clave_vnc`). Sin esa variable no se levanta
  la pantalla y la demo corre con `sumo` sin GUI. **Pausar** en `sumo-gui` congela también la
  demo, y **cerrar la ventana** termina la corrida con error.
- **Una corrida a la vez.** Por defecto `p50_rf_s2`, ritmo 2, hasta t = 3 600 s (30 min reales);
  en el visor se elige el % de usuarios con app y el ritmo. Termina sola o con «Detener».
- **Consumo medido** (1 vCPU, 3,8 GiB): sin GUI, ~390 MiB y ~34 % de CPU a ritmo 5; con
  `sumo-gui` a ritmo 2, ~600 MiB y ~46 % de CPU. El VPS tiene 2 GiB de swap (`/swapfile`) como margen.
- Los logs de cada corrida quedan en `/tmp/esert-demo/` dentro del contenedor (se pierden al
  redesplegar).
- **Desarrollo, pruebas y experimentos** también son en el VPS, en el contenedor `van3twin`
  (ver `CLAUDE.md` y `herramientas/van3twin_vps.sh`). La laptop ya no hace falta.

## Reglas

- **Variables de entorno** (en Dokploy → Environment, nunca en el repo):
  - `ESERT_DB_URL=sqlite:////data/esert.db` (con el volumen `/data` montado en Dokploy);
  - `ESERT_TOKEN_SIM` (token largo y aleatorio), que exige `POST /interno/snapshot`; el
    controlador de la demo lo recibe del propio backend;
  - `ESERT_CLAVE_DEMO`: clave para iniciar y detener la simulación desde el visor;
  - `ESERT_URL_SIM` (en `api`) = `http://esert-sim-ygqubj:8100`;
  - en `sim`: `ESERT_TOKEN_SIM` (el mismo), `ESERT_CLAVE_VNC` (contraseña de `sumo-gui`) y
    `ESERT_URL_BACKEND` = `http://esert-api-ya3sai:8000`;
  - `ESERT_CORS_ORIGENES`;
  - `PAYPHONE_TOKEN` y `PAYPHONE_STORE_ID`, en modo de pruebas;
  - `ANTHROPIC_API_KEY`, si se usa el asistente LLM.
- **Seguridad mínima** (está en internet):
  - los endpoints internos exigen el token;
  - límite de tasa simple (por ejemplo, 10 recargas por minuto por usuario);
  - la billetera es **solo de prueba**: nada de dinero real;
  - no se guardan datos personales más allá de un `usuario_id` aleatorio y la placa ficticia.
- **Healthcheck:** `GET /salud` → `{"ok": true, "version": "...", "contrato": 1}`.
- **Autodeploy On Push** a `main` con **Watch Paths** (tabla de arriba): un push solo redespliega
  los servicios cuyas carpetas cambiaron. Un cambio solo de `CLAUDE.md` o `herramientas/` no
  redespliega nada.
- **Plan B:** si falla la red en la exposición, se proyecta el video del plan B. La demo local
  (`./demo/demo.sh --local` en una computadora con `van3twin`) sigue funcionando, pero ya no es
  la forma de trabajo.

## Configuración de `esert-demo` (app `api` en Dokploy)

| Campo | Valor |
|---|---|
| Repository / Branch | `e-sert` / `main` |
| Build Path | `/` |
| Docker File | `proyecto/backend/Dockerfile` |
| Docker Context Path | `.` (escribirlo explícito) |
| Trigger | On Push |
| Domains | `demo.e-sert.tesisucuenca.com`, Container Port `8000`, HTTPS con Let's Encrypt |
| Volumes | volumen persistente montado en `/data` |
| DNS | registro A `demo.e-sert` → IP del VPS |

Traefik (el proxy de Dokploy) soporta WebSocket sin configuración extra.
