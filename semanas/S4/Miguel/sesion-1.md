---
semana: S4
persona: Miguel
sesion: 1
titulo: Pulido final de la app y manual de usuario
horas: 3-4
modulo: app
depende: [S3-Miguel-2, S3-Miguel-3]
entrega: [app/, app/src/config/demo.ts, app/src/errores.ts, app/CHECKLIST_QA.md, app/MANUAL.md, app/capturas/]
evidencias: [s1_app-pantallas.png]
---
# S4 · Sesión 1 · Miguel 🔴: Pulido final de la app y manual de usuario

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (sección de la app y reglas de cobro) y
`docs/CONTRATO.md` (API y códigos de error). Primero copia tus módulos (`app/`, `datos/`,
`backend/pagos/` y `backend/asistente/`) desde `proyecto/` a `semanas/S4/Miguel/codigo/`.
Ya no se agregan funciones nuevas: esta semana la app tiene que **no fallar delante del
profesor**. Recuerda que en iPhone el segundo plano es limitado, así que en la demo la app
debe quedar abierta. Plazo real: sábado 14, 23:59.

## Objetivo
Pasar una batería de QA en un iPhone y en el Android con Expo Go, corregir lo encontrado,
dejar la configuración de la demo a prueba de redes cambiantes y escribir el manual de
usuario.

## Pasos
1. Escribe `app/CHECKLIST_QA.md`, una tabla con caso, pasos, resultado esperado, y resultado
   en iPhone y en Android:
   - primer uso y permisos de ubicación (aceptar, denegar y "solo una vez");
   - recarga con Payphone en **modo de prueba** (éxito, cancelación, error);
   - buscar → guiar → confirmar (placa + puesto) → sesión activa;
   - avisos de saldo bajo (< 10 min) y de tiempo máximo SERT próximo;
   - modo espejo: selector de candidatos, seguimiento GUIADO → CERRADA, reconexión del WS tras
     cortar la red 15 s y `espejo_fin`;
   - cierre automático disparado por la simulación (vía espejo) y recibo ("con tarjeta habrías
     pagado X");
   - bloqueo por saldo negativo y desbloqueo al recargar;
   - sin red, backend caído, cambio de Wi-Fi a datos y app vuelta al primer plano (el teléfono
     queda quieto: todo es simulado, no hay pruebas en la calle).
2. Ejecuta la batería y corrige cada falla. Los arreglos en el backend van solo en
   `backend/pagos/` y `backend/asistente/`; lo demás del backend es de Freddy (pedido).
3. Crea `app/src/errores.ts`: traduce cada código del contrato (`SALDO_INSUFICIENTE`,
   `PUESTO_LLENO`, `SESION_NO_EXISTE`, `SESIONES_BLOQUEADAS` y errores de red) a un mensaje
   en español con una acción ("Recargar", "Buscar otro puesto", "Reintentar"). Ningún error
   técnico crudo llega a la pantalla.
4. Crea `app/src/config/demo.ts` y una pantalla oculta **Ajustes de demo** (mantener
   pulsado el logo 3 s): URL del backend editable con dos atajos, **VPS**
   (`https://demo.e-sert.tesisucuenca.com`, por defecto) y **Local** (la IP que imprime
   `demo.py --local` de Tyrone); botón "Probar conexión" que llama a `GET /salud` y
   `GET /api/v1/espejo/candidatos` y muestra la latencia; e indicador del estado del WebSocket
   espejo. La URL se guarda en `AsyncStorage`.
5. Pulido de UX: estados de carga y vacío en todas las listas, botones de al menos 44×44 pt,
   `accessibilityLabel` en los controles, contraste AA, nombre y color de la app
   consistentes, formato de moneda `$0,50` y horas en la zona de Ecuador.
6. Calidad: `npx tsc --noEmit` sin errores, `npx expo-doctor` sin problemas críticos y el
   *linter* del proyecto limpio. Anota las versiones de Expo SDK y Node usadas.
7. Pide al usuario capturas reales de 8 pantallas (inicio, mapa con puestos, selector espejo,
   espejo GUIADO, espejo A_PIE, aviso, recibo, billetera) y guárdalas en `app/capturas/` con
   nombres `01_inicio.png`, `02_mapa.png`, etc.
8. Escribe `app/MANUAL.md` para el usuario final: qué hace la app, instalación con Expo Go
   (QR), cada pantalla con su captura, cómo funciona el cobro por tiempo real frente a la
   tarjeta SERT, el **modo espejo** (el teléfono sigue a un conductor simulado y no usa tu GPS),
   preguntas frecuentes (¿por qué debo dejar la app abierta?, ¿qué pasa si me quedo sin
   saldo?) y una sección **Modo demo** con los Ajustes de demo.
9. **Evidencia** `evidencias/s1_app-pantallas.png`: montaje 4×2 de las 8 capturas, hecho con
   Pillow, con el nombre de cada pantalla debajo.

## Dónde escribir
`semanas/S4/Miguel/codigo/app/`, `semanas/S4/Miguel/codigo/backend/pagos/`,
`semanas/S4/Miguel/codigo/backend/asistente/` y `evidencias/`. Credenciales de Payphone solo
en `.env`.

## Hecho cuando
- [ ] `CHECKLIST_QA.md` está completo en ambos teléfonos y no queda ningún caso crítico en
  rojo (los menores quedan listados con su motivo).
- [ ] `npx tsc --noEmit` termina sin errores.
- [ ] Cambiar la URL del backend desde Ajustes de demo funciona sin reinstalar la app.
- [ ] Ningún código de error del contrato llega crudo a la pantalla.
- [ ] `MANUAL.md` existe con las 8 capturas enlazadas.
- [ ] Existe la evidencia `s1_app-pantallas.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 1, Miguel). En "Pedidos a
otros": @Freddy, fallas del backend que encontraste en QA; @Tyrone, confirma el puerto y la
ruta del WS que la app espera en la demo.
