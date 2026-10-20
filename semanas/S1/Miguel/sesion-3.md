---
semana: S1
persona: Miguel
sesion: 3
titulo: Reglas SERT verificadas, prototipo del conductor espejo y protocolo casero
horas: 4
modulo: app
depende: [S1-Miguel-1, S1-Miguel-2]
entrega: ["app/docs/sert_reglas.md", "app/app/espejo/index.tsx", "app/app/espejo/[vehId].tsx", "app/src/espejo/componentes/", "app/src/espejo/recorridoMock.ts", "app/src/espejo/recorrido_mock.json", "app/src/espejo/__tests__/recorridoMock.test.ts", "datos/PROTOCOLO_CASERO.md"]
evidencias: [s3_espejo-prototipo.png, s3_espejo-recibo.png]
---
# S1 · Sesión 3 · Miguel 🔴: Reglas SERT verificadas, prototipo del conductor espejo y protocolo casero

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (extras: teléfono espejo), `docs/CONTRATO.md` (secciones 3, 5 y
**6b**) y tu bitácora de S1-1 y S1-2. **Todo el proyecto es simulado**: nadie va al Centro a grabar
ni a hacer pruebas de campo. En la demo, el teléfono es un **espejo** de un conductor simulado de
SUMO: no se mueve ni envía su GPS. El backend del espejo (Freddy, S3-3) aún no existe, así que hoy
se construyen las pantallas con un recorrido **mock** que cumple al pie de la letra el JSON de 6b.
Además, la tarifa de `tarifa.json` es provisional y hay que verificarla contra la regulación real.

## Objetivo
Documentar las reglas SERT con fuentes, tener en Expo Go el prototipo completo del modo espejo
reproduciendo un recorrido mock de ~60 s (de `BUSCANDO` a `CERRADA` con recibo) y dejar un protocolo
corto para grabaciones caseras opcionales.

## Pasos
1. **Reglas SERT** (`app/docs/sert_reglas.md`). Investiga en fuentes oficiales (EMOV EP, ordenanza
   del SERT en Cuenca, sitio del GAD Municipal):
   - valor por hora o por fracción; horario y días de cobro;
   - **tiempo máximo de permanencia**;
   - número aproximado de plazas y calles incluidas;
   - cómo funciona la tarjeta prepago (bloques, precio por bloque).

   **Cita cada dato con su enlace y fecha de consulta.** Lo que no se pueda verificar se marca
   "no verificado". Termina con una tabla "Clave de `tarifa.json` / Valor actual / Valor real /
   Fuente" para que Freddy actualice el contrato. Revisa `calles_sert.yaml` de Tyrone (de su rama,
   sin editar) y deja observaciones en la bitácora.
2. **Tipos** en `app/src/api/tipos.ts`: `CandidatoEspejo {id, destino_nombre, estado, t_sim}`,
   `MensajeEspejo` (6b, con `ruta: [number, number][]`, `sesion | null`, `recibo | null`),
   `ReciboEspejo {minutos_reales, minutos_cobrados, cobrado_usd, tarjeta_sert_usd, ahorro_usd}`,
   `FinEspejo {tipo: "espejo_fin", veh_id}` y `EstadoSesion` como unión literal de los 7 estados.
   Si `comun/esquemas.ts` de Freddy ya los trae, impórtalos; si no, márcalos `// SINCRONIZAR con comun/esquemas.ts`.
3. **Recorrido mock** (`app/src/espejo/recorridoMock.ts`, marcado `// MOCK: reemplazar por WS /ws/espejo (S2-3)`):
   - genera ~60 mensajes (1 por segundo real) para `sim_veh42` con destino Parque Calderón
     (-2.8975, -79.0045); `t_sim` avanza de forma no uniforme para que la sesión dure 47 min
     simulados: BUSCANDO (5 s) → GUIADO (12 s, la posición avanza sobre `ruta`) → ESTACIONADO (6 s)
     → A_PIE (15 s) → REGRESANDO (8 s) → SALIENDO (6 s) → CERRADA (recibo);
   - `costo_usd` y el recibo se calculan con `tarifa.json` (fracciones de 5 min, cobro mínimo; con
     los valores provisionales: 47 min → 50 cobrados → $0,42; tarjeta 2 bloques $0,50; ahorro $0,08);
   - `avisos: ["saldo_bajo"]` en algún tramo de ESTACIONADO; termina con un `espejo_fin`;
   - exporta también `recorrido_mock.json` (con `npm run generar-mock`), que el servidor mock de S2-3
     reproducirá tal cual;
   - `suscribirMock(vehId, onMensaje): () => void` con la misma firma que tendrá el cliente WS real.
