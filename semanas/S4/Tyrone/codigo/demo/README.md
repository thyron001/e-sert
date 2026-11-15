# Demo de e-sert en un comando

Levanta en orden el **backend** (FastAPI de Freddy), el **controlador TraCI con sumo-gui** (dentro
del contenedor `van3twin`) y el **visor Leaflet**; comprueba que cada pieza responde y, con
**Ctrl+C** o al **cerrar sumo-gui**, lo apaga todo en orden inverso, también lo que corre dentro
del contenedor.

## Prerrequisitos

| Qué | Cómo comprobarlo |
|---|---|
| Repo clonado dentro de `van3twin-docker/results/e-sert` | `git rev-parse --show-toplevel` termina en `/results/e-sert` |
| Contenedor `van3twin` corriendo, con `sumo-gui` | `docker ps` lo lista; si no: `docker compose up -d van3twin` en `van3twin-docker/` |
| Dependencias de Python en el contenedor (una vez; se pierden si se recrea) | `docker exec van3twin pip3 install --user -r <ruta>/backend/requirements.txt pandas scipy` |
| Python 3.11 o más en la computadora, con el entorno de la demo | ver "Instalación" |
| Puertos 8000 (backend) y 8088 (visor) libres | la demo lo comprueba; el 8080 no se usa (lo publica el contenedor) |
| Cliente VNC para ver sumo-gui | `127.0.0.1:5901` |

### Instalación (una vez)

Linux/macOS:

```bash
python3 -m venv demo/.venv
demo/.venv/bin/pip install -r demo/requirements.txt
```

Windows (PowerShell):

```powershell
py -3.11 -m venv demo\.venv
demo\.venv\Scripts\pip install -r demo\requirements.txt
```

## El comando

| Sistema | Remoto (principal) | Local (plan B, sin internet) |
|---|---|---|
| Linux/macOS | `./demo/demo.sh` | `./demo/demo.sh --local` |
| Windows | `.\demo\demo.ps1` | `.\demo\demo.ps1 --local` |

Se ejecuta desde la carpeta que contiene `demo/` (`proyecto/` tras la unificación).

- **Remoto (`--remoto`, por defecto):** la laptop corre SUMO, sumo-gui y el controlador y publica
  en `https://demo.e-sert.tesisucuenca.com` con `ESERT_TOKEN_SIM` (variable de entorno; solo la
  tiene Tyrone). Abre `https://demo.e-sert.tesisucuenca.com/visor/`. Si `/salud` no responde en 5 s,
  **cae solo a `--local`**. También cae a local si falta `ESERT_TOKEN_SIM` (el VPS rechazaría los snapshots).
- **Local (`--local`):** backend `uvicorn` en el puerto 8000 con una base `demo/demo.db` nueva
  (se borra en cada arranque) y visor en `http://localhost:8088/?ws=ws://127.0.0.1:8000/ws/estado`.

Opciones: `--sin-gui`, `--sin-navegador`, `--penetracion 0.8`, `--semilla 2`,
`--clasificador umbral`, `--ritmo 5` (veces el tiempo real; 1 = en vivo), `--hasta 1800`,
`--cronometro` (escribe `logs/<sello>/tiempos.json`), `--ruta visor=semanas/S4/Tyrone/codigo/visor`
(durante la semana, para usar las copias de trabajo).

**Escenario por defecto** (`config_demo.yaml`): 50 % de usuarios con app, `rf_final`, **semilla 2**
y **`ritmo: 2`**.
- Con la semilla 2, la primera sesión se cierra en t = 1 014 s simulados, la más temprana de las
  5 semillas.
- A 2× hay cierres con recibo a los ~8,5 min de lanzar la demo. Por eso conviene lanzarla al
  empezar la exposición.
- Sin GUI, el controlador usa libsumo: ~9× el tiempo real, frente a ~7× con TraCI.

Prueba de humo sin GUI (también la usa la unificación):

