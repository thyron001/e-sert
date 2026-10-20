# Equipo, roles y calendario

| Persona | Color | Hex | Emoji | Rama git (semana N) | Rol principal |
|---|---|---|---|---|---|
| Tyrone | Azul | `#1E63D6` | 🔵 | `tyrone/sN` | Escenario SUMO, experimentos, KPIs y visor web |
| Freddy | Tomate | `#FF7043` | 🍅 | `freddy/sN` | Controlador TraCI, emulador GPS, guiado y backend FastAPI |
| Pablo | Verde | `#2E9E4F` | 🟢 | `pablo/sN` | IA: dataset, clasificador de movimiento y servicio de inferencia |
| Miguel | Rojo | `#C62828` | 🔴 | `miguel/sN` | App Expo: sensores, sesión de parqueo, billetera y Payphone |

## Módulos de `proyecto/` y dueños

Cada módulo tiene un dueño. Los demás pueden leerlo, pero no editarlo: si hace falta un
cambio, se deja como **pedido** en la bitácora y en la nota de entrega.

| Carpeta | Dueño | Contenido |
|---|---|---|
| `proyecto/sumo/` | Tyrone | Red OSM, `parkingArea`, demanda, configuraciones `.sumocfg` |
| `proyecto/kpis/` | Tyrone | Ejecutor de experimentos, cálculo de KPIs y gráficas |
| `proyecto/visor/` | Tyrone | Visor web Leaflet |
| `proyecto/demo/` | Tyrone | Lanzador de la demo en un solo comando |
| `proyecto/traci/` | Freddy | Controlador TraCI, emulador GPS, máquina de estados, peatones y guiado |
| `proyecto/backend/` (salvo las subcarpetas de Miguel) | Freddy | FastAPI, núcleo de billetera y sesiones, WebSocket |
| `proyecto/comun/` | Freddy (custodio) | Esquemas del contrato compartidos (Pydantic y TypeScript), `tarifa.json` |
| `proyecto/ia/` | Pablo | Preprocesamiento, ventanas, características, modelos e inferencia |
| `proyecto/informe/` | Pablo (editor) | Informe final; cada persona aporta su sección como archivo propio |
| `proyecto/app/` | Miguel | App Expo (React Native) |
| `proyecto/datos/` | Miguel | Grabaciones caseras etiquetadas (opcionales; sin salir al Centro) |
| `proyecto/backend/pagos/` | Miguel | Adaptador de Payphone en modo de pruebas |
| `proyecto/backend/asistente/` | Miguel | Entrada por lenguaje natural (LLM), opcional |

En `proyecto/informe/`, cada persona escribe solo su archivo de sección (`tyrone.md`,
`freddy.md`, `pablo.md`, `miguel.md`). Pablo integra el documento final.

## Calendario

| Semana | Fechas | Plazo de commits | Unificación automática |
|---|---|---|---|
| S1 | lun 19 – dom 25 oct | sáb 24 oct, 23:59 | dom 25 oct, 09:00 |
| S2 | lun 26 oct – dom 1 nov | sáb 31 oct, 23:59 | dom 1 nov, 09:00 |
| S3 | lun 2 – dom 8 nov | sáb 7 nov, 23:59 | dom 8 nov, 09:00 |
| S4 | lun 9 – dom 15 nov | sáb 14 nov, 23:59 | dom 15 nov, 09:00 |
| Entrega | lun 16 nov | — | — |

Cada persona hace **3 sesiones largas por semana** (unas 3–4 h cada una). El domingo, la
unificación las integra en `proyecto/`.