4. **Pantallas** (`expo-router`):
   - `app/espejo/index.tsx`: selector de vehículo con 3–5 candidatos mock (id, destino, estado,
     `t_sim` formateado mm:ss) en `FlatList`; al tocar, `router.push("/espejo/" + id)`;
   - `app/espejo/[vehId].tsx` con componentes en `app/src/espejo/componentes/`:
     `MapaEspejo` (`react-native-maps`: `Marker` del auto que rota según el rumbo, `Marker` del
     destino, `Marker` del puesto, `Polyline` de `ruta` con `strokeWidth={5}`, `animateToRegion`
     suave cada mensaje), `LineaTiempo` (7 pasos horizontales, el actual resaltado y los pasados
     con su `t_sim`), `CostoVivo` (minutos, costo, retenido, disponible), `BannerAvisos` y
     `ReciboEspejo` (modal al llegar `recibo`, "Con la tarjeta SERT habrías pagado $X").
   - Botón "Reiniciar recorrido" para repetir los 60 s en la demo.
5. **Test** `recorridoMock.test.ts` (`jest-expo`): todos los mensajes cumplen el tipo (validador
   en tiempo de ejecución `esMensajeEspejo`), los estados nunca retroceden, el recibo cuadra con la
   tarifa y la duración total está entre 55 y 65 s. `npx tsc --noEmit` sin errores.
6. **Protocolo casero** `datos/PROTOCOLO_CASERO.md` (máximo 1 página): grabaciones **opcionales**,
   solo si hay tiempo, con el grabador de S1-2, **donde sea** (casa, barrio, campus), sin ir al
   Centro; clases `a_pie`, `quieto`, `vehiculo` y `vehiculo_lento`; **seguridad: nunca grabar
   mientras se maneja, siempre graba el acompañante**; esperar precisión < 15 m; recortar los
   primeros y últimos 2 min si empiezan en un domicilio; nombre `<fecha>_<persona>_<escenario>_<n>.csv`.
7. **Evidencias**: pide al usuario capturas del teléfono en Expo Go y únelas con Pillow:
   - `s3_espejo-prototipo.png`: selector, GUIADO (mapa con ruta y puesto) y A_PIE, lado a lado;
   - `s3_espejo-recibo.png`: la pantalla con el recibo y la línea de tiempo completa.

## Dónde escribir
`semanas/S1/Miguel/codigo/app/` y `semanas/S1/Miguel/codigo/datos/`.

## Hecho cuando
- [ ] `sert_reglas.md` tiene fuentes citadas con fecha y la tabla de comparación para `tarifa.json`.
- [ ] El recorrido mock se reproduce completo en Expo Go en ~60 s, de BUSCANDO al recibo.
- [ ] `npx jest app/src/espejo` y `npx tsc --noEmit` pasan.
- [ ] `recorrido_mock.json` existe y cada mensaje cumple el JSON de CONTRATO 6b.
- [ ] `PROTOCOLO_CASERO.md` existe e incluye la regla de seguridad.
- [ ] Existen las dos evidencias PNG y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 3, Miguel), **incluido el PDF
semanal**. En "Pedidos a otros": @Freddy, valores reales para `tarifa.json` y los tipos del espejo en
`comun/esquemas.ts`; @Tyrone, observaciones a `calles_sert.yaml`; @Pablo, las grabaciones caseras son
opcionales y, si se hacen, quedan en `datos/grabaciones/`.
