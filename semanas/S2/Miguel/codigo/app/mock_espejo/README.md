# Servidor MOCK del modo espejo

> **MOCK: reemplazar cuando Freddy publique el modo espejo (S3-3).**

Servidor local (FastAPI + uvicorn) que imita el modo espejo del backend según
`docs/CONTRATO.md` §7, para desarrollar y probar la app sin SUMO ni el backend real.
Reproduce el recorrido grabado en `../src/espejo/recorrido_mock.json` (59 mensajes `espejo`
y un `espejo_fin`).

## Qué ofrece

| Ruta | Qué hace |
|---|---|
| `GET /api/v1/espejo/candidatos` | `[{id, destino_nombre, estado, t_sim}]` con 3 vehículos: `sim_veh42` (Parque Calderón), `sim_veh17` (Mercado 10 de Agosto), `sim_veh63` (Catedral Nueva). `estado` y `t_sim` muestran dónde va cada uno (`estado: null` y el `t_sim` inicial si aún no arranca). |
| `WS /ws/espejo/{veh_id}` | Mensajes `espejo` a 1 Hz de ese vehículo; al final `espejo_fin` (`salio_simulacion`) y cierra (código 1000). Un `veh_id` desconocido recibe `espejo_fin` con `motivo: "no_existe"` y `t_sim: null`, y se cierra. |
| `GET /api/v1/salud`, `GET /salud` | `{"ok": true, "contrato": 1, "t_sim": null, "ts": "<UTC ISO con ms y Z>"}`. El `ts` (y la cabecera `Date` que pone uvicorn) sirve para estimar el desfase de reloj con el método de Cristian. |
| `GET` o `POST /api/v1/espejo/reiniciar` | Pone a cero los relojes de reproducción de los tres vehículos. |

Detalles:

- **Simulación en vivo, no por conexión.** Cada vehículo arranca cuando el primer cliente se
  conecta a él; desde ahí avanza un mensaje por segundo aunque nadie lo mire. Si el cliente
  se reconecta, recibe el mensaje que toca *ahora* (no vuelve a empezar).
- Al conectar se envía de inmediato el mensaje actual; los siguientes van alineados al reloj
  del vehículo.
- Cada mensaje es una copia del grabado con `veh_id` cambiado y `ts` = hora UTC de emisión,
  con milisegundos y `Z` (por ejemplo `2026-11-01T20:15:03.123Z`). El recorrido es el mismo
  para los tres vehículos (el destino dentro del mensaje sigue siendo el grabado).
- CORS abierto. Cada conexión y desconexión se registra en consola con su `veh_id`.

## Opciones

| CLI | Variable de entorno | Efecto |
|---|---|---|
| `--bucle` | `ESPEJO_BUCLE=1` | Al terminar, el vehículo vuelve al primer mensaje, sin `espejo_fin` (los `t_sim` se repiten). |
| `--cortar-en N` | `ESPEJO_CORTAR_EN=N` | Cierra cada websocket N segundos después de abrirse, **sin** `espejo_fin` (código 4000, razón `corte_prueba`). Sirve para probar la reconexión de la app. Por defecto, apagado. |
| `--host` | | Por defecto `0.0.0.0` (necesario para que el teléfono lo alcance). |
| `--port` | | Por defecto `8001`. |

## Cómo correrlo

Desde esta carpeta (`semanas/S2/Miguel/codigo/app/mock_espejo/`), con Python 3.10 o superior:

```bash
python3 -m venv .venv            # .venv está en .gitignore
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Forma 1, script con banderas:

```bash
python servidor_mock.py                        # reproducción normal
python servidor_mock.py --bucle                # repetir sin fin
python servidor_mock.py --cortar-en 10         # cortar cada conexión a los 10 s
python servidor_mock.py --host 0.0.0.0 --port 8001
```

Forma 2, uvicorn directo (configurado con variables de entorno):

```bash
uvicorn servidor_mock:app --host 0.0.0.0 --port 8001
ESPEJO_BUCLE=1 ESPEJO_CORTAR_EN=10 uvicorn servidor_mock:app --host 0.0.0.0 --port 8001
```

Comprobación rápida:

```bash
curl http://127.0.0.1:8001/api/v1/salud
curl http://127.0.0.1:8001/api/v1/espejo/candidatos
curl -X POST http://127.0.0.1:8001/api/v1/espejo/reiniciar
```

## Cómo apunta la app al mock

En el `.env` de la app:

```bash
EXPO_PUBLIC_ESPEJO_URL=http://<ip-tailscale-de-la-mac>:8001
```

La app usa esa base para las rutas del espejo (`/api/v1/espejo/candidatos`,
`ws://.../ws/espejo/{veh_id}`, `/api/v1/salud`). **El teléfono nunca usa `localhost`**:
`localhost` en el teléfono es el propio teléfono. Usa la IP de Tailscale (o de la red local)
de la computadora que corre el mock, y lánzalo con `--host 0.0.0.0`. Tras cambiar el `.env`,
reinicia Expo (`npx expo start -c`).

## Pruebas

```bash
pip install -r requirements.txt
python -m pytest -q -p no:cacheprovider
```

Las pruebas usan un reloj falso (la reproducción es instantánea y determinista) y una prueba
con reloj real e intervalo de 0.01 s. Cubren: candidatos, reproducción completa con
`espejo_fin`, `veh_id` desconocido, `--cortar-en` con reconexión que retoma más adelante,
`--bucle`, `reiniciar`, salud y CORS.
