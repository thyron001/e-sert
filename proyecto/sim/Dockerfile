# Servicio `sim` de Dokploy: SUMO 1.12 + controlador TraCI + sumo-gui en el navegador (noVNC).
# Contexto = raíz del repo:
#   docker build -f proyecto/sim/Dockerfile .                                   # servicio sim
#   docker build -f proyecto/sim/Dockerfile --target dev -t esert-sim-dev .     # contenedor van3twin
# Ubuntu 22.04 trae SUMO 1.12 y Python 3.10: lo mismo que el contenedor van3twin de la materia.

# --- base: SUMO + dependencias de la simulación y del núcleo del backend que importa el controlador
FROM ubuntu:22.04 AS base
ENV DEBIAN_FRONTEND=noninteractive SUMO_HOME=/usr/share/sumo \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_ROOT_USER_ACTION=ignore
RUN apt-get update \
 && apt-get install -y --no-install-recommends sumo sumo-tools python3 python3-pip procps ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY proyecto/backend/requirements-servidor.txt proyecto/sim/requirements-sim.txt /tmp/req/
RUN pip3 install -r /tmp/req/requirements-servidor.txt -r /tmp/req/requirements-sim.txt

# --- dev: contenedor `van3twin` del VPS (el repo se monta en /home/vanet/results/e-sert)
FROM base AS dev
# Node 20 (pruebas JS del visor, app Expo y verificación del contrato TS) y git
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg git \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/*
# Cliente de Docker (solo el binario): las e2e lanzan SUMO con `docker exec van3twin` desde dentro
# del propio contenedor, que monta /var/run/docker.sock (ver herramientas/van3twin_vps.sh).
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.3.1.tgz \
 | tar -xz -C /usr/local/bin --strip-components=1 docker/docker
COPY proyecto/sim/requirements-dev.txt /tmp/req/
RUN pip3 install -r /tmp/req/requirements-dev.txt
# IA (`proyecto/ia`): scikit-learn 1.9.1 (con el que se entrenó el RF) exige Python 3.11.
# Entorno aparte en /opt/ia311:  /opt/ia311/bin/python -m pytest ia
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
COPY proyecto/ia/requirements.txt /tmp/req/ia.txt
RUN uv venv -q -p 3.11 /opt/ia311 && VIRTUAL_ENV=/opt/ia311 uv pip install -q -r /tmp/req/ia.txt
WORKDIR /home/vanet/results
CMD ["sleep", "infinity"]

# --- final: lo que sirve Dokploy (debe ser la última etapa)
FROM base
# Pantalla virtual para ver y controlar sumo-gui en el navegador (https://sumo.tesisucuenca.com)
RUN apt-get update \
 && apt-get install -y --no-install-recommends xvfb x11vnc fluxbox novnc python3-websockify tini \
 && rm -rf /var/lib/apt/lists/*
# Misma estructura que el repo: correr_una busca la raíz subiendo hasta un CLAUDE.md.
WORKDIR /srv/e-sert/proyecto
RUN touch /srv/e-sert/CLAUDE.md
COPY proyecto/comun ./comun
COPY proyecto/backend ./backend
COPY proyecto/ia ./ia
COPY proyecto/traci ./traci
COPY proyecto/kpis ./kpis
COPY proyecto/sumo ./sumo
COPY proyecto/sim/arranque.sh ./sim/arranque.sh
RUN rm -rf backend/tests comun/tests ia/tests traci/tests kpis/tests backend/*.db
EXPOSE 8100 6080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/salud').status==200 else 1)"
# tini como PID 1: recoge los procesos huérfanos (sumo-gui al terminar el controlador), que si no
# quedan como zombis. Lo demás lo arranca arranque.sh.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash", "sim/arranque.sh"]
