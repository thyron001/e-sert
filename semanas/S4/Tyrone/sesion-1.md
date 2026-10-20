---
semana: S4
persona: Tyrone
sesion: 1
titulo: Demo en un comando (backend, sumo-gui y visor)
horas: 3-4
modulo: demo
depende: [S3-Tyrone-3, S3-Freddy-3]
entrega: [demo/demo.py, demo/demo.ps1, demo/demo.sh, demo/config_demo.yaml, demo/verificar_demo.py, demo/README.md]
evidencias: [s1_demo-un-comando.png]
---
# S4 · Sesión 1 · Tyrone 🔵: Demo en un comando (backend, sumo-gui y visor)

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md`, `docs/CONTRATO.md` (secciones 4 y 6) y `docs/PLAN.md`
(fila S4). Es la última semana: el **plazo real es el sábado 14 de noviembre a las 23:59**, la
unificación final corre el domingo 15 a las 09:00 y la entrega es el lunes 16. En la
exposición no hay tiempo para abrir cuatro terminales: la demo debe arrancar con **un solo
comando** y cerrarse limpia con Ctrl+C. Primero copia tus módulos (`sumo/`, `kpis/`,
`visor/`) desde `proyecto/` a `semanas/S4/Tyrone/codigo/` según la regla de copia;
`demo/` es nuevo. El backend y el controlador son de Freddy: se **leen** desde `proyecto/`.

## Objetivo
Crear `demo/demo.py`, que levanta en orden el backend FastAPI, el controlador TraCI con
`sumo-gui` y el visor Leaflet, comprueba que cada pieza responde y lo apaga todo junto.

## Pasos
1. Lanza un subagente `Explore` que resuma, sin editar: cómo se arranca el backend
   (`proyecto/backend/`, objeto `app` de FastAPI y su módulo), los flags del controlador
   (`proyecto/traci/`: `--cfg`, `--gui`, URL del backend, penetración, clasificador) y cómo
   recibe el visor la URL del WebSocket. Ojo: la carpeta `traci/` se llama igual que la
   librería `traci` de SUMO; respeta el `cwd`/`PYTHONPATH` que documente Freddy.
2. Crea `demo/config_demo.yaml` con rutas **relativas a la raíz del repo** (búscala subiendo
   desde `Path(__file__)` hasta encontrar `CLAUDE.md`), de modo que funcione igual en
   `semanas/S4/Tyrone/codigo/demo/` y en `proyecto/demo/`:
   ```yaml
   rutas: {backend: proyecto/backend, traci: proyecto/traci, sumo: proyecto/sumo, visor: proyecto/visor}
   sumocfg: sumo/centro_base.sumocfg
   puertos: {backend: 8000, visor: 8080, traci: 8813}
   escenario: {penetracion: 0.5, clasificador: rf, semilla: 1, hasta_s: 3600, delay_ms: 100}
   db: demo/demo.db          # se borra y recrea en cada arranque
   ```
   Durante la semana permite `--ruta visor=semanas/S4/Tyrone/codigo/visor` para usar tu copia.
3. Crea `demo/demo.py` (`argparse`, `subprocess.Popen`, `pathlib`, sin rutas absolutas):
   - **Prerrequisitos:** `SUMO_HOME` definido, `sumo-gui` en el `PATH`, Python ≥ 3.11,
     puertos libres (`socket.bind`). Si algo falla, mensaje en español con la solución.
   - **Backend:** `uvicorn <modulo>:app --host 0.0.0.0 --port 8000` con la base SQLite de la
     demo recién creada. Espera *healthcheck* sondeando `GET /api/v1/puestos` cada 0,5 s
     (máximo 20 s).
   - **Controlador:** con `--gui`, el `sumocfg`, la penetración y la URL del backend.
     Espera a que el WS `/ws/estado` emita el primer `snapshot` (máximo 30 s).
   - **Visor:** `python -m http.server 8080` sobre la carpeta del visor y
     `webbrowser.open("http://localhost:8080/?ws=ws://localhost:8000/ws/estado")`.
   - Imprime la URL que debe usar el teléfono espejo de Miguel en Expo Go (la del VPS en
     `--remoto`; la **IP de la LAN** solo en `--local`), los primeros candidatos de
     `GET /api/v1/espejo/candidatos` y una tabla con el tiempo de arranque de cada componente.
   - Logs de cada proceso en `demo/logs/<AAAAMMDD-HHMMSS>/<componente>.log` (en `.gitignore`).
   - **Apagado:** Ctrl+C o el cierre de `sumo-gui` termina todo en orden inverso. En Windows
     usa `CREATE_NEW_PROCESS_GROUP` y `CTRL_BREAK_EVENT`; en Linux, `start_new_session=True`
     y `os.killpg`. Tras 5 s, `kill()` a lo que siga vivo.
   - Flags: `--sin-gui`, `--penetracion`, `--semilla`, `--sin-navegador`, `--cronometro`
     (escribe `logs/.../tiempos.json`; lo usarás en la sesión 3).
4. Crea los envoltorios `demo/demo.ps1` y `demo/demo.sh`, que activan el `.venv` del backend
   si existe y llaman a `demo.py` pasando los argumentos.
5. Crea `demo/verificar_demo.py`, la prueba de humo sin GUI que también usará la unificación:
   arranca `demo.py --sin-gui --sin-navegador`, se conecta al WS 120 s y comprueba:
   - al menos 100 `snapshot` válidos contra `proyecto/comun/esquemas.py`, y nunca más de 1
     por segundo de simulación;
   - `GET /puestos` coincide en número con `proyecto/sumo/parqueos/puestos.csv`;
   - al menos una sesión pasa a `CERRADA` y la billetera cumple `saldo = Σrecargas − Σdébitos`;
   - después del apagado, los puertos 8000 y 8080 quedan libres y no quedan procesos `sumo`.
   Sale con código 0 o 1 y escribe `verificacion.json`.
6. Escribe `demo/README.md`: prerrequisitos, el comando, qué se ve, IP para teléfonos,
   firewall de Windows (permitir Python en red privada) y una tabla de errores frecuentes.
7. **Evidencia** `evidencias/s1_demo-un-comando.png` (matplotlib, 3 paneles): captura de
   `sumo-gui` (`PIL.ImageGrab` tras 60 s), captura del visor (Playwright *headless* si está;
   si no, pide la captura al usuario) y barras con el tiempo de arranque por componente.

## VPS (demo en línea)
Lee `docs/DESPLIEGUE.md`. La demo tiene **dos modos**:
- `--remoto` (el principal): la laptop corre SUMO, `sumo-gui` y el controlador, y publica en `https://demo.e-sert.tesisucuenca.com` con `ESERT_TOKEN_SIM`; abre `https://demo.e-sert.tesisucuenca.com/visor` en el navegador. El teléfono espejo (que sigue a un auto simulado; no envía GPS) usa la misma URL.
- `--local` (plan B, sin internet): backend `uvicorn` local + visor local, como ya estaba.
Al arrancar en `--remoto`, comprueba `/salud` y, si falla en 5 s, ofrece pasar a `--local` automáticamente.

## Dónde escribir
`semanas/S4/Tyrone/codigo/demo/` (y tus copias de `sumo/`, `kpis/`, `visor/`) y
`semanas/S4/Tyrone/evidencias/`. No edites `proyecto/backend/` ni `proyecto/traci/`.

## Hecho cuando
- [ ] Los dos modos arrancan con un comando, y el modo remoto cae al local si el VPS no responde.
- [ ] `python demo/demo.py` arranca las tres piezas en menos de 60 s y el visor muestra autos
  y puestos en verde/rojo.
- [ ] Ctrl+C deja libres los puertos 8000 y 8080 y sin procesos `sumo-gui` vivos.
- [ ] `python demo/verificar_demo.py` sale con código 0 y deja `verificacion.json`.
- [ ] Funciona en PowerShell (Windows); el camino Linux está documentado en el README.
- [ ] Existe la evidencia `s1_demo-un-comando.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 1, Tyrone). En "Pedidos a
otros": @Freddy, cualquier flag del controlador o del backend que tuviste que suponer;
@Miguel, la URL que debe usar el modo espejo de la app en la demo (VPS y, en plan B, IP y puerto locales).
