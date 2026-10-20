# e-sert · Parqueo SERT inteligente

Proyecto de **Redes Vehiculares** (Universidad de Cuenca). Es una app que detecta la llegada
y la salida reales del auto en la zona SERT del Centro Histórico, construye un mapa de
ocupación en vivo, guía al puesto libre más cercano y cobra solo el tiempo real. Se evalúa
con **SUMO + TraCI** y con un **clasificador de movimiento (Random Forest)**.

🌐 Roadmap del equipo: **https://e-sert.tesisucuenca.com**

| | Persona | Rol |
|---|---|---|
| 🔵 | Tyrone | Escenario SUMO, experimentos, KPIs y visor web |
| 🍅 | Freddy | Controlador TraCI, emulador GPS, guiado y backend |
| 🟢 | Pablo | IA: dataset, clasificador e inferencia |
| 🔴 | Miguel | App Expo: sensores, sesión, billetera y Payphone |

## Cómo trabajar una sesión

1. Clona el repo y ábrelo en Claude Code.
2. Escribe, por ejemplo: **`Soy Pablo. Ejecuta la primera sesión de esta semana.`**
3. Claude lee `CLAUDE.md`, abre tu rama (`pablo/s1`) y ejecuta el prompt de
   `semanas/S1/Pablo/sesion-1.md`. Trabaja con agentes y en bucle hasta cumplir los criterios
   de "hecho". Al final cierra: escribe la bitácora, las evidencias PNG, el PDF explicativo,
   `estado.json`, el commit y el push.
4. **Plazo: sábado a las 23:59.** El domingo a las 09:00, la unificación automática fusiona
   todo en `proyecto/` y en `main`.

## Estructura

```
proyecto/      código unificado (un módulo por dueño, ver docs/EQUIPO.md)
semanas/SN/    trabajo de cada semana
  <Nombre>/    sesion-1..3.md (prompts), codigo/, evidencias/, explicaciones/, estado.json
  unificacion.md
bitacoras/     una bitácora por persona, más la de las unificaciones
docs/          CONTEXTO, PLAN, EQUIPO y CONTRATO
herramientas/  generadores de PDF (semanal y explicativo por sesión)
roadmap/       sitio Flask del roadmap (Dockerfile para Dokploy)
```

## Correr el roadmap en local

```bash
pip install -r roadmap/requirements.txt
python roadmap/app.py
```

Luego abre http://localhost:5050. Con `ESERT_HOY=2026-10-28` puedes simular otra fecha.
