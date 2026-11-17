# Checklist de QA de la app e-sert (S4-1)

Batería para que la app **no falle delante del profesor**. Todo es simulado: el teléfono queda
quieto y no hay pruebas en la calle.

- **Fecha:** 2026-11-14, de 19:10 a 22:45.
- **Versiones:** Expo SDK 58 (`expo` ~58.0.25), React Native 0.88, Node v26.10 en la computadora.
- **Teléfonos:**
  - **Android**, el de Miguel, con Expo Go SDK 58, por Tailscale (Wi-Fi y datos).
  - **iPhone:** no hubo un iPhone físico; se usó el **simulador de iOS** (iPhone 18 Pro, iOS 27.1) con Expo Go 58.0.5. `simctl` no puede tocar la pantalla, así que en el simulador solo se recorrieron las pantallas por enlaces profundos y se probó lo que no necesita toques. El resto queda "n/a (simulador)".
- **Backends:**
  - **Local:** `proyecto/backend` en la computadora (`--host 0.0.0.0 --port 8000`, `PAYPHONE_MODO=mock`, base de datos de prueba nueva), con la simulación de Freddy (`python3 -m traci.correr_guiado --escenario app50_s1 --publicar http://host.docker.internal:8000`) en el contenedor `van3twin`.
  - **VPS:** `https://demo.e-sert.tesisucuenca.com` (solo "Probar conexión": `/salud` y candidatos responden).
- **Capturas:** en `semanas/S4/Miguel/evidencias/capturas/` (las 8 del manual también en `capturas/`).
- **Leyenda:**
  - ✅ pasa;
  - ⚠️ pasa con una observación menor;
  - ❌ falla;
  - n/a no aplica.

| # | Caso | Pasos | Resultado esperado | Android | iPhone (simulador) | Notas y evidencia |
|---|---|---|---|---|---|---|
| 1 | Primer uso y permisos de ubicación | Quitar el permiso de Expo Go en Ajustes del teléfono; Grabador → Iniciar; luego "Preguntar siempre" → "Solo esta vez" | Sin cierre; al denegar, mensaje claro; nada pide la ubicación fuera del Grabador | ✅ | n/a (simulador) | Con el permiso ya dado no se pregunta (es de Expo Go, no de e-sert). Denegado: "Sin permiso de ubicación: actívalo en los ajustes…". `s4_permiso_negado` |
| 2 | Recarga Payphone: éxito | Billetera → Recargar → $10 → Aprobar | Recarga confirmada y saldo +$10,00 | ✅ | n/a (simulador) | `08_billetera2` (Payphone mock 87327042) |
| 3 | Recarga Payphone: cancelación | Recargar → Rechazar | "El pago fue rechazado o cancelado. No se cobró nada." | ✅ | n/a (simulador) | `08_billetera1` |
| 4 | Recarga Payphone: error | Recargar con el backend detenido | Mensaje traducido con "Revisar conexión"; sin texto técnico | ✅ | n/a (simulador) | Corregido en la batería: antes salía solo el texto, sin botón. `s4_recarga_error` (antes de la corrección) |
| 5 | Buscar → guiar → confirmar → activa | Buscar puesto → Llegar ya → placa y puesto → Confirmar | Sesión activa con cronómetro y costo | ✅ | n/a (simulador) | `06_aviso` |
| 6 | Aviso de saldo bajo (< 10 min) | Sesión con poco saldo (escala de demo 60×) | Notificación y banner "Saldo bajo" | ⚠️ | ⚠️ | Android: en esta batería no se forzó el saldo bajo (había $9,84); el aviso se probó en S3-2 y tiene pruebas en Jest (`calcularAvisos`). iPhone: el simulador mostró el banner "Saldo agotado" en una sesión vieja (`s1_ios-simulador.png`, 01) |
| 7 | Aviso de tope SERT próximo | Misma sesión, a los 110 min de la regla (~110 s) | Notificación y banner "Tope SERT cerca" | ✅ | ⚠️ | `06_aviso` (notificación + banner). iPhone: solo el banner "Superaste el tiempo máximo SERT" |
| 8 | Espejo: selector de candidatos | Sesión → Modo espejo | Lista de autos con app (o mensaje de vacío) | ✅ | ✅ | Android: 15+ autos en Guiado (`03_selector`). iPhone: sin simulación, "No hay autos con app…" |
| 9 | Espejo: GUIADO → CERRADA | Seguir un auto de la simulación | Mapa, estados, costo en vivo y recibo al cerrar | ✅ | n/a (simulador) | `04_guiado`, `04_espejo_apie`, `07_recibo_espejo` (sim_busca_4, 65,8 min, $0,58) |
| 10 | Espejo: reconexión tras cortar la red 15 s | Modo avión 15 s con un auto en vivo | "Reconectando" y luego "En vivo", sin cerrar la pantalla | ✅ | n/a (simulador) | `04_guiado` muestra "Reconectando (1)" en modo avión; luego "En vivo" |
| 11 | Espejo: `espejo_fin` | Auto en Guiado cuando termina la corrida | "El auto salió de la simulación" e indicador "Finalizado" | ✅ | n/a (simulador) | Solo se ve si la corrida termina antes del cierre del auto: corrida corta `--ritmo 1 --hasta 180`. `s4_espejo_fin` |
| 12 | Cierre automático por la simulación y recibo | Seguir un auto hasta CERRADA | Recibo solo, con "Con la tarjeta SERT habrías pagado $X" | ✅ | n/a (simulador) | `07_recibo_espejo`, `s4_espejo_fin` previo (sim_busca_7). Menor: "Llegada" sale "—" en un caso (ver abajo) |
| 13 | Bloqueo por saldo negativo y desbloqueo | Saldo −$0,57 → Sesión → Recargar $5 | "Buscar puesto" desactivado con la deuda; tras recargar, activo | ✅ | n/a (simulador) | Saldo negativo con una sesión de prueba de 20 h abierta y cerrada por la API local. `s4_bloqueo`, `s4_desbloqueo`; el backend confirmó `bloqueada: false` y $4,43 |
| 14 | Sin red | Modo avión → Mapa | "No hay conexión con el servidor" + "Revisar conexión"; nada crudo | ✅ | n/a (simulador) | `s4_sin_red` |
| 15 | Backend caído | Detener el backend → Mapa / Billetera | Mensaje traducido con acción; la app no se cierra | ✅ | n/a (simulador) | `s4_backend_caido`, `s4_demorevisarconexion` |
| 16 | Cambio de Wi-Fi a datos | Cambiar de red con la app abierta | Sigue funcionando (con Tailscale o el VPS) | ✅ | n/a (simulador) | Tailscale mantiene la IP 100.85.244.14 en datos móviles |
| 17 | App de vuelta al primer plano | Segundo plano 30 s con el espejo abierto | Reconecta el espejo y conserva la sesión | ✅ | n/a (simulador) | Volvió a "En vivo" sola |
| 18 | Ajustes de demo | Mantener pulsado el logo 3 s → VPS / Local → Probar conexión | Cambia de backend sin reinstalar; latencia de /salud, candidatos y WS | ✅ | ✅ | Android: VPS y Local con ✓ (`s4_demo`: /salud 197 ms, candidatos 26 ms). iPhone: la pantalla abre y muestra el backend en uso (`s1_ios-simulador.png`) |
| 19 | Errores del contrato traducidos | Puesto con formato malo; puesto inexistente; sesión inexistente | Mensaje en español con "Buscar otro puesto", "Volver al inicio" o "Recargar" | ✅ | ✅ | Android: `pa_no_existe` → aviso de formato antes de enviar (`s4_puesto_formato`); `pa_no_existe_999` → "Ese puesto no existe…" + "Buscar otro puesto" (`s4_error_puesto`). iPhone: sesión guardada de otro backend → "El servidor ya no tiene esta sesión…" + "Descartar sesión" |

