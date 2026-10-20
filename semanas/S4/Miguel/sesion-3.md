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
`app/MANUAL.md` (sesión 1), y `app/ensayo/resultados_ensayo.json`, `app/ensayo/guion_demo.md` y
`app/plan_b/crudo/LEEME.md` (sesión 2). Todo es simulado: no hubo pruebas de campo. Pablo integra
el informe el sábado: tu sección debe estar en `miguel/s4` **antes del sábado 14 a las
18:00**, y en todo caso antes de las 23:59, que es el plazo real. La unificación final corre
el domingo 15 a las 09:00 y la exposición es el lunes 16. Si la demo en vivo falla, el plan B
es tu video.

## Objetivo
Escribir `informe/miguel.md` con resultados reales de la app y del ensayo de la demo, y dejar
listo un video de 3 a 4 min de la demo completa, editado a partir de la grabación cruda de S4-2,
enlazado y respaldado fuera del repo.

## Pasos
1. Escribe `informe/miguel.md` (1 500–2 500 palabras), con el formato de la guía de estilo:
   - **Diseño de la app:** diagrama del flujo de pantallas (Mermaid o figura) y capturas de
     `app/capturas/` copiadas a `informe/figuras/miguel/`.
   - **Modo espejo:** por qué el teléfono sigue a un conductor simulado en vez de enviar su GPS;
     `GET /espejo/candidatos`, `WS /ws/espejo/{veh_id}`, reconexión exponencial y notificaciones
     locales; la limitación del segundo plano en iOS y cómo se resolvió para la demo.
   - **Sesión y cierre automático:** cómo la app sigue la máquina de estados por el espejo y
     cómo la simulación dispara el cierre y el recibo.
   - **Billetera y Payphone en modo de prueba:** retención y débito, flujo de recarga,
     manejo de credenciales (`.env`, nunca en el repo) y por qué los autos simulados nunca
     llaman a Payphone.
   - **Reglas SERT verificadas:** tarifa vigente y tiempo máximo, con su fuente.
   - **Grabador de sensores:** configuración de `expo-location` y `expo-sensors`, y las
     grabaciones caseras opcionales de `proyecto/datos/` (minutos por clase), solo si existen.
   - **Ensayo de la demo:** tabla con las latencias evento → pantalla (VPS y local), las
     reconexiones y el tiempo de recuperación de `resultados_ensayo.json`, y lo que salió mal.
   - **Usabilidad y limitaciones.**
   Cada cifra con `<!-- fuente: ... -->`.
2. Escribe `app/plan_b/guion_video.md`: toma por toma, con duración y lo que se dice:
   1. problema y app (20 s);
   2. `demo.py` arrancando: sumo-gui y visor (30 s);
   3. un auto con app guiado al puesto frente a uno buscando a ciegas (40 s);
   4. teléfono espejo: elige un auto simulado, guiado al puesto, ESTACIONADO y el conductor
      a pie (A_PIE) **sin** que se libere el puesto en el visor (60 s);
   5. REGRESANDO, SALIENDO, cierre automático disparado por la simulación y recibo (40 s);
   6. KPIs en vivo y cierre (30 s).
3. Parte de la grabación cruda combinada de S4-2 (`app/plan_b/crudo/`); si alguna toma
   salió mal, regrábala con la demo de Tyrone (extraída de `origin/tyrone/s4` con
   `git archive`, sin editarla): laptop con OBS y teléfono espejo con la grabación de pantalla
   de iOS o Android, combinadas con `ffmpeg` (`-filter_complex hstack`). Corta según el guion,
   agrega subtítulos en español (`.srt`) y exporta MP4 H.264 1080p de menos de 200 MB.
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
