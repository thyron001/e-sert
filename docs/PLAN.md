# Plan de 4 semanas (3 sesiones por persona por semana)

Cada sesión tiene su prompt detallado en `semanas/SN/<Nombre>/sesion-K.md`. Este documento
es el mapa general: qué hace cada persona, en qué orden y qué necesita de los demás.

## S1 · 19–25 oct · Cimientos y contrato

| | Sesión 1 | Sesión 2 | Sesión 3 |
|---|---|---|---|
| 🔵 Tyrone | Red OSM del Centro en SUMO (veredas, cruces, edificios) | Generación de puestos SERT (`parkingArea`, `puestos.csv`) | Demanda de hora pico y búsqueda a ciegas (línea base) calibrada al 85–95 % de ocupación |
| 🍅 Freddy | Contrato v1 + `comun/` (Pydantic, TS, ejemplos, tests) | Núcleo del backend: billetera, tarifa, sesiones y ocupación (sin HTTP) | Controlador TraCI base + emulador GPS con ruido AR(1) + trazas etiquetadas |
| 🟢 Pablo | Ingesta de GeoLife → CSV del contrato | Remuestreo a 1 Hz, ventanas de 30 s, clase "quieto" y características | Línea base por umbral + primer Random Forest (GroupKFold por usuario) + `inferencia.py` |
| 🔴 Miguel | Proyecto Expo: navegación, pantallas, cliente API con mock | Grabador de sensores etiquetado (GPS 1 Hz + acelerómetro) con exportación CSV | Protocolo de grabación + primeras grabaciones en el Centro + reglas SERT verificadas |

## S2 · 26 oct – 1 nov · Piezas funcionando por separado

| | Sesión 1 | Sesión 2 | Sesión 3 |
|---|---|---|---|
| 🔵 Tyrone | KPIs de la línea base (`kpis/kpis.py`): búsqueda en tiempo y distancia, CO₂, ocupación | Visor web Leaflet + servidor WS de prueba que reproduce snapshots | Escenarios con penetración de app (0/20/50/80 %) + registro de la ocupación real |
| 🍅 Freddy | Capa FastAPI sobre el núcleo + WebSocket + Swagger | Máquina de estados + peatones que hacen diligencias (TraCI) | Guiado con `rerouteParkingArea`, sesiones y cobro integrados en la simulación |
| 🟢 Pablo | Ventanas desde trazas de SUMO + ruido calibrado con grabaciones reales | Ajuste de hiperparámetros, importancia, suavizado temporal → `rf_v1` | Evaluación con datos de Cuenca (nunca vistos), incluido el tráfico lento |
| 🔴 Miguel | Flujo de sesión de parqueo en la app (buscar → guiar → confirmar → activa) | Billetera + recarga con Payphone en modo de pruebas (`backend/pagos/`) | Teléfono real enviando ubicación (aparece en el visor) + más grabaciones |

## S3 · 2–8 nov · Integración y experimentos

| | Sesión 1 | Sesión 2 | Sesión 3 |
|---|---|---|---|
| 🔵 Tyrone | Ejecutor de experimentos (penetración × clasificador × semillas) | Análisis estadístico y figuras finales de KPIs | Visor final: panel de KPIs en vivo, capa de teléfonos y modo presentación |
| 🍅 Freddy | KPIs de sistema: falsas liberaciones, retardo de cierre, error de facturación, precisión del mapa | Rendimiento y robustez (pérdida de GPS, teléfono apagado, 80 % de penetración) | Clasificación en vivo de teléfonos reales y cierre automático de sesión |
| 🟢 Pablo | Servicio de inferencia robusto (huecos, latencia < 5 ms, *fallback*) | Análisis de errores y efecto del suavizado en las falsas liberaciones | Borrador de la sección de IA del informe |
| 🔴 Miguel | Cierre automático en la app + recibo ("con tarjeta habrías pagado X") | Avisos: saldo bajo, tiempo máximo y bloqueo por saldo negativo | Entrada por lenguaje natural (LLM, opcional) o pulido de UX |

## S4 · 9–15 nov · Cierre, demo e informe

| | Sesión 1 | Sesión 2 | Sesión 3 |
|---|---|---|---|
| 🔵 Tyrone | Demo en un comando (`demo/`): backend + sumo-gui + visor | Corrida final de experimentos con el modelo y el controlador finales | Presentación: guion, resultados y ensayo de la demo |
| 🍅 Freddy | Pruebas de punta a punta (`pytest -m e2e`) | Documentación técnica: arquitectura y diagramas de secuencia | Sección backend/TraCI del informe + ensayo de la demo |
| 🟢 Pablo | Modelo final congelado + *model card* | Sección de IA final + preguntas probables del profesor | Integración del informe completo (`proyecto/informe/`) |
| 🔴 Miguel | Pulido final de la app + manual de usuario | Prueba de campo final en el Centro con la simulación en vivo | Sección de la app en el informe + plan B de la demo (video) |

## Demo en línea (VPS)

Ver `docs/DESPLIEGUE.md`.

- **S2:** Freddy deja el backend desplegable (Dockerfile, `/salud`, token).
- **Después de la unificación de S2 (dom 1 nov):** Tyrone crea la app `esert-demo` en Dokploy
  con `demo.e-sert.tesisucuenca.com`.
- **S3:** Freddy prueba en línea con un teléfono real con datos móviles, y Tyrone publica el
  visor final con su QR.
- **S4:** demo `--remoto` con plan B `--local`, y prueba de campo de Miguel contra el VPS.

## Dependencias críticas

- La red y los puestos de Tyrone (S1) los necesitan Freddy y Pablo en S1-3 y S2-1.
- Las trazas de SUMO de Freddy (S1-3) las necesita Pablo en S2-1.
- Las grabaciones de Miguel (S1-3 y S2-3) las necesita Pablo en S2-1 y S2-3.
- `inferencia.py` de Pablo (S1-3 y S2-2) lo necesita Freddy en S2-2 y S3-1.
- El controlador con KPIs de Freddy (S3-1) lo necesita Tyrone en S3-1 y S3-2.
- La API de Freddy (S2-1) la necesitan Miguel (S2) y el visor de Tyrone (S2-2, con mock
  mientras tanto).
