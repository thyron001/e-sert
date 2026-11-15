# backend/pagos: recarga con Payphone (Miguel)

Router `APIRouter(prefix="/pagos")` que `backend/api/main.py` (Freddy) monta en `/api/v1` si
`backend.pagos.rutas` es importable. La billetera no se toca: solo se llama a
`Billetera.recargar(usuario, monto, referencia_payphone=id)`.

| Ruta | Qué hace |
|---|---|
| `POST /pagos/preparar {usuario_id, monto, url_app?}` | `monto < 5` → `RECARGA_MINIMA` (422). Crea la intención `rec_<uuid4>` (pendiente), llama a Prepare y devuelve `{client_transaction_id, payment_id, pay_url, modo}`. |
| `GET /pagos/ir/{id}` | Página puente en nuestro dominio que salta al formulario (Payphone exige Referer del dominio registrado). |
| `GET /pagos/retorno?id=&clientTransactionId=` | La `responseUrl`: Confirm y recarga **una sola vez**; página "Pago confirmado" que vuelve al deep link de la app (en Android, `intent://`). |
| `GET /pagos/{client_transaction_id}` | Estado de la intención (`pendiente`, `aprobado`, `rechazado`) para que la app lo consulte. |
| `GET /pagos/mock`, `/pagos/mock/decidir` | Solo con `PAYPHONE_MODO=mock`: formulario simulado con "Aprobar" y "Rechazar". |

## Configuración

Copia `.env.ejemplo` a `.env` (ignorado por git). Las variables de entorno mandan sobre el
archivo. `responseUrl = ${ESERT_URL_PUBLICA}/api/v1/pagos/retorno` salvo que se fije
`PAYPHONE_RESPONSE_URL`. En modo `pruebas` sin `PAYPHONE_TOKEN` o `PAYPHONE_STORE_ID`,
`preparar` responde `ERROR_INTERNO` con `detalle.faltan` (nombres, nunca valores).

## Correr en local (con el backend de Freddy)

```bash
# desde la carpeta que contiene backend/ y comun/, con backend/pagos copiado o enlazado
pip install -r backend/requirements.txt -r backend/pagos/requirements.txt
PAYPHONE_MODO=mock ESERT_URL_PUBLICA=http://<ip-tailscale>:8000 \
  uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
python -m pytest backend/pagos/tests -q
```
