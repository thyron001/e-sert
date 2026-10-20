---
semana: S2
persona: Miguel
sesion: 3
titulo: Teléfono real enviando ubicación al visor y más grabaciones
horas: 3-4
modulo: app
depende: [S2-Miguel-1, S2-Freddy-1, S2-Tyrone-2, S1-Miguel-3]
entrega: [app/src/servicios/ubicacion.ts, app/src/servicios/cola.ts, datos/grabaciones/, datos/metadatos.csv, datos/validar.py]
evidencias: [s3_telefono-en-visor.png, s3_grabaciones-mapa.png]
---
# S2 · Sesión 3 · Miguel 🔴: Teléfono real enviando ubicación al visor y más grabaciones

## Contexto
Lee `CLAUDE.md` y `docs/CONTRATO.md` (secciones 1, 4, 6 y 7). Esta sesión tiene dos partes:
que un teléfono real aparezca en el mismo mapa que la simulación (lo verá el profesor en la
demo) y ampliar las grabaciones, que Pablo usa **hoy mismo** para su evaluación (S2-3). El
backend está en `proyecto/backend/` o `origin/freddy/s2`; el visor de Tyrone en
`proyecto/visor/` o `origin/tyrone/s2` (léelos sin editar). El protocolo de grabación de S1-3
está en `proyecto/datos/`. Recuerda: en iPhone la app debe estar abierta en primer plano.

## Objetivo
Enviar la ubicación del teléfono al backend a 1 Hz con una cola robusta, verla en el visor
junto a los autos simulados y sumar grabaciones etiquetadas de los casos difíciles.

## Pasos
1. **Identidad**: `usuario_id = "app_" + uuid4` generado una vez y guardado en AsyncStorage.
2. Crea `app/src/servicios/ubicacion.ts`:
   - `Location.watchPositionAsync({accuracy: Location.Accuracy.BestForNavigation,
     timeInterval: 1000, distanceInterval: 0})`;
   - por cada lectura construye el cuerpo de `POST /eventos/ubicacion` con
     `origen: "app"`, `ts` ISO UTC, `lat`, `lon`, `velocidad_mps` (`coords.speed`, `null` si
     es negativa) y `precision_m` (`coords.accuracy`);
   - interruptor "Compartir ubicación" en la pantalla de sesión, activo por defecto durante
     una sesión.
3. Crea `app/src/servicios/cola.ts`: cola en memoria con respaldo en AsyncStorage (máximo
   600 eventos), envío por lotes cada 5 s con reintento exponencial, y descarte de los más
   antiguos si se llena. Muestra en pantalla "en cola: N". Si el backend acepta lotes, úsalos;
   si no, envía uno por uno y deja el pedido a Freddy.
4. **Prueba con el visor**: laptop y teléfono en la misma red (o `npx expo start --tunnel`
   y el backend expuesto según indique Freddy), backend con `uvicorn --host 0.0.0.0`
   **en segundo plano**, visor abierto con `?ws=ws://<ip>:8000/ws/estado`. Camina por el
   Centro con la simulación corriendo y comprueba que el teléfono aparece en `telefonos`
   del snapshot y se mueve en el mapa. Si el snapshot no incluye `telefonos`, deja el pedido
   a Freddy y verifica al menos con `GET` o los logs del backend.
5. **Más grabaciones** con el grabador de S1-2 y el protocolo de S1-3 (mínimo de esta
   sesión):
   - 3 recorridos de auto en tráfico lento (≥ 10 min cada uno, Gran Colombia o Mariscal
     Lamar en hora pico);
   - 4 secuencias "estacionar → bajarse → caminar 200–400 m → volver → irse" (el caso de
     falsa liberación), con la hora de estacionamiento marcada;
   - 2 de quieto dentro del auto estacionado (≥ 5 min) y 2 de caminata lenta;
   - al menos 2 personas y los dos sistemas (iPhone y Android).
6. Crea `datos/validar.py`: cada CSV cumple la sección 7 del contrato, la frecuencia
   mediana es 1 Hz ± 0,1, la etiqueta `modo_real` no está vacía en más del 5 % de las filas,
   y `metadatos.csv` (`grabacion_id,persona,telefono,so,fecha,escenario,minutos,notas`) lista
   todas las grabaciones. Nombra los archivos
   `<fecha>_<persona>_<escenario>_<n>.csv`.
   Paraleliza: un subagente escribe `validar.py` y el mapa de evidencia mientras tú haces
   la cola de envío; las grabaciones de campo las hace el usuario.
7. **Evidencias**:
   - `s3_telefono-en-visor.png`: captura del visor con el teléfono real entre los autos
     simulados (y, si se puede, una foto de la pantalla del teléfono al lado);
   - `s3_grabaciones-mapa.png`: todas las grabaciones nuevas sobre el mapa del Centro,
     coloreadas por `modo_real` (matplotlib + `contextily` si está, o la red de SUMO de
     fondo).

## Dónde escribir
`semanas/S2/Miguel/codigo/app/`, `semanas/S2/Miguel/codigo/datos/` y
`semanas/S2/Miguel/evidencias/`. Revisa que las grabaciones no incluyan datos personales
(domicilios): recorta los primeros y últimos 2 min si empiezan en casa.

## Hecho cuando
- [ ] El backend recibe la ubicación del teléfono a ~1 Hz (cuéntalo en los logs durante
  5 min: ≥ 270 eventos).
- [ ] El teléfono aparece en el visor junto a la simulación (o el pedido a Freddy está
  documentado y el envío está verificado en el backend).
- [ ] La cola sobrevive a 1 min sin red y luego vacía todo.
- [ ] Hay al menos 11 grabaciones nuevas que pasan `python datos/validar.py`.
- [ ] Existen las dos evidencias PNG y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 3, Miguel), **incluido el PDF
semanal**. En "Pedidos a otros": @Pablo, ruta y lista de las grabaciones nuevas con sus
minutos por clase; @Freddy, si `telefonos` llega en el snapshot; @Tyrone, cómo se ve el
teléfono en el visor.
