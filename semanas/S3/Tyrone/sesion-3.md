---
semana: S3
persona: Tyrone
sesion: 3
titulo: Visor final - panel de KPIs en vivo, capa de teléfonos y modo presentación
horas: 3-4
modulo: visor
depende: [S2-Tyrone-2, S2-Freddy-1, S2-Miguel-3, S3-Tyrone-2]
entrega: [visor/index.html, visor/js/panel_kpis.js, visor/js/capa_telefonos.js, visor/js/presentacion.js, visor/css/visor.css, visor/datos/base.json, visor/servidor_prueba.py, visor/tests/]
evidencias: [s3_visor-final.png, s3_visor-presentacion.png]
---
# S3 · Sesión 3 · Tyrone 🔵: Visor final (panel de KPIs en vivo, capa de teléfonos y modo presentación)

## Contexto
Lee `CLAUDE.md` y `docs/CONTRATO.md` (sección 6, WebSocket). El visor de S2 ya pinta autos,
peatones y puestos desde `/ws/estado`. Ahora se convierte en la **pantalla de la demo**: debe
mostrar los KPIs en vivo, el teléfono real de Miguel moviéndose junto a la simulación y verse
bien en un proyector. El backend se lee desde `proyecto/backend/`. Si el teléfono de Miguel
(S2-Miguel-3) no llega a `snapshot.telefonos`, genera teléfonos sintéticos en
`servidor_prueba.py` marcados `# MOCK: reemplazar cuando Miguel envíe ubicación real`.

## Objetivo
Dejar el visor final: panel de KPIs que se actualiza con los mensajes `kpi`, capa de teléfonos
reales con su modo y un modo presentación a pantalla completa, robusto ante cortes del WS.

## Pasos
1. **Panel de KPIs** (`js/panel_kpis.js`), alimentado por `{"tipo": "kpi"}`:
   - tarjetas: búsqueda media (s), falsas liberaciones /100, ocupación (%), CO₂ de búsqueda
     (kg), sesiones activas y `t_sim` como reloj `hh:mm:ss`;
   - comparación con la búsqueda a ciegas: exporta desde `kpis/analisis.py` el archivo
     `visor/datos/base.json` (medias de penetración 0) y muestra "−X % vs a ciegas";
   - minigráfica de los últimos 10 min por KPI con Chart.js 4.4.1 desde cdnjs, sin animación;
   - redibujo limitado a 2 Hz (`requestAnimationFrame` + bandera de cambio).
2. **Capa de teléfonos** (`js/capa_telefonos.js`), desde `snapshot.telefonos`:
   - marcador distinto a los autos (icono de teléfono, `L.divIcon`) coloreado por modo
     (`a_pie` verde, `quieto` ámbar, `vehiculo` azul);
   - rastro de los últimos 60 s con `L.polyline` y círculo de precisión `L.circle(radio=precision_m)`;
   - *popup* con `usuario_id` recortado (`app_7f1c…`), modo, confianza y antigüedad;
   - sin datos durante 30 s pasa a gris; a los 120 s se elimina.
3. **Modo presentación** (`js/presentacion.js`), tecla `P` o `?presentacion=1`:
   - `document.documentElement.requestFullscreen()`, oculta controles, fuentes ×1,5 y leyenda
     grande (puesto libre/ocupado, auto con/sin app, peatón, teléfono);
   - encuadre automático a la zona SERT con `map.fitBounds` de los puestos;
   - tecla `T`: recorrido automático entre 3 vistas (zona completa, Parque Calderón, mercado
     10 de Agosto) cada 20 s; `H` muestra la ayuda de teclas.
4. **Robustez y rendimiento:**
   - reconexión del WS con espera exponencial 1, 2, 4… hasta 30 s e indicador de conexión;
   - con 80 % de penetración (~800 vehículos) usa `L.canvas()` y `L.circleMarker`, y actualiza
     posiciones en lugar de recrear capas; meta: tiempo por cuadro < 33 ms, medido con
     `performance.now()` y mostrado con la tecla `D` (depuración).
5. Extiende `servidor_prueba.py`: reproduce snapshots grabados, emite `kpi` cada 5 s y 2
   teléfonos sintéticos (uno camina, se queda quieto y vuelve en auto).
6. **Tests:** separa la lógica pura (formateo de KPIs, envejecimiento de teléfonos, cálculo del
   "−X %") en módulos ES y pruébala con `node --test visor/tests/*.test.mjs`.
7. Verifica de verdad en el navegador: abre el visor con `preview_start` contra
   `servidor_prueba.py` y luego contra el backend real; toma capturas. Mientras ajustas estilos,
   un subagente puede escribir los tests y otro extender el servidor de prueba.
8. **Evidencias:** `evidencias/s3_visor-final.png` (vista normal con panel y un teléfono
   visible) y `evidencias/s3_visor-presentacion.png` (modo presentación).

## Dónde escribir
`semanas/S3/Tyrone/codigo/visor/`, `semanas/S3/Tyrone/codigo/kpis/` (solo el exportador de
`base.json`) y `evidencias/`.

## Hecho cuando
- [ ] El panel se actualiza con mensajes `kpi` del servidor de prueba y del backend real.
- [ ] La capa de teléfonos muestra modo, rastro y precisión, y retira los teléfonos sin datos.
- [ ] El modo presentación funciona con `P`, `T` y `H`.
- [ ] Al apagar y reiniciar el servidor, el visor se reconecta solo en menos de 30 s.
- [ ] Con 800 vehículos, el tiempo por cuadro medido es menor que 33 ms.
- [ ] `node --test` pasa y existen las dos evidencias PNG y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 3, Tyrone), **incluido el PDF
semanal**. En "Pedidos a otros": @Freddy, confirma la frecuencia de los mensajes `kpi`; @Miguel,
necesito el teléfono enviando ubicación durante el ensayo de la demo en S4.