**Resultado:** en Android pasan 18 de 19 casos; el 6 queda ⚠️ porque no se repitió en esta batería. En el simulador de iOS pasan 4 (8, 18, 19 y los banners de 6 y 7); los demás necesitan tocar la pantalla o un teléfono real y quedan n/a. No queda ningún caso crítico en rojo.

## Fallas encontradas y corregidas

1. **Caso 19: puesto mal escrito.**
   - El backend valida el formato `^pa_.+_\d+$` antes de buscar el puesto, así que `pa_no_existe` devolvía `VALIDACION` ("Algún dato no es válido"), sin botón.
   - Corrección: `Confirmar` valida el formato en el teléfono, como la placa (`esPuestoValido` en `src/sesion/placa.ts`). Muestra la ayuda "Código del puesto: pa_ + calle + número" y desactiva el botón.
   - Prueba nueva en `__tests__/placa.test.ts`.
2. **Caso 4: recarga sin conexión.**
   - `recarga.tsx` mostraba el texto traducido, pero sin el botón de acción.
   - Corrección: ahora usa `AvisoError`, con "Revisar conexión" y "Reintentar".
3. **Decimales con punto.**
   - "0.2 min" en el recibo y "2.9 minutos" en el espejo.
   - Corrección: coma decimal, igual que los montos (`$0,50`).

## Casos menores que quedan abiertos

1. **iPhone físico:** no hubo uno. El simulador no permite tocar, así que los casos 1–5, 9–17 quedan sin probar en iOS. Hay que repetirlos con un iPhone del grupo antes de la demo, si alguien lo tiene.
2. **Recibo del espejo, "Llegada" = "—"** (caso 12, sim_busca_4).
   - El recibo que arma la app con `recibo_sesion` no siempre trae la hora de llegada.
   - Lo revisa Freddy (pedido en la bitácora).
3. **`espejo_fin` en la corrida normal** (caso 11).
   - Con `--ritmo 5 --hasta 7200`, todos los autos cierran antes del final y el teléfono salta al recibo.
   - El mensaje "salió de la simulación" solo aparece si la corrida termina con el auto en camino.
   - Es el comportamiento correcto, pero para mostrarlo en la demo hace falta una corrida corta.
4. **Placa sin guion:** la app acepta "ABC1234" y la muestra así en el recibo. El contrato lo permite (guion opcional).
