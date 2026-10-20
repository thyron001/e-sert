---
semana: S2
persona: Freddy
sesion: 1
titulo: Capa FastAPI sobre el núcleo, WebSocket y Swagger
horas: 3-4
modulo: backend
depende: [S1-Freddy-1, S1-Freddy-2]
entrega: [backend/api/main.py, backend/api/rutas/, backend/api/ws.py, backend/api/errores.py, backend/tests/test_api.py, backend/requirements.txt]
evidencias: [s1_swagger.png]
---
# S2 · Sesión 1 · Freddy 🍅: Capa FastAPI sobre el núcleo, WebSocket y Swagger

## Contexto
Lee `CLAUDE.md`, `docs/CONTRATO.md` (ya v1 tras la unificación del 25 de octubre; secciones
4 y 6) y tu núcleo de S1-2. Es la primera sesión de S2: copia `proyecto/backend/` (sin
`backend/pagos/` ni `backend/asistente/`, que son de Miguel) y `proyecto/comun/` a
`semanas/S2/Freddy/codigo/` si aún no existe la copia. **Miguel y el visor de Tyrone dependen
de esta API desde esta semana**. La regla es firme: la lógica vive en `backend/nucleo/`
(Python puro); FastAPI solo valida, llama al núcleo y traduce errores.

## Objetivo
Exponer el núcleo por HTTP y WebSocket exactamente como dice el contrato, con documentación
Swagger útil y tests de cada ruta.

## Pasos
1. Crea `backend/api/main.py` con una fábrica `crear_app(config: Config) -> FastAPI`:
   - `Config` (pydantic-settings) lee `E_SERT_DB_URL` (por defecto
     `sqlite:///./e-sert.db`), `E_SERT_PUESTOS_CSV` (por defecto
     `proyecto/sumo/parqueos/puestos.csv`; si falta, el mock de 20 puestos de S1-2) y
     `E_SERT_CORS` (por defecto `*` para Expo Go y el visor);
   - todas las rutas bajo el prefijo `/api/v1`; *middleware* que añade
     `X-Contrato-Version: 1` a cada respuesta;
   - las dependencias (`Billetera`, `ServicioSesiones`, `MapaOcupacion`) se inyectan con
     `Depends`, de modo que los tests usan SQLite en memoria;
   - si `backend.pagos.rutas` es importable (módulo de Miguel), móntalo con
     `app.include_router(...)` dentro de un `try/except ImportError`. **No lo edites.**
2. Crea `backend/api/rutas/` con un archivo por recurso (`puestos.py`, `guia.py`,
   `eventos.py`, `sesiones.py`, `billetera.py`), con los cuerpos y respuestas de
   `comun/esquemas.py` como `response_model`. `POST /eventos/*` devuelve `202` y actualiza
   el `MapaOcupacion` y el último estado conocido de cada usuario.
3. Crea `backend/api/errores.py`: *exception handlers* que convierten las excepciones del
   núcleo al formato `{"error": {"codigo", "mensaje"}}` con su estado HTTP
   (`SALDO_INSUFICIENTE` → 402, `PUESTO_LLENO` → 409, `SESION_NO_EXISTE` → 404,
   `SESIONES_BLOQUEADAS` → 403, validación → 422 con el mismo formato).
4. Crea `backend/api/ws.py` con `GestorConexiones` (`conectar`, `desconectar`,
   `difundir(mensaje)` con `asyncio.gather` y descarte de clientes caídos) y la ruta
   `WS /ws/estado`. Añade `publicar_snapshot(snapshot)` para que el controlador TraCI
   empuje mensajes: **en proceso** (cola `asyncio.Queue`) y, para procesos separados,
   `POST /api/v1/interno/snapshot`. Limita a 1 snapshot por segundo de simulación y no
   difundas `tipo: "verdad"` a clientes que no lo pidan (`?verdad=1`). Si esta ruta interna
   cambia el contrato, regístrala en `comun/CONTRATO.propuesto.md`.
5. Swagger: `title="e-sert API"`, `version="1"`, descripción en español, `tags` por
   recurso y `openapi_examples` cargados desde `comun/ejemplos/*.json`. Exporta
   `backend/openapi.json` con un script (`python -m backend.api.exportar_openapi`).
6. **Tests** `backend/tests/test_api.py` (pytest + `fastapi.testclient.TestClient`):
   - flujo feliz: recarga 5 → `POST /sesiones` → `GET /sesiones/{id}` → cerrar a los 47 min
     → saldo correcto;
   - `GET /guia` nunca devuelve un puesto lleno y responde `404` si no hay libres;
   - cada código de error devuelve su estado HTTP y el formato acordado;
   - el header `X-Contrato-Version` está en todas las respuestas;
   - el WS recibe un snapshot publicado y respeta el límite de 1 por segundo.
   Delega en un subagente los tests de WebSocket mientras tú haces las rutas REST.
7. Lanza `uvicorn backend.api.main:app --reload --port 8000` **en segundo plano** y prueba
   a mano con `curl`/`httpx` los ejemplos de `comun/ejemplos/`.
8. **Evidencia** `evidencias/s1_swagger.png`: captura de `/docs` con todas las rutas
   desplegadas (Playwright, `page.screenshot(full_page=True)`).

## Dónde escribir
`semanas/S2/Freddy/codigo/backend/` (salvo `pagos/` y `asistente/`),
`semanas/S2/Freddy/codigo/comun/CONTRATO.propuesto.md` si hace falta, y `evidencias/`.

## Hecho cuando
- [ ] `pytest backend/tests` pasa, con cobertura mayor al 85 % en `backend/api/` y
  `backend/nucleo/`.
- [ ] `backend/api/` no contiene reglas de cobro ni de ocupación: todo llama al núcleo
  (revísalo con `grep`).
- [ ] Las 9 rutas del contrato y `/ws/estado` responden con el formato exacto.
- [ ] `openapi.json` está exportado y `/docs` muestra ejemplos en cada ruta.
- [ ] Existe la evidencia `s1_swagger.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 1, Freddy). En "Pedidos a
otros": @Miguel, la URL base, el arranque con `uvicorn` y cómo se monta `backend/pagos/`;
@Tyrone, la URL `ws://<host>:8000/ws/estado` y `POST /interno/snapshot`.
