---
semana: S4
persona: Tyrone
sesion: 3
titulo: Presentación, guion, resultados y ensayo de la demo
horas: 3-4
modulo: demo
depende: [S4-Tyrone-1, S4-Tyrone-2, S4-Miguel-3]
entrega: [demo/presentacion/diapositivas.md, demo/presentacion/diapositivas.pdf, demo/presentacion/guion.md, demo/presentacion/ensayo.md, demo/presentacion/checklist_entrega.md, demo/plan_b/snapshots_demo.jsonl]
evidencias: [s3_diapositiva-resultados.png, s3_ensayo-cronometro.png]
---
# S4 · Sesión 3 · Tyrone 🔵: Presentación, guion, resultados y ensayo de la demo

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md`, tu `demo/README.md` (sesión 1) y
`kpis/resultados/final/resumen.md` (sesión 2). Es la **última sesión del proyecto**: el plazo
es el **sábado 14 de noviembre a las 23:59**; lo que no esté en `tyrone/s4` a esa hora no
entra en la unificación final del domingo 15 a las 09:00 ni en la entrega del lunes 16.

## Objetivo
Dejar la presentación lista (diapositivas, guion por persona y tiempos), la demo ensayada
dos veces desde cero y un plan B escalonado si algo falla delante del profesor.

## Pasos
1. **Duración.** Si nadie confirmó la duración con el profesor, asume 20 min (15 de
   exposición y 5 de demo) más preguntas, y déjalo como parámetro en `guion.md`.
2. Crea `demo/presentacion/diapositivas.md` en formato Marp (12–15 diapositivas, tema claro,
   colores del equipo de `docs/EQUIPO.md`):
   - problema (búsqueda de parqueo en la zona SERT) y objetivo;
   - arquitectura (usa el diagrama de Freddy de `origin/freddy/s4:.../comun/docs/`);
   - escenario SUMO y línea base;
   - IA: falsas liberaciones, RF frente a umbral (figuras de Pablo);
   - app en modo espejo y cobro por tiempo real frente a tarjeta SERT (gráfica de S1-2 de Freddy);
   - **resultados**: una diapositiva con 3 cifras grandes (búsqueda, CO₂, falsas
     liberaciones al 50 %) con su IC, y la figura 2×2;
   - demo en vivo (simulación + teléfono espejo), limitaciones (todo es simulado, sin pruebas
     de campo) y conclusiones.
   Toda cifra sale de `resumen.csv`; nada escrito a mano. Las figuras se leen de las ramas
   con `git archive` si aún no están en `proyecto/`.
3. Genera `diapositivas.pdf` con una versión fija de `@marp-team/marp-cli`
   (`npx @marp-team/marp-cli@<versión> diapositivas.md --pdf --allow-local-files`) y anota la
   versión en `ensayo.md`.
4. Escribe `guion.md`: una tabla por diapositiva con minuto de inicio, quién habla (Tyrone:
   intro, escenario y resultados; Freddy: arquitectura, TraCI y backend; Pablo: IA; Miguel:
   app y teléfono espejo), la frase clave y la transición.
5. **Ensayo de la demo**, dos veces desde arranque en frío, con `python demo/demo.py
   --cronometro`:
   - mide arranque, demo guiada (auto buscando, el teléfono de Miguel siguiéndolo en modo
     espejo y resaltado en el visor, sesión cerrada con recibo) y apagado;
   - en la primera vuelta graba los mensajes WS a `demo/plan_b/snapshots_demo.jsonl` (unos
     5 min) para el plan B;
   - anota en `ensayo.md` cada tropiezo, su causa y la corrección.
6. **Plan B escalonado** en `ensayo.md`:
   1. Falla `sumo-gui` → `demo.py --sin-gui` y solo el visor.
   2. Falla el backend o la red → el servidor WS de prueba de S2 reproduce
      `snapshots_demo.jsonl` en el visor.
   3. Falla todo → el video de Miguel (`app/plan_b/ENLACE_VIDEO.md`, léelo de `origin/miguel/s4`).
7. Escribe `checklist_entrega.md` para el lunes 16: laptop cargada, *hotspot* de un teléfono
   (la WiFi de la universidad puede aislar clientes), IP fija anotada, firewall, Expo Go
   instalado, billetera de prueba recargada, `demo.db` limpia, PDF de diapositivas y video
   en USB.
8. **Evidencias:** `s3_diapositiva-resultados.png` (la diapositiva de resultados exportada,
   `--images png`) y `s3_ensayo-cronometro.png` (barras apiladas por fase de los dos ensayos
   frente al presupuesto de tiempo, desde `tiempos.json`).

## Dónde escribir
`semanas/S4/Tyrone/codigo/demo/presentacion/`, `semanas/S4/Tyrone/codigo/demo/plan_b/` y
`evidencias/`.

## Hecho cuando
- [ ] `diapositivas.pdf` existe y todas sus cifras coinciden con `resumen.csv`.
- [ ] `guion.md` asigna cada diapositiva a una persona y suma el tiempo objetivo (±1 min).
- [ ] Dos ensayos completos registrados en `ensayo.md`, el segundo sin tropiezos graves.
- [ ] `snapshots_demo.jsonl` se reproduce en el visor con el servidor WS de prueba.
- [ ] Existen las dos evidencias PNG y el **PDF semanal**
  (`python herramientas/resumen_pdf.py S4 Tyrone`).
- [ ] Todo está en `tyrone/s4` antes del sábado 14 a las 23:59.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 3, Tyrone), **incluido el PDF
semanal**. En "Pedidos a otros": a cada persona, su parte del guion y el minuto en que habla.
