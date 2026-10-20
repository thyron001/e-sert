---
semana: S2
persona: Miguel
sesion: 2
titulo: Billetera y recarga con Payphone en modo de pruebas
horas: 3-4
modulo: backend/pagos
depende: [S2-Miguel-1, S1-Freddy-2, S2-Freddy-1]
entrega: [backend/pagos/payphone.py, backend/pagos/rutas.py, backend/pagos/.env.example, backend/pagos/tests/, app/app/billetera.tsx, app/app/recarga.tsx, app/src/api/pagos.ts]
evidencias: [s2_billetera-recarga.png]
---
# S2 · Sesión 2 · Miguel 🔴: Billetera y recarga con Payphone en modo de pruebas

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (reglas de cobro: recarga mínima de $5) y
`docs/CONTRATO.md` (billetera y `POST /billetera/{id}/recarga` con `referencia_payphone`).
Eres dueño de `backend/pagos/`; la billetera es de Freddy (`proyecto/backend/nucleo/`): **no
la edites**, solo llama a `Billetera.recargar`. Freddy monta tu router si
`backend.pagos.rutas` es importable. **Payphone solo en modo de pruebas**; credenciales solo
en `.env` (en `.gitignore`). Los endpoints, campos y formatos exactos se toman de la
documentación vigente de Payphone Developers (Botón de Pagos, API *Prepare* y *Confirm*):
**no los inventes**; ábrela y cita en el código la sección consultada y la fecha.

## Objetivo
Recargar la billetera desde la app con el flujo real de Payphone en pruebas, con
confirmación del lado del servidor, idempotencia y un modo mock para trabajar sin
credenciales.

## Pasos
1. Crea `backend/pagos/.env.example` con las variables (vacías): `PAYPHONE_TOKEN`,
   `PAYPHONE_STORE_ID`, `PAYPHONE_URL_BASE`, `PAYPHONE_RESPONSE_URL`,
   `PAYPHONE_MODO=mock|pruebas`. El usuario copia a `.env` y pega sus credenciales de
   prueba; **tú nunca las escribes ni las repites en el chat**.
2. Crea `backend/pagos/payphone.py` con `AdaptadorPayphone(config, cliente_http)`:
   - `preparar(monto_usd, client_transaction_id, referencia) -> {payment_id, pay_url}`
     según el *Prepare* documentado (verifica si los montos van en centavos y qué campos de
     impuestos son obligatorios);
   - `confirmar(payment_id, client_transaction_id) -> {aprobado, monto_usd, autorizacion}`
     según el *Confirm* documentado;
   - `AdaptadorMock` con la misma interfaz: `pay_url` apunta a una página local
     `/api/v1/pagos/mock` con botones "Aprobar" y "Rechazar".
   - `httpx` con *timeout* de 10 s y sin registrar el token en los logs.
3. Crea `backend/pagos/rutas.py` (`APIRouter(prefix="/pagos")`, delgado):
   - `POST /pagos/preparar {usuario_id, monto}`: rechaza `monto < 5.00` con
     `RECARGA_MINIMA`; genera `client_transaction_id = "rec_<uuid4>"`; guarda la
     intención en una tabla `intenciones_pago` propia (estado `pendiente`);
   - `GET /pagos/retorno?id=&clientTransactionId=` (la `responseUrl`): llama a
     `confirmar`; si está aprobado, `Billetera.recargar(usuario, monto,
     referencia_payphone=id)` **una sola vez** (idempotente por `clientTransactionId`);
     responde una página corta "Pago confirmado, vuelve a la app" que redirige al *deep
     link* de la app;
   - `GET /pagos/{client_transaction_id}`: estado de la intención para que la app lo
     consulte.
   - Las rutas nuevas no están en el contrato v1: proponlas a Freddy como pedido para su
     `CONTRATO.propuesto.md`.
4. **App**:
   - `billetera.tsx`: `GET /billetera/{usuario_id}` con saldo, retenido, disponible y lista
     de movimientos (tipo, monto, fecha local), con *pull to refresh*;
   - `recarga.tsx`: botones $5, $10 y $20 y monto libre ≥ $5; llama a `preparar` y abre
     `pay_url` con `WebBrowser.openAuthSessionAsync(pay_url, Linking.createURL("pagos/retorno"))`
     de `expo-web-browser`; al volver, consulta `GET /pagos/{id}` hasta 10 veces cada 2 s y
     muestra éxito o error;
   - la pantalla de buscar (S2-1) ahora lleva aquí cuando el saldo no alcanza.
5. **Tests** (`backend/pagos/tests/`, pytest + `httpx.MockTransport`): monto < 5 rechazado;
   pago aprobado acredita exactamente una vez aunque `retorno` llegue 3 veces; pago
   rechazado no acredita; el token nunca aparece en los logs (`caplog`); el saldo de
   Freddy cuadra después de la recarga. Un subagente puede escribir los tests mientras tú
   haces las pantallas.
6. Prueba de punta a punta: backend con `uvicorn` **en segundo plano**, primero en
   `PAYPHONE_MODO=mock` y luego en `pruebas` con los datos de prueba que publica Payphone
   en su documentación (los introduce el usuario, no tú).
7. **Evidencia** `evidencias/s2_billetera-recarga.png`: tira de capturas del teléfono
   (billetera antes, Payphone en pruebas o mock, billetera después) unida con Pillow.

## VPS (demo en línea)
Lee `docs/DESPLIEGUE.md`. Payphone exige una `responseUrl` **pública HTTPS**: usa `https://demo.e-sert.tesisucuenca.com/api/v1/pagos/retorno` (en local, déjala configurable con `ESERT_URL_PUBLICA`). Las credenciales de prueba (`PAYPHONE_TOKEN`, `PAYPHONE_STORE_ID`) van como variables de entorno en Dokploy y en `.env` local; nunca en el repo. Si la demo aún no está desplegada, deja todo listo y la prueba de punta a punta queda para S3 (estado `parcial` documentado).

## Dónde escribir
`semanas/S2/Miguel/codigo/backend/pagos/`, `semanas/S2/Miguel/codigo/app/` y
`semanas/S2/Miguel/evidencias/`. Comprueba con `git status` que ningún `.env` queda
preparado para commit.

## Hecho cuando
- [ ] La `responseUrl` se arma desde `ESERT_URL_PUBLICA`, y existe un test del retorno idempotente que no depende de Payphone real.
- [ ] `pytest backend/pagos/tests` pasa, incluida la idempotencia.
- [ ] La recarga funciona de punta a punta en modo mock desde Expo Go.
- [ ] El modo `pruebas` de Payphone funciona o queda documentado qué falta (credenciales,
  `responseUrl` pública, etc.) con estado `parcial`.
- [ ] No hay credenciales en el repositorio (`git grep -i token` sin resultados sensibles).
- [ ] Existe la evidencia `s2_billetera-recarga.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 2, Miguel). En "Pedidos a
otros": @Freddy, añadir `/pagos/*` y el código `RECARGA_MINIMA` al contrato propuesto, y
confirmar que `Billetera.recargar` acepta `referencia_payphone`.
