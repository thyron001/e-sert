---
semana: S1
persona: Miguel
sesion: 3
titulo: Protocolo y jornada de grabación en el Centro + reglas SERT
horas: 4
modulo: datos
depende: [S1-Miguel-2]
entrega: [datos/PROTOCOLO.md, datos/grabaciones/, datos/inventario.csv, app/docs/sert_reglas.md]
evidencias: [s3_mapa-grabaciones.png, s3_horas-por-clase.png]
---
# S1 · Sesión 3 · Miguel 🔴: Protocolo y jornada de grabación en el Centro + reglas SERT

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` y tu bitácora. Las grabaciones de esta sesión son el
**conjunto de prueba con datos de Cuenca**: la evidencia más fuerte del proyecto. Además, la
tarifa del contrato (`tarifa.json`) es provisional y alguien tiene que verificarla contra la
regulación real del SERT.

## Objetivo
Definir un protocolo de grabación reproducible, ejecutar una primera jornada en el Centro
Histórico y documentar las reglas reales del SERT con fuentes.

## Pasos
1. `datos/PROTOCOLO.md` (1–2 páginas), con:
   - **Clases y metas:** al menos 30 min por clase (`a_pie`, `quieto`, `vehiculo`) y
     **al menos 20 min de `vehiculo_lento`** (tráfico en Gran Colombia o Bolívar en hora
     pico).
   - **Variedad:** al menos 2 teléfonos iOS y 1 Android; teléfono en el bolsillo, en la mano
     y en el soporte del auto; calles angostas (cañón urbano) frente a plazas abiertas.
   - **Procedimiento:**
     - esperar a que la precisión baje de 15 m antes de iniciar;
     - anotar la ruta;
     - cambiar la etiqueta en caliente al bajarse o subirse;
     - nunca grabar mientras se maneja: graba el acompañante.
   - **Escenario clave de falsa liberación:** estacionar, bajarse, caminar 3 cuadras,
     hacer una diligencia de 5 min y volver. Graba la secuencia completa como una sola
     grabación con cambios de etiqueta.
2. **Jornada de grabación**, coordinada con quien esté disponible del grupo. Guía al usuario
   durante la jornada: Claude le recuerda las metas y lleva la cuenta de lo grabado.
3. Copia los CSV a `datos/grabaciones/AAAA-MM-DD/` con el nombre del exportador.
   - Crea `datos/inventario.csv` (`archivo,persona,telefono,duracion_min,min_por_clase,precision_media,notas`),
     generado por `datos/herramientas/inventario.py`, que además valida cada CSV contra el
     contrato.
   - Si los datos pesan más de 20 MB, guarda solo el inventario y comparte los CSV por Drive,
     con el enlace en `datos/README.md`.
4. **Reglas SERT** (`app/docs/sert_reglas.md`). Investiga en fuentes oficiales (EMOV EP,
   ordenanza del SERT en Cuenca, sitio del GAD Municipal):
   - valor por hora o por fracción;
   - horario y días de cobro;
   - **tiempo máximo de permanencia**;
   - número aproximado de plazas y calles incluidas;
   - cómo funciona la tarjeta prepago.

   **Cita cada dato con su enlace y fecha de consulta.** Lo que no se pueda verificar se
   marca "no verificado". Termina con una tabla "Valor en `tarifa.json` / Valor real /
   Fuente" para que Freddy actualice el contrato.
5. Revisa `calles_sert.yaml` de Tyrone (de su rama) contra lo que encuentres y deja
   observaciones en la bitácora.
6. **Evidencias:**
   - `s3_mapa-grabaciones.png`: todas las trazas sobre el Centro, coloreadas por clase
     (usa `contextily` si está disponible; si no, solo lat/lon).
   - `s3_horas-por-clase.png`: minutos grabados por clase frente a la meta del protocolo.

## Dónde escribir
`semanas/S1/Miguel/codigo/datos/` y `semanas/S1/Miguel/codigo/app/docs/`.

## Hecho cuando
- [ ] `PROTOCOLO.md` está completo, e `inventario.csv` está generado y validado.
- [ ] Hay al menos 60 min de grabación total con las 3 clases. Si faltan minutos para la
  meta, cuántos faltan queda en "Pendientes".
- [ ] Al menos una grabación del escenario de falsa liberación está completa.
- [ ] `sert_reglas.md` tiene fuentes citadas y la tabla de comparación.
- [ ] Existen las dos evidencias PNG y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 3, Miguel), **incluido el PDF
semanal**. En "Pedidos a otros": @Pablo, ruta e inventario de las grabaciones; @Freddy,
valores reales para `tarifa.json`; @Tyrone, observaciones a `calles_sert.yaml`.
