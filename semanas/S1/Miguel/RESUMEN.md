# S1 · Miguel 🔴 · Galería semanal

## Sesión 1 · 2026-10-22 · Proyecto Expo, navegación y cliente API

**Estado:** hecha (4/4 criterios).

- Se creó la app Expo **SDK 58** con TypeScript y `expo-router`, con 5 pestañas: Mapa, Sesión, Billetera, Grabador y Ajustes.
- Se escribió un cliente API tipado contra el contrato, con dos implementaciones de la misma interfaz `ApiESert`:
  - `cliente.ts`: el cliente HTTP real.
  - `mock.ts`: 20 puestos, billetera con la tarifa y 300 ms de latencia.
- La app se probó en Expo Go en un Android real y en el simulador de iPhone 18 Pro.

![Mapa y Ajustes en iOS y Android](evidencias/s1_app-pantallas.png)

![Las 5 pestañas en iOS (simulador)](evidencias/s1_ios-pestanas.png)

![Las 5 pestañas en Android, probando el flujo: llegada confirmada y $0,25 retenidos](evidencias/s1_android-pestanas.png)

Explicación: [explicaciones/s1_explicacion.pdf](explicaciones/s1_explicacion.pdf)

## Sesión 2 · 2026-10-22 · Grabador de sensores etiquetado

**Estado:** parcial (3/4 criterios). En iOS solo se probó en el simulador, sin un iPhone físico.

- La pestaña **Grabador** registra:
  - el GPS a 1 Hz y el acelerómetro a 10 Hz;
  - 4 etiquetas, entre ellas `vehiculo_lento`, que se exporta como `vehiculo` + `trafico_lento`;
  - los cambios de etiqueta hechos sin detener la grabación.
- Los datos se vuelcan a disco cada 30 s. El CSV sigue el contrato y se comparte por correo o Drive.
- `graficar_grabacion.py` valida el CSV, lo dibuja y resume la duración por etiqueta y la precisión.
- **Android real:** 663 muestras a 1,00 Hz, 5:53 a pie y 5:17 quieto, con el cambio en caliente a los 5:54; el acelerómetro dio 9,9 Hz. La grabación se anonimizó antes de subirla.

![Pantalla del grabador en Android y en el simulador de iOS](evidencias/s2_grabador-pantalla.png)

![Primera grabación (Android, anonimizada)](evidencias/s2_primera-grabacion.png)

![Grabación de prueba en el simulador de iOS](evidencias/s2_grabacion-ios-simulador.png)

Explicación: [explicaciones/s2_explicacion.pdf](explicaciones/s2_explicacion.pdf)

## Sesión 3 · 2026-10-22 · Reglas SERT verificadas, prototipo del conductor espejo y protocolo casero

**Estado:** hecha (6/6 criterios).

- **Reglas SERT** (`app/docs/sert_reglas.md`): USD 0,25 por media hora (Art. 36 de la ordenanza), máximo 2 h y tarjeta de 4 casilleros de 30 min. **`tarifa.json` no necesita cambios.**
- **Modo espejo:** un selector de conductores y una pantalla con mapa (ruta, puesto, destino, auto que rota y peatón), línea de tiempo de 7 estados, costo en vivo, avisos y recibo frente a la tarjeta SERT.
- **Recorrido mock:** 60 mensajes que cumplen el JSON del contrato (§6b). La sesión dura 47 min simulados: 50 cobrados = $0,42, frente a $0,50 con la tarjeta.
- **Pruebas:** jest pasa 11/11 y tsc no da errores. Probado en Android real y en el simulador de iPhone.
- **`datos/PROTOCOLO_CASERO.md`:** grabaciones opcionales y la regla de seguridad.

![Prototipo del espejo](evidencias/s3_espejo-prototipo.png)

![Recibo y línea de tiempo completa](evidencias/s3_espejo-recibo.png)

Explicación: [explicaciones/s3_explicacion.pdf](explicaciones/s3_explicacion.pdf) · PDF semanal: [evidencias/resumen_S1_Miguel.pdf](evidencias/resumen_S1_Miguel.pdf)
