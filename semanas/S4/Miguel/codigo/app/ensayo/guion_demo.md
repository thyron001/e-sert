# Guion de la demo de e-sert (6 min 45 s)

Todo es simulado: `sumo-gui` en la laptop, el visor en el proyector y el teléfono espejo en la
mano, siguiendo a un auto simulado. Los estados y avisos que se nombran son los del contrato
(§3 máquina de estados, §6 avisos, §7 espejo).

**Antes de empezar:** `checklist_previa.md` completa.

**Escenario recomendado:**
- `correr_guiado --escenario app50_s1 --gui --ritmo 5`, en local, o `demo.py`, que usa la semilla 2 y ritmo 2.
- Hay que elegir un auto **en Guiado durante los primeros 60 s** de la corrida. En el ensayo,
  `sim_busca_7` y otros parecidos cerraron en 1–4 min de reloj a ritmo 5, mientras que
  `sim_busca_4` tardó 14 min.
- Si el auto elegido no ha cerrado al llegar a la toma 6, se cambia a uno en `Saliendo` desde el selector.

| Toma | Duración | Quién | Qué se ve | Qué se dice |
|---|---|---|---|---|
| 1. Problema y app | 0:30 | Tyrone | Diapositiva: tarjeta SERT de 30 min frente a la app | "Hoy pagas bloques de 30 min aunque te quedes 10. e-sert te guía a un puesto libre y cobra el tiempo real." |
| 2. Arranque de la demo | 0:45 | Tyrone | `demo.py --remoto` (o `--local`): tabla de arranque; sumo-gui con el centro; visor con puestos verdes (con lugar) y rojos (llenos) | "La laptop simula el tráfico del centro con SUMO; el visor muestra los puestos SERT en vivo." |
| 3. Elegir el auto | 0:45 | Miguel | Teléfono: Sesión → Modo espejo → lista de candidatos; se toca uno en **Guiado**. En el visor, el auto queda con **halo amarillo** (`espejos`) | "Este teléfono va a ver lo que ve el conductor de este auto simulado." |
| 4. GUIADO | 1:00 | Miguel | Teléfono: mapa con la ruta y el puesto ("Puesto a N m"). sumo-gui: el mismo auto avanzando | "La app le asignó un puesto libre cerca de su destino y lo guía. Fíjense que el teléfono no se mueve." |
| 5. ESTACIONADO → A_PIE | 1:00 | Miguel + Freddy | Teléfono: Estacionado, luego **A pie**, con el costo en vivo y el retenido de $0,25. Visor: el peatón se aleja y **el puesto sigue rojo** | "El clasificador detecta que camina, pero el puesto sigue ocupado: no lo liberamos por error." |
| 6. REGRESANDO → SALIENDO → CERRADA | 1:00 | Miguel | Teléfono: Regresando, Saliendo y Cerrada. Se abre el **recibo** solo: tiempo real, débito y "Con la tarjeta SERT habrías pagado $X · Ahorraste $Y" | "Al irse, la simulación cierra la sesión: paga solo lo que usó." |
| 7. KPIs y cierre | 0:45 | Pablo + Tyrone | Panel de KPIs del visor (búsqueda guiada frente a búsqueda a ciegas) | "Menos vueltas buscando, menos tiempo y menos cobro. Gracias." |
| **Total** | **5:45 + 1:00 de margen = 6:45** | | | |

**Si algo falla:**

| Falla | Qué hacer |
|---|---|
| El VPS no responde | `demo.py` cae solo a `--local`. En el teléfono: pulsación larga de 3 s en el logo → Ajustes de demo → Local con la IP de la laptop → Probar conexión |
| El espejo dice "Reconectando" | Esperar: se reconecta solo con espera exponencial. Si pasan más de 30 s, tocar **Reconectar** |
| No hay candidatos | La corrida ya terminó: relanzar, o pasar al video de respaldo (`plan_b/`) |
| Nada funciona | Video de respaldo (S4-3) |
