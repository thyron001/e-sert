---
semana: S4
persona: Pablo
sesion: 3
titulo: Integración del informe completo
horas: 3-4
modulo: informe
depende: [S4-Pablo-2, S4-Tyrone-2, S4-Freddy-3, S4-Miguel-3]
entrega: [informe/informe.md, informe/comun/, informe/referencias.bib, informe/construir_informe.py, informe/verificar_informe.py, informe/salida/informe_e-sert.pdf]
evidencias: [s3_informe-paginas.png]
---
# S4 · Sesión 3 · Pablo 🟢: Integración del informe completo

## Contexto
Lee `CLAUDE.md`, `docs/EQUIPO.md` (eres el **editor** de `proyecto/informe/`) y tu
`informe/GUIA_ESTILO.md`. Cada persona escribe **solo** su sección (`tyrone.md`,
`freddy.md`, `pablo.md`, `miguel.md`) y sus figuras en `informe/figuras/<nombre>/`. Tú
escribes las partes comunes y el armado. Haz esta sesión el **sábado 14 por la tarde**: el
plazo real es ese día a las 23:59. La unificación del domingo 15 a las 09:00 volverá a
construir el informe con las secciones ya fusionadas en `proyecto/informe/`, para la entrega
del lunes 16.

## Objetivo
Un informe único, coherente y verificable, generado por script desde las cuatro secciones y
las partes comunes, con salida en PDF.

## Pasos
1. Escribe las partes comunes en `informe/comun/`: `00_portada.md` (título, integrantes,
   materia, fecha 16 de noviembre de 2026), `01_resumen.md` (≤ 250 palabras, con las 3
   cifras principales), `02_introduccion.md` (problema de buscar parqueo en la zona SERT y
   objetivos), `03_trabajo_relacionado.md`, `90_conclusiones.md` y `91_trabajo_futuro.md`.
2. Crea `informe/referencias.bib` con lo que se cite: SUMO, TraCI, GeoLife, SHL, Random
   Forest (Breiman, 2001), *model cards* (Mitchell et al., 2019), *cruising for parking*
   (Shoup) y la ordenanza SERT que verificó Miguel. Sin referencias inventadas: si no puedes
   comprobar una, no la pongas.
3. Crea `informe/informe.md`, el maestro con el orden y marcadores
   `<!-- incluir: comun/02_introduccion.md -->`. Orden: portada, resumen, introducción,
   trabajo relacionado, arquitectura (`freddy.md`), escenario y experimentos (`tyrone.md`),
   IA (`pablo.md`), app (`miguel.md`), resultados integrados, conclusiones, trabajo futuro,
   referencias y anexos (`anexos/preguntas_profesor.md`).
4. Crea `informe/construir_informe.py` con `--fuentes {proyecto,ramas}`:
   - `proyecto` (por defecto, el que usa la unificación): lee las secciones de la carpeta
     `informe/` donde está el script;
   - `ramas` (para hoy): extrae `semanas/S4/<Nombre>/codigo/informe/` de cada rama
     `origin/<nombre>/s4` con `git archive` a una carpeta temporal. **No copies** las
     secciones ajenas a tu carpeta;
   - expande los `incluir`, numera secciones, figuras y tablas, reescribe rutas de imágenes,
     genera el índice y escribe `informe/salida/informe_e-sert.md`;
   - si hay `pandoc`, produce `informe_e-sert.pdf` (`--citeproc --toc`, motor `xelatex` o,
     si no está, `wkhtmltopdf`); si no hay, produce HTML y lo dice con claridad;
   - si falta una sección, inserta un recuadro `[SECCIÓN PENDIENTE: <Nombre>]` y sale con
     código 2 (no inventa contenido).
5. Crea `informe/verificar_informe.py`, que sale con código 1 si encuentra:
   - una sección de persona ausente o con menos de 800 palabras;
   - una imagen enlazada que no existe;
   - `TODO`, `PENDIENTE` o `MOCK` en el texto final;
   - una cita `[@clave]` que no está en `referencias.bib`;
   - la misma métrica con valores distintos en dos secciones (compara las cifras marcadas
     con `<!-- fuente: X -->` que apunten a la misma fuente).
   Imprime una tabla de palabras por sección.
6. Ejecuta `python informe/construir_informe.py --fuentes ramas` y luego el verificador.
   Las inconsistencias en secciones ajenas se piden a su dueño con la línea exacta; no las
   corrijas tú.
7. Lanza un subagente revisor sin contexto: "lee `informe/salida/informe_e-sert.md` como
   el profesor de Redes Vehiculares y lista las 10 debilidades más graves". Corrige las que
   sean de tus partes y pide el resto.
8. **Evidencia** `evidencias/s3_informe-paginas.png`: miniaturas de la portada, el índice,
   una página de resultados y una de IA, renderizadas del PDF con PyMuPDF (`fitz`).

## Dónde escribir
`semanas/S4/Pablo/codigo/informe/` (partes comunes, scripts, maestro, `salida/`) y
`evidencias/`. Nunca dentro de `tyrone.md`, `freddy.md` ni `miguel.md`.

## Hecho cuando
- [ ] `python informe/construir_informe.py --fuentes ramas` produce el PDF (o el HTML, si no
  hay `pandoc`) con las cuatro secciones.
- [ ] `python informe/verificar_informe.py` sale con código 0, o cada falla tiene su pedido
  al dueño anotado en la bitácora.
- [ ] El script funciona con `--fuentes proyecto`, que es como lo correrá la unificación.
- [ ] El resumen tiene ≤ 250 palabras y sus 3 cifras coinciden con `resumen.csv` de Tyrone.
- [ ] Existen la evidencia `s3_informe-paginas.png` y el **PDF semanal**
  (`python herramientas/resumen_pdf.py S4 Pablo`).
- [ ] Todo está en `pablo/s4` antes del sábado 14 a las 23:59.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 3, Pablo), **incluido el PDF
semanal**. En "Pedidos a otros": a cada persona, la lista exacta de correcciones a su sección
que salieron del verificador y del revisor.
