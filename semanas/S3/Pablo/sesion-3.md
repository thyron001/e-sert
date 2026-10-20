---
semana: S3
persona: Pablo
sesion: 3
titulo: Borrador de la sección de IA del informe
horas: 3-4
modulo: informe
depende: [S3-Pablo-1, S3-Pablo-2, S3-Tyrone-2]
entrega: [informe/pablo.md, informe/figuras/ia/, informe/referencias_ia.bib, informe/verificar_cifras.py]
evidencias: [s3_informe-ia-figuras.png]
---
# S3 · Sesión 3 · Pablo 🟢: Borrador de la sección de IA del informe

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (la IA es **la parte evaluable**) y tus bitácoras de S1 a S3.
Eres el editor del informe, pero aquí escribes **solo tu sección**: `proyecto/informe/pablo.md`,
que en esta semana vive en `semanas/S3/Pablo/codigo/informe/pablo.md`. Las cifras del sistema
(falsas liberaciones con umbral y rf en la simulación completa) son de Tyrone (S3-2) y aún no
están en `proyecto/`: léelas sin editar de
`origin/tyrone/s3:semanas/S3/Tyrone/codigo/kpis/resultados/hallazgos.md` y `tabla_kpis.md`. Si no
existen, deja marcadores visibles `[PENDIENTE: cifra de Tyrone S3-2]`, nunca números inventados.

## Objetivo
Un borrador completo y verificable de la sección de IA, de 2 500 a 3 500 palabras, con figuras,
tablas y referencias, listo para revisión en S4.

## Pasos
1. Estructura de `informe/pablo.md`:
   1. **Problema:** por qué un clasificador de movimiento y qué es una falsa liberación.
   2. **Datos:** GeoLife (usuarios, horas, remuestreo a 1 Hz y derivación de la clase `quieto`),
      SUMO (semillas, ruido AR(1) con σ y ρ, casos de tráfico lento) y Cuenca (grabaciones,
      teléfonos, protocolo y horas). Tabla de clases por fuente.
   3. **Preprocesamiento y características:** ventanas de 30 s con paso de 5 s y la lista de
      características con su fórmula.
   4. **Modelos:** línea base por umbral (8 y 0,5 km/h) y Random Forest con los hiperparámetros
      de `rf_v1.meta.json`; validación con `GroupKFold` por usuario y por qué.
   5. **Evaluación:** macro-F1, recall por clase y matriz de confusión; generalización a Cuenca y
      el caso de auto en tráfico lento.
   6. **Suavizado temporal y falsas liberaciones:** la tabla de las 12 combinaciones y el k elegido.
   7. **Servicio de inferencia:** latencia p95, lote y *fallback*.
   8. **Efecto en el sistema:** falsas /100 y retardo de cierre con IC 95 % por penetración (Tyrone).
   9. **Limitaciones y trabajo futuro:** sin acelerómetro (SHL como opción), segundo plano en
      iPhone, tamaño del conjunto de Cuenca.
2. **Trazabilidad:** cada cifra lleva al lado un comentario `<!-- fuente: ia/reportes/suavizado_k.csv -->`
   con el archivo del que sale. Crea `informe/verificar_cifras.py`, que lee esos comentarios,
   abre cada fuente y reporta las cifras que no encuentra.
3. **Figuras** en `informe/figuras/ia/` (PNG a 300 dpi y PDF): matriz de confusión rf en Cuenca,
   importancia de características, recall por contexto (S3-2), suavizado vs falsas liberaciones
   (S3-2) y latencia (S3-1). Numéralas y ponles pie de figura en el texto; no copies figuras de
   otros, enlázalas desde `proyecto/kpis/figuras/` con ruta relativa.
4. **Referencias** en `informe/referencias_ia.bib` (BibTeX): GeoLife (Zheng et al.), Random
   Forest (Breiman, 2001), scikit-learn (Pedregosa et al., 2011), SUMO (Lopez et al., 2018) y SHL
   (Gjoreski et al., 2018). Verifica cada entrada (DOI o URL) antes de citarla.
5. **Agentes en paralelo:** un subagente regenera las figuras a 300 dpi; otro arma y verifica el
   `.bib`; tú escribes el texto. Al final, un subagente **auditor de cifras** sin contexto ejecuta
   `verificar_cifras.py` y compara cada número del texto con su fuente.
6. Renderiza para revisar: si `pandoc` está instalado,
   `pandoc informe/pablo.md --citeproc --bibliography informe/referencias_ia.bib -o pablo.html`
   (el HTML no se versiona). Comprueba que no haya imágenes rotas.
7. Al final del archivo, una lista **"Preguntas abiertas para S4"** (qué falta medir o confirmar).
8. **Evidencia** `evidencias/s3_informe-ia-figuras.png`: montaje con matplotlib de las figuras de
   la sección en una rejilla, con su número y pie corto.

## Dónde escribir
Solo en `semanas/S3/Pablo/codigo/informe/` y `evidencias/`. No toques las secciones de los demás.

## Hecho cuando
- [ ] `pablo.md` tiene las 9 subsecciones y entre 2 500 y 3 500 palabras (`wc -w`).
- [ ] `verificar_cifras.py` no reporta cifras huérfanas (los `[PENDIENTE]` se listan aparte).
- [ ] Todas las figuras citadas existen y el render no tiene imágenes rotas.
- [ ] `referencias_ia.bib` tiene al menos 5 entradas verificadas.
- [ ] Existen `s3_informe-ia-figuras.png` y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 3, Pablo), **incluido el PDF
semanal**. En "Pedidos a otros": @Tyrone, confirma las cifras de `hallazgos.md` que cito;
@Freddy, @Miguel, sus secciones deben seguir el mismo formato de trazabilidad.
