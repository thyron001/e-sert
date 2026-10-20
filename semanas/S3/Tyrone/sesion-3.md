---
semana: S3
persona: Tyrone
sesion: 3
titulo: Visor final - panel de KPIs en vivo, vehículo espejo resaltado y modo presentación
horas: 3-4
modulo: visor
depende: [S2-Tyrone-2, S2-Freddy-1, S2-Miguel-3, S3-Tyrone-2, S3-Freddy-3]
entrega: [visor/index.html, visor/js/panel_kpis.js, visor/js/capa_espejo.js, visor/js/presentacion.js, visor/css/visor.css, visor/datos/base.json, visor/servidor_prueba.py, visor/tests/]
evidencias: [s3_visor-final.png, s3_visor-presentacion.png]
---
# S3 · Sesión 3 · Tyrone 🔵: Visor final (panel de KPIs en vivo, vehículo espejo resaltado y modo presentación)

## Contexto
Lee `CLAUDE.md` y `docs/CONTRATO.md` (sección 6, WebSocket). El visor de S2 ya pinta autos,
peatones y puestos desde `/ws/estado`. Ahora se convierte en la **pantalla de la demo**: debe
mostrar los KPIs en vivo, **resaltar el vehículo simulado que sigue el teléfono espejo** de
Miguel (`snapshot.espejos`, `docs/CONTRATO.md` 6 y 6b) y verse bien en un proyector. Todo es
simulado: ningún teléfono envía su GPS. El backend se lee desde `proyecto/backend/`; el modo
espejo lo publica Freddy hoy (S3-3, `origin/freddy/s3`, solo lectura). Si `snapshot.espejos`
aún no llega, el `servidor_prueba.py` elige vehículos con app marcados
`# MOCK: reemplazar cuando el backend publique espejos (Freddy S3-3)`.

## Objetivo
Dejar el visor final: panel de KPIs que se actualiza con los mensajes `kpi`, capa que resalta el
vehículo espejo con su ruta y su puesto asignado, y un modo presentación a pantalla completa, robusto ante cortes del WS.

## Pasos
1. **Panel de KPIs** (`js/panel_kpis.js`), alimentado por `{"tipo": "kpi"}`:
   - tarjetas: búsqueda media (s), falsas liberaciones /100, ocupación (%), CO₂ de búsqueda
     (kg), sesiones activas y `t_sim` como reloj `hh:mm:ss`;
   - comparación con la búsqueda a ciegas: exporta desde `kpis/analisis.py` el archivo
     `visor/datos/base.json` (medias de penetración 0) y muestra "−X % vs a ciegas";
   - minigráfica de los últimos 10 min por KPI con Chart.js 4.4.1 desde cdnjs, sin animación;
   - redibujo limitado a 2 Hz (`requestAnimationFrame` + bandera de cambio).
2. **Vehículo espejo resaltado** (`js/capa_espejo.js`), desde `snapshot.espejos`:
   - cada ID de `espejos` se dibuja encima del resto con un halo pulsante (`L.divIcon` con
     animación CSS) y una etiqueta "espejo"; si su conductor se bajó, el halo pasa a su
     peatón (`ped_<veh>`);
   - rastro de los últimos 60 s con `L.polyline`; si el visor abre con `?espejo=<veh_id>`, se
     conecta además a `WS /ws/espejo/{veh_id}` y dibuja la `ruta` restante y el `puesto`
     asignado (línea punteada al puesto);
   - *popup* con `id`, estado de la sesión, destino y costo en vivo (si hay WS espejo);
   - cuando el ID sale de `espejos` o llega `espejo_fin`, el resaltado se retira en 5 s.
3. **Modo presentación** (`js/presentacion.js`), tecla `P` o `?presentacion=1`:
   - `document.documentElement.requestFullscreen()`, oculta controles, fuentes ×1,5 y leyenda
     grande (puesto libre/ocupado, auto con/sin app, peatón, vehículo espejo);
   - encuadre automático a la zona SERT con `map.fitBounds` de los puestos; tecla `E`: la
     cámara sigue al vehículo espejo (`map.panTo` suave);
   - tecla `T`: recorrido automático entre 3 vistas (zona completa, Parque Calderón, mercado
     10 de Agosto) cada 20 s; `H` muestra la ayuda de teclas.
4. **Robustez y rendimiento:**
   - reconexión del WS con espera exponencial 1, 2, 4… hasta 30 s e indicador de conexión;
   - con 80 % de penetración (~800 vehículos) usa `L.canvas()` y `L.circleMarker`, y actualiza
     posiciones en lugar de recrear capas; meta: tiempo por cuadro < 33 ms, medido con
     `performance.now()` y mostrado con la tecla `D` (depuración).
5. Extiende `servidor_prueba.py`: reproduce snapshots grabados, emite `kpi` cada 5 s,
   rellena `espejos` con 1–2 vehículos con app y sirve un `WS /ws/espejo/{veh_id}` de prueba con
   los campos de 6b (marcado `# MOCK`).
6. **Tests:** separa la lógica pura (formateo de KPIs, retiro del resaltado espejo, cálculo del
   "−X %") en módulos ES y pruébala con `node --test visor/tests/*.test.mjs`.
7. Verifica de verdad en el navegador: abre el visor con `preview_start` contra
   `servidor_prueba.py` y luego contra el backend real; toma capturas. Mientras ajustas estilos,
   un subagente puede escribir los tests y otro extender el servidor de prueba.
8. **Evidencias:** `evidencias/s3_visor-final.png` (vista normal con panel y un vehículo
   espejo resaltado con su ruta) y `evidencias/s3_visor-presentacion.png` (modo presentación).

## VPS (demo en línea)
Lee `docs/DESPLIEGUE.md`. El visor final se publica en `https://demo.e-sert.tesisucuenca.com/visor` (lo sirve el backend). Añade un enlace "Demo en vivo" al roadmap (`roadmap/templates/base.html`, que es tuyo) que apunte ahí. El modo presentación debe verse bien en el proyector (1920×1080) y en un teléfono (el QR es solo un enlace abreviado al visor para que el profesor lo abra en su celular: genera
`evidencias/s3_qr-demo.png` con `qrcode` apuntando a `https://demo.e-sert.tesisucuenca.com/visor`).

## Dónde escribir
`semanas/S3/Tyrone/codigo/visor/`, `semanas/S3/Tyrone/codigo/kpis/` (solo el exportador de
`base.json`) y `evidencias/`.

## Hecho cuando
- [ ] El visor funciona en la URL pública (o, si la demo aún no está desplegada, servido desde el backend local en `/visor/`), y existe el QR.
- [ ] El panel se actualiza con mensajes `kpi` del servidor de prueba y del backend real.
- [ ] El vehículo de `espejos` se ve resaltado con rastro, ruta y puesto, y el resaltado se retira
  al dejar de seguirlo.
- [ ] El modo presentación funciona con `P`, `T`, `E` y `H`.
- [ ] Al apagar y reiniciar el servidor, el visor se reconecta solo en menos de 30 s.
- [ ] Con 800 vehículos, el tiempo por cuadro medido es menor que 33 ms.
- [ ] `node --test` pasa y existen las dos evidencias PNG y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 3, Tyrone), **incluido el PDF
semanal**. En "Pedidos a otros": @Freddy, confirma la frecuencia de los mensajes `kpi`; @Miguel,
el visor resalta el vehículo que sigues y acepta `?espejo=<veh_id>` para el ensayo de la demo en S4.
