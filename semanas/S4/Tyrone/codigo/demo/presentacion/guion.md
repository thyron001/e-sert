# Guion de la exposición: e-sert (lunes 16 de noviembre)

**Parámetro de duración:** `DURACION_MIN = 20` (15 min de exposición + 5 de demo) más preguntas.
Nadie confirmó otra duración con el profesor. Si cambia, se escalan los minutos de la columna
"Dura" de la exposición y la demo se mantiene en 5 min.

Diapositivas: `diapositivas.pdf` (15 diapositivas, generadas desde `resumen.csv`). Quién habla:
🔵 Tyrone (intro, escenario y resultados), 🍅 Freddy (arquitectura, TraCI y backend), 🟢 Pablo
(IA), 🔴 Miguel (app y teléfono espejo).

| # | Diapositiva | Inicio | Dura | Habla | Frase clave | Transición |
|---|---|---|---|---|---|---|
| 1 | Título | 00:00 | 0:30 | 🔵 Tyrone | "Simulamos qué pasa en el Centro Histórico si parte de los conductores usa una app que sabe dónde hay parqueo." | Presenta al equipo y su parte. |
| 2 | El problema | 00:30 | 1:00 | 🔵 Tyrone | "Quien busca parqueo circula a ciegas: gasta tiempo, combustible y congestiona a los demás." | "¿Qué propusimos?" |
| 3 | Objetivo y alcance | 01:30 | 1:00 | 🔵 Tyrone | "Todo es simulado: el teléfono refleja un auto de SUMO, no hay GPS real." | "Freddy explica cómo se conectan las piezas." |
| 4 | Arquitectura | 02:30 | 1:30 | 🍅 Freddy | "SUMO y el controlador TraCI publican el estado; el backend lleva sesiones y billetera y lo reparte por WebSocket." | "Tyrone muestra el escenario que corre en SUMO." |
| 5 | Escenario SUMO | 04:00 | 1:00 | 🔵 Tyrone | "Red de OpenStreetMap con los puestos SERT y una hora pico calibrada al 85–95 % de ocupación." | "Así se ve buscar sin ayuda." |
| 6 | Línea base (0 %) | 05:00 | 1:00 | 🔵 Tyrone | "Esta es la referencia: lo que tarda hoy un conductor sin app." | "Para ayudar, hay que saber cuándo se libera un puesto: Pablo." |
| 7 | IA: bajarse o seguir | 06:00 | 1:30 | 🟢 Pablo | "Con el GPS ruidoso del teléfono distinguimos caminar de conducir; el error caro es la falsa liberación." | "¿Y dentro de la simulación?" |
| 8 | IA: falsas liberaciones | 07:30 | 1:00 | 🟢 Pablo | "El *random forest* comete menos falsas liberaciones que un umbral de velocidad." | "Esto es lo que ve el usuario: Miguel." |
| 9 | App en modo espejo | 08:30 | 1:00 | 🔴 Miguel | "El teléfono sigue a un auto simulado: búsqueda, puesto, sesión y recibo." | "¿Cuánto paga? Freddy." |
| 10 | Cobro real vs tarjeta | 09:30 | 1:00 | 🍅 Freddy | "Se cobra el tiempo usado, no bloques completos de la tarjeta." | "¿Sirve para todos? Resultados." |
| 11 | Resultados al 50 % | 10:30 | 1:30 | 🔵 Tyrone | "Con la mitad de conductores con app, la búsqueda no baja frente a buscar a ciegas, pero el RF deja cero falsas liberaciones: el cobro queda correcto." | "Y cómo cambia con la penetración." |
| 12 | Figura 2×2 | 12:00 | 1:00 | 🔵 Tyrone | "Con el mapa del sistema, más usuarios no bajan la búsqueda; con la ocupación real (el rombo, el oráculo) bajaría cerca de un 18 %: falta información, no clasificador." | "Lo vemos en vivo." |
| 13 | Demo en vivo | 13:00 | 5:00 | 🔴 Miguel + 🔵 Tyrone | Tyrone: "sumo-gui y el visor"; Miguel: "mi teléfono sigue a este auto… ya parqueó… y aquí está el recibo." | Volver a las diapositivas (tecla `P` sale del modo presentación del visor). |
| 14 | Limitaciones | 18:00 | 1:00 | 🔵 Tyrone | "Todo es simulado, la IA se entrenó con datos de Pekín y son 5 semillas." | "Para cerrar…" |
| 15 | Conclusiones | 19:00 | 1:00 | 🔵 Tyrone | "El clasificador funciona y el sistema corre de punta a punta; para bajar la búsqueda falta una fuente de ocupación de los autos sin app." | "¿Preguntas?" |
| | **Total** | | **20:00** | | | |

## Por persona

| Persona | Diapositivas | Minutos | Tiempo total |
|---|---|---|---|
| 🔵 Tyrone | 1, 2, 3, 5, 6, 11, 12, 14, 15 (y demo: sumo-gui y visor) | 00:00, 00:30, 01:30, 04:00, 05:00, 10:30, 12:00, 18:00, 19:00 | 9:00 + demo |
| 🍅 Freddy | 4, 10 | 02:30, 09:30 | 2:30 |
| 🟢 Pablo | 7, 8 | 06:00, 07:30 | 2:30 |
| 🔴 Miguel | 9, 13 (demo con el teléfono) | 08:30, 13:00 | 1:00 + demo 5:00 |

## Demo (13:00–18:00), paso a paso

| Min | Qué se muestra | Quién |
|---|---|---|
| 13:00 | `demo.py` ya está corriendo desde antes de empezar (se lanza a las 00:00, arranque ≈ 10–20 s; `ritmo: 2`, así hay sesiones cerrándose desde el minuto ~9). Pantalla: `sumo-gui` por VNC. | 🔵 |
| 13:45 | Visor en el proyector, modo presentación (`P`), tecla `T` para el recorrido por la zona. | 🔵 |
| 14:30 | Miguel elige en la app un candidato que busca; el visor lo resalta con el halo, su ruta y el puesto asignado (`E` sigue al espejo). | 🔴 |
| 15:30 | Miguel cambia a un auto cuyo conductor ya vuelve (estado `REGRESANDO` en el *popup* del visor): así el cierre llega dentro de la demo. | 🔴 |
| 16:30 | Sesión `CERRADA` y recibo en el teléfono: lo cobrado frente a la tarjeta SERT (en los ensayos, 0,13 USD frente a 0,25 USD). | 🔴 |
| 17:30 | Panel de KPIs: búsqueda y falsas liberaciones en vivo frente a la base a ciegas. | 🔵 |

Si algo falla, se aplica el plan B escalonado de `ensayo.md` sin detener la exposición.
