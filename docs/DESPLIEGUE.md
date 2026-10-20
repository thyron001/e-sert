# Despliegue en el VPS (Dokploy)

El grupo tiene un VPS con Dokploy, el mismo de `tesisucuenca.com`. Hay dos aplicaciones:

| App en Dokploy | Dominio | Qué sirve | Dockerfile | Dueño |
|---|---|---|---|---|
| `esert-roadmap` | `e-sert.tesisucuenca.com` | Roadmap del equipo (ya funciona) | `Dockerfile` (raíz) | Tyrone |
| `esert-demo` | `demo.e-sert.tesisucuenca.com` | Backend FastAPI (`/api/v1`, `/ws/estado`) + visor (`/visor`) | `proyecto/backend/Dockerfile` | Freddy (backend) y Tyrone (visor) |

## Accesos: solo Tyrone

**Solo Tyrone tiene acceso** al VPS, al panel de Dokploy, al DNS y a la cuenta de Payphone
(modo de pruebas). Ninguna otra persona ni sus sesiones de Claude intentan entrar ahí ni
piden esas credenciales. Si una sesión necesita algo de esto (crear la app, una variable de
entorno, un volumen, un redeploy, credenciales de Payphone o ver logs del contenedor):

1. **Deja todo listo** del lado del repo: Dockerfile, código y `.env.ejemplo` con los
   *nombres* de las variables, sin valores.
2. **Escribe el pedido** en "Pedidos a otros" de la bitácora, con el formato
   `@Tyrone [VPS]` o `@Tyrone [Payphone]`, y exactamente qué hacer: campo, valor o comando.
3. **Sigue con un mock o en local**, y marca el criterio afectado como `parcial` si depende
   de eso.

Tyrone revisa estos pedidos en las bitácoras o en el resultado de la unificación del domingo.
Las credenciales de Payphone nunca se comparten por el repo: si alguien necesita probar en
local, Tyrone las pasa por privado y van en su `.env`.

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

## Arquitectura de la demo

```
 Laptop (SUMO + sumo-gui + controlador TraCI)          VPS (Dokploy, HTTPS con Traefik)
 ───────────────────────────────────────────           ─────────────────────────────────
 traci/controlador.py --publicar https://demo...  ──►  POST /api/v1/interno/snapshot   (token)
                                                       FastAPI + núcleo + SQLite (volumen)
 Teléfono espejo (Expo Go, quieto en la mano)   ──►    GET /api/v1/espejo/candidatos
                                                ◄──    WS /ws/espejo/{veh_id} (guiado, sesión, costo)
 Proyector / cualquier navegador                ◄──    GET /visor  +  WS /ws/estado
 Payphone (modo de pruebas)                     ──►    GET /api/v1/pagos/retorno
```

**SUMO no corre en el VPS.** Corre en la laptop de la demo, con `sumo-gui` visible, y publica
snapshots al backend en línea. El VPS solo sirve la API, el WebSocket y el visor; es liviano.

## Reglas

- **Variables de entorno** (en Dokploy → Environment, nunca en el repo):
  - `ESERT_DB_URL=sqlite:////data/esert.db` (con el volumen `/data` montado en Dokploy);
  - `ESERT_TOKEN_SIM` (token largo y aleatorio), que exige `POST /interno/snapshot`;
  - `ESERT_CORS_ORIGENES`;
  - `PAYPHONE_TOKEN` y `PAYPHONE_STORE_ID`, en modo de pruebas;
  - `ANTHROPIC_API_KEY`, si se usa el asistente LLM.
- **Seguridad mínima** (está en internet):
  - los endpoints internos exigen el token;
  - límite de tasa simple (por ejemplo, 10 recargas por minuto por usuario);
  - la billetera es **solo de prueba**: nada de dinero real;
  - no se guardan datos personales más allá de un `usuario_id` aleatorio y la placa ficticia.
- **Healthcheck:** `GET /salud` → `{"ok": true, "version": "...", "contrato": 1}`.
- **Autodeploy On Push** a `main`: cada unificación del domingo actualiza la demo. Mientras
  `proyecto/backend/Dockerfile` no exista (antes de la unificación de S2), la app
  `esert-demo` no se crea.
- **Plan B:** todo debe funcionar también en local (`uvicorn` + visor en `localhost`), por si
  falla la red en la exposición.

## Configuración de `esert-demo` en Dokploy (la hace Tyrone tras la unificación de S2)

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
