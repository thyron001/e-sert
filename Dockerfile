# ==========================================================================================
#  e-sert — Roadmap del proyecto (Flask + Gunicorn) para Dokploy
# ==========================================================================================
#  El sitio lee los archivos del propio repo (prompts, estado.json, bitácoras, evidencias),
#  por eso este Dockerfile vive en la RAÍZ del repositorio:
#
#     docker build -t esert-roadmap .
#
#  En Dokploy: Build Path = /, Build Type = Dockerfile, Docker File = Dockerfile,
#  Docker Context Path = . , puerto 5000, dominio e-sert.tesisucuenca.com.
#  Con "Autodeploy" activo, cada push a main (por ejemplo la unificación del domingo)
#  reconstruye la imagen y el progreso de la página se actualiza solo.
# ==========================================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ESERT_RAIZ=/repo

WORKDIR /repo/roadmap

COPY roadmap/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Solo lo que el sitio necesita leer (nada de código del proyecto ni datos pesados).
COPY docs /repo/docs
COPY bitacoras /repo/bitacoras
COPY semanas /repo/semanas
COPY roadmap /repo/roadmap

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "60", "app:app"]
