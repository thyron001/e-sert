---
semana: S2
persona: Pablo
sesion: 3
titulo: Evaluación con datos de Cuenca nunca vistos, incluido el tráfico lento
horas: 3-4
modulo: ia
depende: [S2-Pablo-2, S1-Miguel-3, S2-Miguel-3]
entrega: [ia/evaluar_cuenca.py, ia/reportes/evaluacion_cuenca.md, ia/reportes/metricas_cuenca.json]
evidencias: [s3_cuenca-umbral-vs-rf.png, s3_trafico-lento.png]
---
# S2 · Sesión 3 · Pablo 🟢: Evaluación con datos de Cuenca nunca vistos, incluido el tráfico lento

## Contexto
Lee `CLAUDE.md` y `docs/CONTEXTO.md` (sección IA). Esta es **la evaluación que va al
informe**: datos propios del Centro que el modelo nunca vio. Las grabaciones de S1-3 están en
`proyecto/datos/`; las nuevas de Miguel (S2-3) se hacen esta semana: léelas de
`origin/miguel/s2` sin editar (`git show origin/miguel/s2:semanas/S2/Miguel/codigo/datos/...`).
Si no hay ninguna grabación real, **no inventes resultados**: usa un mock con trazas SUMO
ruidosas marcado `# MOCK`, márcalo así en cada figura y deja la sesión como `parcial`.

## Objetivo
Medir con honestidad cómo rinden el umbral, `rf_v1` y `rf_v1` con suavizado en Cuenca,
con atención especial al caso difícil de auto en tráfico lento y a su efecto en las falsas
liberaciones.

## Pasos
1. Crea `ia/evaluar_cuenca.py`: carga solo las grabaciones de la partición de **prueba** de
   `ia/particion_cuenca.json` (las de calibración quedan fuera) y aplica exactamente el
   mismo remuestreo, ventanas y características que en entrenamiento.
   - **Prohibido** reentrenar o ajustar umbrales con estos datos. Si algo lo pide a gritos,
     anótalo como propuesta para `rf_v1.1` en S3.
2. Compara tres sistemas: `umbral`, `rf_v1` (crudo) y `rf_v1 + suavizado`:
   - macro-F1, *recall* y precisión por clase, matriz de confusión;
   - IC 95 % por *bootstrap* **por grabación** (1 000 remuestreos), no por ventana;
   - resultados separados por teléfono (iPhone frente a Android) y por persona.
3. **Tráfico lento**: subconjunto de ventanas con `modo_real = vehiculo` y velocidad media
   < 8 km/h. Reporta el *recall* de `vehiculo` y a qué clase se confunde. Es el caso donde
   el umbral falla por diseño; muestra cuánto mejora el RF.
4. **Proxy de falsas liberaciones fuera de línea**: reproduce la máquina de estados del
   contrato sobre cada grabación etiquetada con secuencia de estacionamiento (importa
   `proyecto/traci/estados.py` de Freddy si existe; si no, una copia mínima marcada
   `# MOCK`) con distancia al puesto calculada desde el punto de estacionamiento marcado.
   Cuenta cuántas veces llega a `SALIENDO` cuando la persona en realidad caminaba o estaba
   quieta. Reporta por cada 100 sesiones y por sistema.
5. Escribe `ia/reportes/evaluacion_cuenca.md` (redactado para el informe): datos usados
   (minutos por clase y por teléfono), tabla de métricas con IC, matriz de confusión, caso
   tráfico lento, proxy de falsas liberaciones, limitaciones y diferencia frente a la
   validación cruzada de S2-2 (brecha de generalización). Guarda las cifras en
   `metricas_cuenca.json`.
6. Paraleliza: un subagente hace el proxy de falsas liberaciones (paso 4) mientras tú haces
   las métricas por ventana; el *bootstrap* puede correr en segundo plano.
7. **Evidencias** (`dpi=150`):
   - `s3_cuenca-umbral-vs-rf.png`: macro-F1 y *recall* por clase de los tres sistemas, con
     barras de error del IC 95 %;
   - `s3_trafico-lento.png`: velocidad de una grabación en tráfico lento, con el modo real y
     lo que predijo cada sistema en franjas de color.

## Dónde escribir
`semanas/S2/Pablo/codigo/ia/` y `semanas/S2/Pablo/evidencias/`. No copies grabaciones de
Miguel a tu carpeta: léelas de su ubicación.

## Hecho cuando
- [ ] La evaluación usa solo la partición de prueba y lo demuestra un test (IDs disjuntos de
  calibración y entrenamiento).
- [ ] Hay macro-F1 con IC 95 % por grabación para los tres sistemas.
- [ ] El caso tráfico lento está reportado con su número de ventanas y minutos.
- [ ] El proxy de falsas liberaciones por cada 100 sesiones está calculado para los tres
  sistemas.
- [ ] `evaluacion_cuenca.md` está listo para pegar en el informe.
- [ ] Existen las dos evidencias PNG y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 3, Pablo), **incluido el PDF
semanal**. En "Pedidos a otros": @Miguel, cuántos minutos más por clase hacen falta para
que los IC sean útiles; @Freddy, qué sistema conviene usar por defecto en el controlador.
