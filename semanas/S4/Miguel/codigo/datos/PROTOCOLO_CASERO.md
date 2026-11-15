# Protocolo de grabaciones caseras (opcional)

**Solo si hay tiempo.** El clasificador se evalúa con GeoLife y con escenarios de SUMO. Estas
grabaciones son una validación extra para Pablo. **Nadie va al Centro**: se graba donde sea, en
la casa, el barrio o el campus.

## ⚠️ Seguridad, lo primero

- **Nunca grabes mientras manejas.** Las clases `vehiculo` y `vehiculo_lento` las graba **siempre
  el acompañante**.
- No te detengas en la vía para cambiar la etiqueta: hazlo cuando el auto esté detenido de forma
  segura, o deja que lo haga el acompañante.
- Caminando, mira el camino y no la pantalla.

## Cómo grabar

1. Abre la app en Expo Go, en la pestaña **Grabador**. Elige quién graba y el teléfono.
2. Espera a que la **precisión sea menor que 15 m** antes de pulsar Iniciar. Mientras tanto, mira
   el dato de precisión en la pantalla o graba un minuto de prueba.
3. Elige la etiqueta y pulsa **Iniciar**. Mantén la app abierta y la pantalla encendida: en iPhone,
   Expo Go no graba en segundo plano.
4. **Cambia la etiqueta en el momento justo** en que cambia el modo, sin detener la grabación. Por
   ejemplo, de "Vehículo" a "A pie" al bajarte del auto.
5. **Detener**. Luego **Compartir** el CSV del GPS (y **Acel.** si quieres el acelerómetro).

## Qué grabar

| Clase | Qué es | Duración sugerida |
|---|---|---|
| `a_pie` | Caminar normal por la vereda | 5 min |
| `quieto` | De pie o sentado, con el teléfono en la mano o el bolsillo | 5 min |
| `vehiculo` | En auto o bus con tráfico normal (graba el acompañante) | 5 a 10 min |
| `vehiculo_lento` | Auto en tráfico lento, a velocidad de peatón (atasco, fila). Se exporta como `vehiculo` + `escenario=trafico_lento` | 3 a 5 min |

Lo más útil es grabar las transiciones reales, por ejemplo vehículo → a pie → quieto → a pie →
vehículo, que es lo que hace un conductor al parquear y volver.

## Antes de subir

1. **Recorta los primeros y los últimos 2 min** si la grabación empieza o termina en un domicilio.
2. **Anonimiza** la grabación (la traslada al Parque Calderón sin deformarla):
   `python herramientas/anonimizar_grabacion.py original.csv --salida grabaciones/<nombre>.csv`
3. **Valida y grafica:** `python herramientas/graficar_grabacion.py grabaciones/<nombre>.csv`.
4. Nombre del archivo: `<fecha>_<persona>_<escenario>_<n>.csv`, por ejemplo
   `2026-10-25_pablo_trafico_lento_1.csv` o `2026-10-25_miguel_caminata_2.csv`.
5. Guárdala en `datos/grabaciones/`. El original con las coordenadas reales **no** se sube.
