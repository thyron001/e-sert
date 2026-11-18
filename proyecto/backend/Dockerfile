# Servicio `api` de Dokploy: backend FastAPI (API, WebSocket, billetera, pagos, asistente).
# Contexto = raíz del repo:   docker build -f proyecto/backend/Dockerfile .
# Imagen ligera: SUMO va en el servicio `sim` (proyecto/sim/Dockerfile) y el visor en `visor`
# (proyecto/visor/Dockerfile). El backend le pide la simulación a `sim` con ESERT_URL_SIM.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_ROOT_USER_ACTION=ignore \
    ESERT_DB_URL=sqlite:////data/esert.db \
    ESERT_PUESTOS_CSV=/srv/datos/puestos.csv \
    ESERT_DESTINOS_CSV=/srv/datos/destinos.csv
WORKDIR /srv
COPY proyecto/backend/requirements-servidor.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && mkdir -p /data /srv/datos
COPY proyecto/sumo/parqueos/puestos.csv proyecto/sumo/demanda/destinos.csv /srv/datos/
COPY proyecto/comun ./comun
COPY proyecto/backend ./backend
RUN rm -rf backend/tests comun/tests backend/*.db
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/salud').status==200 else 1)"
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
