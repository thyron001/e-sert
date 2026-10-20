---
semana: S4
persona: Miguel
sesion: 2
titulo: Prueba de campo final en el Centro con la simulación en vivo
horas: 3-4
modulo: datos
depende: [S4-Miguel-1, S4-Tyrone-1, S4-Pablo-1]
entrega: [datos/campo_final/protocolo.md, datos/campo_final/registro_campo.md, datos/campo_final/marcas_verdad.csv, datos/campo_final/trazas/, datos/campo_final/analizar_campo.py, datos/campo_final/resultados.json]
evidencias: [s2_campo-mapa.png, s2_campo-visor.png]
---
# S4 · Sesión 2 · Miguel 🔴: Prueba de campo final en el Centro con la simulación en vivo

## Contexto
Lee `CLAUDE.md`, `docs/CONTRATO.md` (secciones 3 y 7) y tu protocolo de grabación de S1-3.
Esta es la prueba que demuestra que el sistema funciona **fuera de la simulación**: teléfonos
reales en las calles SERT, apareciendo en el mismo visor que los autos de SUMO, con sesiones
reales que se abren, detectan la salida y cobran. La demo de Tyrone y el modelo final de
Pablo están en sus ramas: tráelos con `git archive origin/tyrone/s4 ...` y
`origin/pablo/s4` a una carpeta temporal y córrelos **sin editarlos**. Plazo: sábado 14, 23:59.

## Objetivo
Ejecutar una prueba de campo planificada con 2 a 4 teléfonos en el Centro mientras la
simulación corre en vivo, con verdad de terreno anotada, y medir retardo de cierre, falsas
liberaciones, error de cobro y latencia hasta el visor.

## Pasos
1. Escribe `datos/campo_final/protocolo.md` antes de salir:
   - **Infraestructura:** laptop con `python demo/demo.py` en un lugar fijo del Centro
     (cafetería con enchufe) y *hotspot* de un teléfono como LAN. No expongas el backend a
     internet; si fuera imprescindible un túnel, solo durante la prueba y con datos de prueba.
   - **Roles:** conductor (nunca toca el teléfono), acompañante que opera la app, anotador
     de verdad de terreno y quien vigila la laptop.
   - **Recorridos** (por teléfono): llegar en auto, parquear en un puesto SERT real (anota el
     `pa_` más cercano de `puestos.csv`), alejarse a pie más de 15 m 10–20 min, volver y salir
     manejando. Incluye el **caso difícil**: tramo de tráfico lento en la Gran Colombia o la
     Simón Bolívar, y una "trampa": caminar rápido cerca del auto sin subir.
   - **Verdad de terreno:** el anotador marca cada evento (`llega`, `estaciona`, `baja`,
     `vuelve`, `sube`, `sale`) con hora UTC en `marcas_verdad.csv`
     (`usuario_id,evento,ts`), usando el botón de marca del grabador de S1-2.
   - **Privacidad:** `usuario_id` tipo `app_<uuid4>`, placa de prueba (no la real) y
     recorte de los primeros y últimos 100 m de cada traza si empiezan en un domicilio.
2. Antes de salir, ensayo de 10 min en el lugar: los teléfonos se conectan desde **Ajustes
   de demo** y aparecen en el visor; la billetera de prueba tiene saldo.
3. Ejecuta la prueba (al menos 6 sesiones completas entre todos los teléfonos, con 1 iPhone
   y el Android como mínimo). Anota incidencias en `registro_campo.md` con la hora: pérdidas
   de GPS, la app pasada a segundo plano, cortes de red.
4. Exporta las trazas del grabador al CSV del contrato (sección 7) en
   `datos/campo_final/trazas/<usuario_id>.csv`, con `modo_real` sacado de las marcas.
5. Crea `datos/campo_final/analizar_campo.py`, que cruza marcas, trazas y la base de la demo
   (`demo.db` o `GET /sesiones/{id}` y `GET /billetera/{id}`) y calcula por sesión y en total:
   - **retardo de cierre:** `ts(CERRADA) − ts(sale)`;
   - **falsas liberaciones:** sesiones `CERRADA` antes de `sube`;
   - **error de cobro:** minutos cobrados frente a minutos reales (`sale − estaciona`), en
     minutos y en dólares;
   - F1 por clase del clasificador en vivo frente a `modo_real`, y el umbral recalculado
     sobre las mismas ventanas;
   - latencia ubicación → visor (`ts` del evento frente a la llegada del `snapshot`).
   Escribe `resultados.json`.
6. **Evidencias:**
   - `s2_campo-mapa.png`: las trazas sobre un fondo de calles (con `contextily` si hay red,
     si no con la red SUMO de `proyecto/sumo/`), coloreadas por modo predicho, con marcas de
     verdad y los puestos usados;
   - `s2_campo-visor.png`: captura del visor con los teléfonos entre los autos simulados
     (pídela al usuario o tómala en la laptop).

## VPS (demo en línea)
Lee `docs/DESPLIEGUE.md`. La prueba de campo final va **contra el VPS** (`https://demo.e-sert.tesisucuenca.com`) con datos móviles, con la simulación corriendo en una laptop y el visor público abierto. Documenta la cobertura y la latencia por punto del recorrido, y graba el video de respaldo desde el visor público y desde el teléfono a la vez.

## Dónde escribir
`semanas/S4/Miguel/codigo/datos/campo_final/` y `evidencias/`. Las trazas crudas grandes
(más de 5 MB) van en `.gitignore`; publica las recortadas y anonimizadas.

## Hecho cuando
- [ ] La prueba de campo se hizo contra el VPS (o queda documentado por qué no) y hay video de respaldo.
- [ ] `protocolo.md` y `registro_campo.md` existen y describen lo que de verdad pasó.
- [ ] Hay al menos 6 sesiones completas con marcas de verdad, en iPhone y en Android.
- [ ] `python datos/campo_final/analizar_campo.py` genera `resultados.json` con las cinco
  métricas.
- [ ] Las trazas publicadas validan contra `comun/esquemas.py` y no tienen datos personales.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 2, Miguel). En "Pedidos a
otros": @Pablo, ruta de las trazas de campo y su F1 para el informe; @Freddy, cualquier
cierre tardío o falsa liberación con su `sesion_id`; @Tyrone, problemas de la demo en campo.
