# Imagen del backend e-sert (app `esert-demo` en Dokploy). Contexto = raíz del repo:
#   docker build -f proyecto/backend/Dockerfile .
# Para probar la copia semanal antes de la unificación:
#   docker build -f semanas/S2/Freddy/codigo/backend/Dockerfile --build-arg ORIGEN=semanas/S2/Freddy/codigo .
# `proyecto/ia`, `proyecto/visor` y `puestos.csv` siempre salen de `proyecto/`.

# --- Etapa 1: junta solo los archivos necesarios (proyecto/visor puede no existir todavía)
FROM python:3.11-slim AS fuentes
ARG ORIGEN=proyecto
COPY proyecto/ /repo/proyecto/
COPY ${ORIGEN}/backend/ /repo/origen/backend/
COPY ${ORIGEN}/comun/ /repo/origen/comun/
RUN set -eu; mkdir -p /srv/ia/modelos /srv/visor /srv/datos; \
    cp -r /repo/origen/backend /srv/backend; \
    rm -rf /srv/backend/.venv /srv/backend/tests /srv/backend/graficas /srv/backend/*.db; \
    cp -r /repo/origen/comun /srv/comun; rm -rf /srv/comun/tests; \
    for f in __init__.py inferencia.py ventanas.py caracteristicas.py umbral.py; do \
      [ -f /repo/proyecto/ia/$f ] && cp /repo/proyecto/ia/$f /srv/ia/; done; \
    [ -d /repo/proyecto/ia/modelos ] && cp -r /repo/proyecto/ia/modelos/. /srv/ia/modelos/ || true; \
    [ -d /repo/proyecto/visor ] && cp -r /repo/proyecto/visor/. /srv/visor/ || true; \
    cp /repo/proyecto/sumo/parqueos/puestos.csv /srv/datos/puestos.csv; \
    cp /repo/proyecto/sumo/demanda/destinos.csv /srv/datos/destinos.csv

# --- Etapa 2: imagen final
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ESERT_DB_URL=sqlite:////data/esert.db \
    ESERT_PUESTOS_CSV=/srv/datos/puestos.csv \
    ESERT_DESTINOS_CSV=/srv/datos/destinos.csv \
    ESERT_VISOR_DIR=/srv/visor
WORKDIR /srv
COPY --from=fuentes /srv/backend/requirements-servidor.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && mkdir -p /data
COPY --from=fuentes /srv /srv
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/salud').status==200 else 1)"
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
