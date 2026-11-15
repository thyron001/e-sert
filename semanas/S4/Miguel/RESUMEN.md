# S4 · Miguel

## Sesión 1 · Pulido final de la app y manual de usuario (parcial, 5/6)

La app quedó lista para la demo final:

- **Errores:** todo error se muestra en español con un botón de acción, y nunca aparece texto técnico.
- **Ajustes de demo:** pantalla oculta (pulsación larga de 3 s en el logo) para cambiar entre el VPS y un backend local sin reinstalar, con la latencia de `/salud`, candidatos y el WebSocket.
- **QA:** batería de 19 casos en Android contra el backend local y la simulación de Freddy en `van3twin`.
  - Pasan 18; el 6 queda con una observación.
  - Encontró 3 fallas, que quedaron corregidas: el formato del puesto, la recarga sin conexión sin botón y los decimales con punto.
- **iPhone:** solo en el simulador de iOS. Por eso el criterio "ambos teléfonos" queda parcial.
- **Manual:** `codigo/app/MANUAL.md`, con 8 capturas.
- **Calidad:** ESLint configurado (0 errores), `tsc` sin errores y Jest 254/254.

![Pantallas de la app](evidencias/s1_app-pantallas.png)

![Simulador de iOS](evidencias/s1_ios-simulador.png)

[Explicación (PDF)](explicaciones/s1_explicacion.pdf) · [Checklist de QA](codigo/app/CHECKLIST_QA.md) · [Manual](codigo/app/MANUAL.md)
