---
semana: S4
persona: Miguel
sesion: 3
titulo: Sección de la app en el informe y plan B de la demo en video
horas: 3-4
modulo: informe
depende: [S4-Miguel-1, S4-Miguel-2, S4-Tyrone-1]
entrega: [informe/miguel.md, informe/figuras/miguel/, app/plan_b/guion_video.md, app/plan_b/ENLACE_VIDEO.md, app/plan_b/fotogramas/]
evidencias: [s3_plan-b-fotogramas.png]
---
# S4 · Sesión 3 · Miguel 🔴: Sección de la app en el informe y plan B de la demo en video

## Contexto
Lee `CLAUDE.md`, `informe/GUIA_ESTILO.md` de Pablo (en `origin/pablo/s4`), tu
`app/MANUAL.md` (sesión 1) y `datos/campo_final/resultados.json` (sesión 2). Pablo integra
el informe el sábado: tu sección debe estar en `miguel/s4` **antes del sábado 14 a las
18:00**, y en todo caso antes de las 23:59, que es el plazo real. La unificación final corre
el domingo 15 a las 09:00 y la exposición es el lunes 16. Si la demo en vivo falla, el plan B
es tu video.

## Objetivo
Escribir `informe/miguel.md` con resultados reales de la app y del campo, y grabar un video
de 3 a 4 min de la demo completa, enlazado y respaldado fuera del repo.

## Pasos
1. Escribe `informe/miguel.md` (1 500–2 500 palabras), con el formato de la guía de estilo:
   - **Diseño de la app:** diagrama del flujo de pantallas (Mermaid o figura) y capturas de
     `app/capturas/` copiadas a `informe/figuras/miguel/`.
   - **Sensores:** configuración real de `expo-location` (precisión, `timeInterval: 1000`,
     `distanceInterval`) y `expo-sensors`; la limitación del segundo plano en iOS y cómo se
     resolvió para la demo.
   - **Sesión y cierre automático:** cómo la app consume `/eventos` y la máquina de estados.
   - **Billetera y Payphone en modo de prueba:** retención y débito, flujo de recarga,
     manejo de credenciales (`.env`, nunca en el repo) y por qué los autos simulados nunca
     llaman a Payphone.
   - **Reglas SERT verificadas:** tarifa vigente y tiempo máximo, con su fuente.
   - **Grabaciones reales:** minutos y ventanas por clase y teléfono en `proyecto/datos/`.
   - **Prueba de campo final:** tabla con las cinco métricas de `resultados.json`, una figura
     del mapa de trazas y lo que salió mal.
   - **Usabilidad y limitaciones.**
   Cada cifra con `<!-- fuente: ... -->`.
2. Escribe `app/plan_b/guion_video.md`: toma por toma, con duración y lo que se dice:
   1. problema y app (20 s);
   2. `demo.py` arrancando: sumo-gui y visor (30 s);
   3. un auto con app guiado al puesto frente a uno buscando a ciegas (40 s);
   4. teléfono real: recarga de prueba, confirmar puesto, alejarse a pie **sin** que se
      libere el puesto (60 s);
   5. volver, salir en auto, cierre automático y recibo (40 s);
   6. KPIs en vivo y cierre (30 s).
3. Graba con la demo de Tyrone (extraída de `origin/tyrone/s4` con `git archive`, sin
   editarla): pantalla de la laptop con OBS o la grabadora del sistema y el teléfono con la
   grabación de pantalla de iOS o Android. Combina con `ffmpeg` (por ejemplo,
   `-filter_complex hstack` con el teléfono escalado a la altura de la laptop), agrega
   subtítulos en español (`.srt`) y exporta MP4 H.264 1080p de menos de 200 MB.
4. **El video no va en git.** Súbelo a la carpeta compartida del grupo (OneDrive o Drive de
   la universidad) y escribe en `app/plan_b/ENLACE_VIDEO.md` el enlace, la duración, el
   tamaño y el SHA-256. Deja copia en las laptops de Tyrone y la tuya y en una memoria USB.
5. Extrae un fotograma por toma a `app/plan_b/fotogramas/toma_<n>.png`
   (`ffmpeg -ss <t> -i video.mp4 -frames:v 1`).
6. Pide a un subagente revisor sin contexto: "lee `informe/miguel.md` y el guion; marca
   cifras sin fuente y afirmaciones que el video no muestre". Corrige.
7. **Evidencia** `evidencias/s3_plan-b-fotogramas.png`: montaje de los 6 fotogramas en orden,
   con el número y el título de cada toma.

## Dónde escribir
`semanas/S4/Miguel/codigo/informe/miguel.md`, `semanas/S4/Miguel/codigo/informe/figuras/miguel/`,
`semanas/S4/Miguel/codigo/app/plan_b/` y `evidencias/`. No escribas en `informe/informe.md`
ni en las secciones de los demás.

## Hecho cuando
- [ ] `informe/miguel.md` existe, sin `TODO` ni `MOCK`, con todas sus figuras enlazadas.
- [ ] El video dura entre 3 y 4 min, cubre las 6 tomas y está subido, con enlace y SHA-256
  en `ENLACE_VIDEO.md`.
- [ ] Ningún archivo de video está en el repo (`git ls-files "*.mp4"` vacío).
- [ ] Existen la evidencia `s3_plan-b-fotogramas.png` y el **PDF semanal**
  (`python herramientas/resumen_pdf.py S4 Miguel`).
- [ ] Todo está en `miguel/s4` antes del sábado 14 a las 23:59.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 3, Miguel), **incluido el PDF
semanal**. En "Pedidos a otros": @Tyrone, enlace del video para el plan B de la
presentación; @Pablo, tu sección está lista y en qué commit.
