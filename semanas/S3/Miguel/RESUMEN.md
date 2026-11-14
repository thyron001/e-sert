# S3 · Miguel 🔴 · Galería semanal

## Sesión 1 · 2026-11-08 · Cierre automático en la app y recibo comparado con la tarjeta SERT

**Estado:** hecha (5/5 criterios).

- Cuando la **simulación** cierra la sesión del auto espejo, el mensaje `CERRADA` con `recibo` de `WS /ws/espejo` (backend real de Freddy) lleva la app sola al recibo, sin poder volver atrás.
- En una sesión propia, `GET /sesiones/{id}` cada 10 s (y al volver a primer plano) detecta un cierre hecho fuera de la app: con `curl` se vio en **7 s**. También está "Ya me voy" con confirmación.
- El cierre se procesa **una sola vez**, venga del WS, del REST o del botón.
- El recibo muestra placa, puesto, calle, horas en America/Guayaquil, minutos reales y cobrados, débito, saldo y la comparación con la **tarjeta SERT**, con los montos del servidor. Ejemplo: 47 min → $0.42 frente a $0.50 con la tarjeta, ahorro $0.08.
- `tarifa.ts` portada de `tarifa.py` con las cifras de Freddy (50 tests). Jest 204/204, `tsc` sin errores, contrato v1.2 verificado.

![Recibos en Android y en el simulador de iPhone](evidencias/s1_recibo.png)

Explicación: [explicaciones/s1_explicacion.pdf](explicaciones/s1_explicacion.pdf)

## Sesión 2 · 2026-11-08 · Avisos de saldo bajo, tiempo máximo y bloqueo por saldo negativo

**Estado:** hecha (5/5 criterios).

- Al confirmar la llegada se programan notificaciones locales: **saldo bajo** 10 min antes de que el disponible se acabe y **tope SERT** 10 min antes de los 120 min. Si caen a menos de 1 min, se combinan en una.
- Con la app abierta aparece un **banner amarillo** y la notificación sale a la hora exacta. En segundo plano, Android la entrega con algo de retraso porque usa alarmas inexactas.
- Al cerrar se **cancelan** todas: en la prueba quedaron 0. Tras recargar se reprograman sin repetir lo ya avisado.
- Con **saldo negativo** se desactiva "Buscar puesto" y se muestra la deuda con "Recargar". Tras recargar $5 por Payphone (mock) se desbloquea.
- Modo demo `EXPO_PUBLIC_ESCALA_TIEMPO=60`: 1 min de la regla = 1 s. Jest 232/232, `tsc` sin errores.

![Avisos y bloqueo en Android](evidencias/s2_avisos.png)

Explicación: [explicaciones/s2_explicacion.pdf](explicaciones/s2_explicacion.pdf)

## Sesión 3 · 2026-11-08 · Entrada por lenguaje natural con LLM (opcional) o pulido de UX

**Estado:** hecha (4/4 criterios). Se eligió el LLM porque S3-1 y S3-2 estaban hechas.

- `backend/asistente/`: `POST /api/v1/asistente/interpretar {texto}` → `{destino, duracion_min, fuente, confianza, avisos}`.
  - Claude Haiku 5.5 con la herramienta forzada `registrar_intencion`, validación Pydantic, caché LRU y registro de tokens; solo se envía el texto.
  - Sin clave, con timeout o con error, responde un **intérprete por reglas** con el mismo resultado en los casos simples.
- El destino siempre sale de `destinos.csv` de Tyrone (alias y comparación difusa ≥ 80): nunca se inventa. La duración se recorta a 10–120 min con aviso.
- App: "Catedral Nueva · 60 min. ¿Correcto?" con Editar y Buscar, y el **formulario** de alternativa siempre disponible, incluso con el asistente caído. Se corrigió el panel que quedaba tapado por el teclado.
- pytest 96 passed, 1 skipped (la prueba real del LLM, sin clave). Jest 232/232. Ninguna clave en el repo (búsqueda con `git grep`).

![Entrada natural y formulario de alternativa](evidencias/s3_entrada-natural.png)

Explicación: [explicaciones/s3_explicacion.pdf](explicaciones/s3_explicacion.pdf) · Resumen de la semana: [evidencias/resumen_S3_Miguel.pdf](evidencias/resumen_S3_Miguel.pdf)
