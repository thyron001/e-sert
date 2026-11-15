# Guion del video del plan B (3 min 40 s)

El video se armó con la **corrida 4 del ensayo de S4-2** (2026-11-14, 23:49–23:53):
- comando: `correr_guiado --escenario app50_s1 --gui --ritmo 5 --hasta 900`, en local;
- laptop con sumo-gui por VNC y el visor;
- teléfono Android en el modo espejo.

**Archivos:**
- video final: `crudo/e-sert_demo_plan_b.mp4`;
- subtítulos: `video_plan_b.srt` (también van incrustados como pista de texto);
- un fotograma por toma: `fotogramas/toma_<n>.png`.

| Toma | Tiempo | Duración | Qué se ve | Qué se dice (subtítulo) |
|---|---|---:|---|---|
| 1. Problema y app | 0:00–0:20 | 20 s | Tarjeta de título | "Con la tarjeta SERT pagas bloques de 30 min aunque te quedes 10. e-sert te guía a un puesto libre y cobra solo el tiempo real." |
| 2. Demo arrancando | 0:20–0:50 | 30 s | sumo-gui con el centro (izquierda), visor con puestos y autos (centro), teléfono en su pantalla de inicio y luego en el selector del modo espejo (derecha) | "La laptop simula el centro de Cuenca con SUMO y el visor muestra puestos y autos en vivo." · "El teléfono espejo elige un conductor simulado." |
| 3. Auto con app guiado | 0:50–1:30 | 40 s | Teléfono: el auto elegido (`sim_busca_7`) en Guiado hacia la Catedral Nueva, con la ruta azul; visor con los demás autos buscando; corte de red con modo avión y "Reconectando (1)" (fotograma `toma_3.png`, 1:15) | "La app le asignó un puesto y lo lleva por la ruta." · "Modo avión: Reconectando, y vuelve solo a En vivo." |
| 4. Estacionado y A pie | 1:30–2:30 | 60 s | `sim_busca_7` llega a su puesto junto a la Catedral: **Estacionado** (fotograma `toma_4.png`, 1:51). Luego `sim_busca_4` **A pie**, con costo en vivo y retenido de $0,25 <!-- fuente: semanas/S4/Miguel/codigo/app/src/contrato/tarifa.json:bloque_minimo_min --> | "El teléfono no se mueve: todo lo hace la simulación." · "El puesto sigue siendo suyo y el costo corre." |
| 5. Cierre y recibo | 2:30–3:10 | 40 s | El recibo se abre solo: 0,6 min → 10 min → $0,08 frente a $0,25 con tarjeta (cuadro congelado 22 s para leerlo) <!-- fuente: semanas/S4/Miguel/codigo/app/ensayo/resultados_ensayo.json:recibos --> | "La simulación detecta que se fue, cierra la sesión y abre el recibo." |
| 6. Fin y cierre | 3:10–3:40 | 30 s | `sim_busca_4` a pie hasta "Finalizado" (fotograma `toma_6.png`, 3:28); tarjeta final | "Los KPIs completos están en la sección de Tyrone del informe." |

**Diferencias con el guion del prompt de S4-3:**
- **Toma 3:** no se compara lado a lado con un auto "a ciegas". El visor muestra los autos sin app buscando, pero no se resalta uno.
- **Toma 4:** el visor del ensayo mostró "Puestos llenos 0/610" todo el tiempo, así que **no se ve el puesto en rojo** (fotogramas `toma_2.png` a `toma_6.png`; `../ensayo/registro_ensayo.md`). Se muestra que la sesión sigue abierta y cobrando durante A pie.
- **Toma 5:** `sim_busca_7` pasó de Estacionado a Cerrada sin REGRESANDO ni SALIENDO visibles: el ciclo dura 8 s a ritmo 5 <!-- fuente: semanas/S4/Miguel/codigo/app/ensayo/resultados_ensayo.json:tomas (toma 6, real_s 8) -->.
- **Toma 6:** el panel de KPIs del visor mostraba "—", así que se remite al informe.
- **Tomas 2 y 3:** se ve la terminal de la laptop al empezar. Para la versión final conviene recortar la ventana.
