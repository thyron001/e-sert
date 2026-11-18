#!/usr/bin/env bash
# Crea (o recrea) en el VPS el contenedor `van3twin`: SUMO 1.12 + Python 3.10 + Node 20, con la
# carpeta results/ montada igual que en el stack van3twin-docker de la materia. Así funcionan sin
# cambios `docker exec van3twin ...`, demo.py, las e2e y los experimentos. No trae sumo-gui.
#   herramientas/van3twin_vps.sh            # construye la imagen y recrea el contenedor
# Límites: 1,5 GiB de RAM y 0,9 CPU, para no ahogar las otras apps del VPS.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS="$(dirname "$RAIZ")"
[ "$(basename "$RESULTS")" = "results" ] || { echo "El repo debe estar en .../results/e-sert (está en $RAIZ)"; exit 1; }
docker build -f "$RAIZ/proyecto/backend/Dockerfile" --target dev -t esert-sim-dev "$RAIZ"
docker rm -f van3twin >/dev/null 2>&1 || true
# docker.sock + host.docker.internal=127.0.0.1: las e2e corren dentro del contenedor, levantan el
# backend ahí mismo y lanzan SUMO con `docker exec van3twin` (se llama a sí mismo).
docker run -d --name van3twin --restart unless-stopped --memory 1536m --cpus 0.9 \
  -v "$RESULTS:/home/vanet/results" -v /var/run/docker.sock:/var/run/docker.sock \
  --add-host host.docker.internal:127.0.0.1 esert-sim-dev >/dev/null
docker exec van3twin bash -lc 'sumo --version | head -1; python3 --version; /opt/ia311/bin/python --version; node --version; docker exec van3twin true && echo "docker exec ok"'
