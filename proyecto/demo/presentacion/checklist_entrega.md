# Checklist de entrega · lunes 16 de noviembre

Marcar la noche del domingo 15 (después de la unificación de las 09:00) y repasar el lunes antes de
entrar. Responsable de cada bloque entre paréntesis.

## La noche anterior (domingo)

- [ ] `git pull` de `main` con el tag `v1.0` en la laptop de la demo (Tyrone).
- [ ] Contenedor `van3twin` arriba y con dependencias: `docker exec van3twin python3 -c "import sqlalchemy, pandas, scipy"` (Tyrone).
- [ ] `kpis/externo/rf_final.plano.npz` presente en la laptop (lo ignora git; si falta, la demo lo exporta o cae al umbral) (Tyrone).
- [ ] `python demo/verificar_demo.py` sale con 0 (Tyrone).
- [ ] Ensayo completo con `python demo/demo.py --cronometro`, dentro del presupuesto de `guion.md` (todos).
- [ ] VPS: la demo en `https://demo.e-sert.tesisucuenca.com/visor/` muestra el visor nuevo tras el autodeploy de `main` (Tyrone).
- [ ] `ESERT_TOKEN_SIM` en el entorno de la laptop (no en el repo) (Tyrone).

## Equipos

- [ ] Laptop cargada al 100 % y con cargador (Tyrone).
- [ ] *Hotspot* de un teléfono probado con la laptop y el teléfono de Miguel: la WiFi de la universidad puede aislar clientes (Miguel).
- [ ] IP fija de la laptop en el *hotspot* anotada aquí: `__________` (con `--local`, el teléfono usa `http://<IP>:8000`) (Tyrone).
- [ ] Firewall de Windows: Python permitido en **red privada** (si la laptop es Windows) (Tyrone).
- [ ] Teléfono de Miguel con Expo Go instalado, la app abierta una vez y el brillo al máximo (Miguel).
- [ ] Cliente VNC (`127.0.0.1:5901`) instalado para mostrar `sumo-gui` (Tyrone).
- [ ] Adaptador HDMI o USB-C para el proyector, probado a 1920×1080 (Freddy).

## Datos de la demo

- [ ] Billetera de prueba recargada (el auto simulado del modo espejo trae su recarga; para la parte de Payphone, la cuenta de pruebas con saldo) (Miguel).
- [ ] `demo/demo.db` limpia: la demo la borra y la recrea en cada arranque; comprobar que no queda un `demo.db` abierto por otro proceso (Tyrone).
- [ ] `demo/plan_b/snapshots_demo.jsonl.gz` presente y probado con `python -m visor.servidor_prueba --snapshots demo/plan_b/snapshots_demo.jsonl.gz --puerto 8765` (Tyrone; probado el 13/11 con Chromium).

## USB de respaldo (dos copias: Tyrone y Pablo)

- [ ] `demo/presentacion/diapositivas.pdf`.
- [ ] Video de la demo de Miguel (`app/plan_b/ENLACE_VIDEO.md` apunta a él; llevar también el archivo) (Miguel).
- [ ] Informe en PDF (`proyecto/informe/`) (Pablo).
- [ ] `demo/plan_b/snapshots_demo.jsonl.gz` y el visor (`proyecto/visor/`) para reproducir sin backend.

## Antes de empezar (10 min antes)

- [ ] `python demo/demo.py` (remoto) o `--local` según la red, y esperar la tabla de arranque.
- [ ] Visor en modo presentación (`P`) en el proyector; `sumo-gui` en la ventana VNC.
- [ ] Miguel elige un candidato de la tabla y lo sigue en modo espejo; se comprueba el halo amarillo en el visor.
- [ ] Notificaciones de la laptop y de los teléfonos en silencio.