```bash
demo/.venv/bin/python demo/verificar_demo.py      # sale con 0 o 1 y escribe demo/verificacion.json
```

## Qué se ve

1. Una tabla con el tiempo de arranque de cada componente, la URL del visor, la URL para el
   teléfono espejo y los primeros candidatos (`GET /api/v1/espejo/candidatos`).
2. **sumo-gui** (VNC `127.0.0.1:5901`) con el centro histórico y los autos.
3. **El visor**: puestos en verde (con lugar) o rojo (llenos), autos coloreados por estado
   (borde negro = con app), peatones, el **vehículo espejo** con halo amarillo, y el panel de KPIs
   con la comparación contra la búsqueda a ciegas. Teclas: `P` presentación, `E` seguir al espejo,
   `T` recorrido, `H` ayuda, `D` tiempos por cuadro.
4. Ctrl+C (o cerrar sumo-gui): "apagando en orden inverso…" y los puertos quedan libres.

## IP para los teléfonos

- **Remoto:** los teléfonos usan `https://demo.e-sert.tesisucuenca.com` (no importa la red).
- **Local:** la demo imprime `http://<IP-de-la-LAN>:8000`. El teléfono debe estar en la **misma
  red**; la WiFi de la universidad suele aislar clientes, así que conviene el *hotspot* de un
  teléfono. El visor también se ve desde otro equipo en `http://<IP>:8000/visor/`.

## Firewall de Windows

La primera vez, Windows pregunta si Python puede usar la red: marca **Redes privadas** y permite.
Si ya se denegó: *Seguridad de Windows → Firewall → Permitir una aplicación* → `python.exe` →
casilla **Privada**. Sin esto, el contenedor (y los teléfonos) no llegan al backend en el 8000.

## RF en el contenedor

El contenedor tiene Python 3.10, sin la versión de scikit-learn con la que Pablo entrenó
`rf_final`. Por eso el controlador usa el mismo bosque exportado a arrays de numpy
(`kpis/externo/rf_final.plano.npz`, ignorado por git). Si falta, la demo intenta exportarlo con
`python -m kpis.modelo_plano exportar` (necesita scikit-learn en la computadora); si no puede,
avisa y usa el clasificador de umbral.

## Errores frecuentes

| Mensaje | Causa | Solución |
|---|---|---|
| `El contenedor van3twin no está corriendo` | el stack está apagado | `docker compose up -d van3twin` |
| `El repo está … fuera de van3twin-docker/results/` | el contenedor no ve los archivos | clonar dentro de `results/` |
| `El puerto 8000 está ocupado` | otra demo o servidor | cerrar esa terminal o `ss -ltnp \| grep 8000` (Windows: `netstat -ano \| findstr 8000`) |
| `No llegó ningún snapshot … en 30 s` | el contenedor no llega al backend | firewall de Windows; ver `logs/<sello>/controlador.log` |
| `ModuleNotFoundError: sqlalchemy/pandas` en `controlador.log` | contenedor recreado | reinstalar dependencias (tabla de prerrequisitos) |
| `401` en el log del controlador (remoto) | falta `ESERT_TOKEN_SIM` | definir la variable (solo Tyrone) o usar `--local` |
| `⚠ sin RF exportado` | falta `kpis/externo/` | ver "RF en el contenedor" |
| El visor dice "sin conexión" | backend caído | revisa `logs/<sello>/backend.log`; el visor reconecta solo (1, 2, 4… 30 s) |

## Archivos

| Archivo | Qué hace |
|---|---|
| `demo.py` | arranque, comprobaciones, tabla de tiempos y apagado ordenado |
| `config_demo.yaml` | rutas (relativas a la raíz del repo), puertos, escenario y VPS |
| `demo.sh`, `demo.ps1` | envoltorios que activan el `.venv` y pasan los argumentos |
| `verificar_demo.py` | prueba de humo sin GUI → `verificacion.json` |
| `logs/<sello>/` | un log por componente, `demo.log`, `tiempos.json` y la captura de sumo-gui (ignorado por git) |
