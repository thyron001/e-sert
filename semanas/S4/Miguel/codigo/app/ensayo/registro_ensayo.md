# Registro del ensayo (2026-11-14)

## Ensayo A, contra el VPS: no se pudo hacer completo

- **22:49:53:** `curl https://demo.e-sert.tesisucuenca.com/salud` respondió `{"ok":true,"contrato":1,"t_sim":null}`.
- `demo.py --remoto` necesita `ESERT_TOKEN_SIM`, que solo tiene Tyrone. Sin él, el VPS rechaza los snapshots y `demo.py` cae solo a `--local`.
  - Sin simulación en el VPS, el selector del teléfono queda vacío ("0 autos con app" en Ajustes de demo).
  - Pedido `@Tyrone [VPS]` en la bitácora.

## Ensayo B, en local (plan B)

**Montaje:**
- **Laptop:**
  - backend `proyecto/backend` en `0.0.0.0:8000` (base nueva, Payphone mock);
  - visor `proyecto/visor` servido en `:8088` con `?ws=ws://127.0.0.1:8000/ws/estado`;
  - sumo-gui por VNC;
  - `correr_guiado --escenario app50_s1 --gui` en el contenedor.
- **Teléfono:** Android con Expo Go por Tailscale (100.85.244.14:8000), desde Ajustes de demo.
- **Por qué no `demo.py --local`:** busca la raíz del repo (la carpeta con `CLAUDE.md`) y `kpis/correr_una.py`, que solo está en `tyrone/s4`. Desde una carpeta temporal con `git archive` no arranca sin editarlo. Se usaron las mismas piezas a mano.

| Hora | Corrida | Toma | Previsto | Real | Incidencia |
|---|---|---|---|---|---|
| 23:17 | 1: `--ritmo 5 --hasta 1800` | 2–3 | 1:30 | ~1:00 (candidatos a los 10 s) | Grabación de la Mac iniciada (palmada). El teléfono eligió `sim_busca_4`; el visor lo resaltó con el halo amarillo |
| 23:18–23:24 | 1 | 4 | 1:00 | 6:00 | Modo avión: el WS de `sim_busca_4` se reabrió solo (2 conexiones aceptadas en el log del backend). `sim_busca_4` no llegó a cerrar en 6 min: a ritmo 5 su sesión dura ~14 min de reloj (la de S4-1 duró 65,8 min simulados) |
| 23:24 | 1 | — | — | — | Fin de la corrida (1801 eventos, 0 fallidos). No apareció "Exportar CSV": el auto no recibió `espejo_fin` en pantalla |
| 23:28–23:33 | 2: `--ritmo 2 --hasta 600` | 3–4 | 1:45 | 5:00 | De nuevo `sim_busca_4`, con una reconexión. No se pudo exportar el CSV |
| 23:36–23:40 | 3: `--ritmo 1 --hasta 240` | 3–4 | 1:45 | 4:00 | Corrida corta para terminar con el auto en Guiado y obtener el CSV |

**Desviación respecto al guion:**
- Las tomas 5 y 6 (A_PIE con el puesto rojo y el recibo) no cupieron en el ensayo: el auto elegido tarda más que las tomas 4–6.
- Para la demo: elegir un auto que ya esté en Estacionado o A pie en el selector, o usar `demo.py` con la semilla 2 y ritmo 2, donde Tyrone midió el primer cierre en t = 1014 s.
- El total del guion **no se cumplió con ±30 s**.
