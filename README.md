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

## Dónde clonar el repo (los cuatro)

Todos usamos el SUMO del contenedor `van3twin`. El contenedor solo ve la carpeta `results/`
de `van3twin-docker`, así que el repo se clona **ahí, en la misma computadora que tiene el
contenedor**. Desde la terminal (Ubuntu/WSL en Windows), con el contenedor encendido:

```bash
cd "$(docker inspect van3twin --format '{{range .Mounts}}{{if eq .Destination "/home/vanet/results"}}{{.Source}}{{end}}{{end}}')"
git clone https://github.com/thyron001/e-sert.git
cd e-sert
```

El primer comando entra en la carpeta `results/` que usa tu contenedor. Si falla, entra a
mano: `cd ~/van3twin-docker/results` (o donde hayas clonado `van3twin-docker`). Para comprobar
que el contenedor ve el repo:

```bash
docker exec van3twin ls /home/vanet/results/e-sert
```

Claude Code se abre en esa carpeta (`results/e-sert`). Claude corre `git` y edita en la
computadora, y ejecuta SUMO dentro del contenedor con `docker exec` (ver `CLAUDE.md`).

## Cómo se trabaja ahora

Desde el 2026-11-17 el proyecto lo continúa una sola persona (Tyrone), en una sola
computadora y solo en la rama `main`. Las reglas están en `CLAUDE.md`. Las carpetas
`semanas/`, las bitácoras de Freddy, Pablo y Miguel, `docs/EQUIPO.md` y `docs/PLAN.md` son la
historia del trabajo en equipo (S1–S4).

## Estructura

```
proyecto/      código del proyecto (se edita aquí, en main)
semanas/SN/    historia: trabajo semanal del equipo en S1–S4
bitacoras/     bitácoras (la activa es tyrone.md)
docs/          CONTEXTO, CONTRATO (referencia de la API), DESPLIEGUE; PLAN y EQUIPO históricos
herramientas/  generadores de PDF y scripts de apoyo
roadmap/       sitio Flask del roadmap (Dockerfile en la raíz, para Dokploy)
```

## Correr el roadmap en local

```bash
pip install -r roadmap/requirements.txt
python roadmap/app.py
```

Luego abre http://localhost:5050. Con `ESERT_HOY=2026-10-28` puedes simular otra fecha.
