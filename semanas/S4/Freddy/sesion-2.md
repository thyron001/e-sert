---
semana: S4
persona: Freddy
sesion: 2
titulo: Documentación técnica, arquitectura y diagramas de secuencia
horas: 3-4
modulo: comun
depende: [S4-Freddy-1]
entrega: [comun/docs/arquitectura.md, comun/docs/diagramas/, comun/docs/generar_diagramas.py, comun/docs/api.md, comun/docs/openapi.json, comun/docs/verificar_contrato_api.py, comun/docs/operacion.md, comun/docs/decisiones.md]
evidencias: [s2_arquitectura.png, s2_secuencia-cierre.png]
---
# S4 · Sesión 2 · Freddy 🍅: Documentación técnica, arquitectura y diagramas de secuencia

## Contexto
Lee `CLAUDE.md`, `docs/CONTRATO.md` y tu código de `traci/`, `backend/` y `comun/`. Como
custodio del contrato, eres quien mejor conoce cómo encajan las piezas. Esta documentación
la usan Pablo en el informe, Tyrone en la diapositiva de arquitectura y el profesor si
pregunta "¿cómo sabe el sistema que el auto se fue?". Plazo real: sábado 14, 23:59.

## Objetivo
Dejar en `comun/docs/` una documentación técnica autocontenida: arquitectura, diagramas de
secuencia generados desde texto, la API real comparada contra el contrato y una guía de
operación.

## Pasos
1. Lanza un subagente `Explore` que liste, sin editar, los puntos de entrada reales: rutas
   de FastAPI, mensajes WS, *hooks* del controlador, llamadas a `inferencia.clasificar` y a
   las funciones TraCI de guiado (`setParkingAreaStop` / `rerouteParkingArea`).
2. Diagramas como texto Mermaid en `comun/docs/diagramas/`:
   - `componentes.mmd`: SUMO + controlador TraCI (con GPS, máquina de estados, peatones,
     guiado e IA), núcleo, API FastAPI, WS, visor, app Expo, Payphone en modo prueba;
     flechas con el mensaje del contrato que viaja;
   - `despliegue.mmd`: la laptop de la demo (procesos y puertos) y los teléfonos por LAN;
   - `estados_sesion.mmd`: `stateDiagram-v2` con las transiciones y umbrales de la sección 3
     del contrato (15 m, 30 m, 20 m, 2 ventanas);
   - secuencias: `seq_llegada.mmd` (guía → confirmación → retención),
     `seq_falsa_liberacion_evitada.mmd` (ESTACIONADO → A_PIE → REGRESANDO → SALIENDO →
     CERRADA con las ventanas de la IA), `seq_vehiculo_simulado.mmd` (el controlador usa el
     núcleo directo frente a la app que usa HTTP), `seq_recarga_payphone.mmd` (pide a Miguel
     que lo valide) y `seq_snapshot_ws.mmd`.
3. `comun/docs/generar_diagramas.py`: renderiza cada `.mmd` a PNG y SVG con una versión fija
   de `@mermaid-js/mermaid-cli` (`npx -y @mermaid-js/mermaid-cli@<versión> -i x.mmd -o x.png
   -s 2`). Si no hay Node, cae a Graphviz o avisa con claridad. Anota la versión usada.
4. `comun/docs/verificar_contrato_api.py`: importa la `app` de FastAPI, vuelca
   `app.openapi()` a `openapi.json` y compara contra la tabla de la sección 4 de
   `docs/CONTRATO.md` (método, ruta, campos del cuerpo y de la respuesta). Sale con código 1
   si hay diferencias y las lista. Genera `api.md` con una tabla por endpoint y un ejemplo
   de `comun/ejemplos/`.
5. `arquitectura.md`: visión general, cada componente (responsabilidad, entradas, salidas,
   archivo principal), los diagramas incrustados, y cifras reales medidas ahora: ms por paso
   de TraCI con 80 % de penetración, latencia p50/p95 de la API y mensajes WS por segundo.
6. `decisiones.md` (registro de decisiones, una por bloque con contexto, decisión,
   alternativas y consecuencias): núcleo sin HTTP, SQLite, suscripciones TraCI, guiado con
   ocupación actual y no predicha, billetera como libro de movimientos, `verdad` solo en
   simulación.
7. `operacion.md`: cómo levantar cada pieza por separado, variables de entorno (`.env`, nunca
   credenciales en el repo), puertos, base de datos, logs y una tabla de fallas comunes.
8. **Evidencias:** `s2_arquitectura.png` (el render de `componentes.mmd`) y
   `s2_secuencia-cierre.png` (el render de `seq_falsa_liberacion_evitada.mmd`).

## Dónde escribir
`semanas/S4/Freddy/codigo/comun/docs/` y `evidencias/`. No edites `docs/` de la raíz: si la
verificación encuentra diferencias que deban cambiar el contrato, escríbelas en
`comun/CONTRATO.propuesto.md`.

## Hecho cuando
- [ ] `python comun/docs/generar_diagramas.py` regenera todos los PNG y SVG desde los `.mmd`.
- [ ] `python comun/docs/verificar_contrato_api.py` sale con código 0, o cada diferencia está
  resuelta en el código o propuesta en `CONTRATO.propuesto.md`.
- [ ] `arquitectura.md` incrusta todos los diagramas y tiene las tres cifras medidas.
- [ ] `decisiones.md` y `operacion.md` existen y no tienen `TODO`.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 2, Freddy). En "Pedidos a
otros": @Tyrone, ruta de `componentes.png` para la diapositiva; @Pablo, rutas de los
diagramas para el informe; @Miguel, revisa `seq_recarga_payphone.mmd`.
