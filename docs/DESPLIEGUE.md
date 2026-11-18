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

## Arquitectura de la demo (desde el 2026-11-18: todo en el VPS)

```
 VPS (Dokploy, HTTPS con Traefik) · contenedor de la app `api` (Ubuntu 22.04, SUMO 1.12, Python 3.10)
 ──────────────────────────────────────────────────────────────────────────────────────────────
 Visor: botón «Iniciar» (X-Clave-Demo)  ──►  POST /api/v1/demo/iniciar
                                             └─ subproceso: python3 -m kpis.correr_una (SUMO por TraCI),
                                                publica en http://127.0.0.1:8000 con el token
                                             FastAPI + núcleo + SQLite (volumen /data)
 Teléfono espejo (Expo Go)              ──►  GET /api/v1/espejo/candidatos
                                        ◄──  WS /ws/espejo/{veh_id} (guiado, sesión, costo)
 Proyector / cualquier navegador        ◄──  GET /visor  +  WS /ws/estado
 Payphone (modo de pruebas)             ──►  GET /api/v1/pagos/retorno
```

- **SUMO corre en el VPS**, dentro del mismo contenedor que el backend. Se arranca y se detiene
  desde el visor (`https://demo.e-sert.tesisucuenca.com/visor/`, sección «Simulación en el
  servidor») con la clave `ESERT_CLAVE_DEMO`. En el VPS está en `/root/.esert_clave_demo`
  (`cat` solo en tu terminal). Sin simulación corriendo, SUMO no gasta CPU ni RAM.
- **`sumo-gui` en el navegador: `https://sumo.tesisucuenca.com`.** El contenedor levanta una
  pantalla virtual (Xvfb :99 + fluxbox) y la publica con noVNC en el puerto 6080 (dominio
  `sumo.tesisucuenca.com` de la app `api`, HTTPS). Cuando la demo corre, `sumo-gui` se abre ahí
  maximizado y con la cámara en la zona SERT (`sumo/demanda/vista_vps.xml`). Tiene **control
  completo** (pausar, cambiar el retardo, mover la cámara, inspeccionar autos) y pide la contraseña `ESERT_CLAVE_VNC` (8 caracteres;
  en el VPS está en `/root/.esert_clave_vnc`). Sin esa variable no se levanta la pantalla y la
  demo corre con `sumo` sin GUI. Todo lo arranca `proyecto/backend/arranque.sh`.
  Con el control vienen dos efectos: **pausar** en `sumo-gui` congela también la demo (el
  controlador espera a SUMO), y **cerrar la ventana** de `sumo-gui` termina la corrida con error.
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
  - `ESERT_CLAVE_VNC`: contraseña para ver `sumo-gui` en `sumo.tesisucuenca.com`;
  - `ESERT_CORS_ORIGENES`;
  - `PAYPHONE_TOKEN` y `PAYPHONE_STORE_ID`, en modo de pruebas;
  - `ANTHROPIC_API_KEY`, si se usa el asistente LLM.
- **Seguridad mínima** (está en internet):
  - los endpoints internos exigen el token;
  - límite de tasa simple (por ejemplo, 10 recargas por minuto por usuario);
  - la billetera es **solo de prueba**: nada de dinero real;
  - no se guardan datos personales más allá de un `usuario_id` aleatorio y la placa ficticia.
- **Healthcheck:** `GET /salud` → `{"ok": true, "version": "...", "contrato": 1}`.
- **Autodeploy On Push** a `main`: cada push a `main` actualiza la demo y el roadmap.
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
