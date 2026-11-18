# Servicio `visor` de Dokploy: solo archivos estáticos (nginx). Contexto = raíz del repo:
#   docker build -f proyecto/visor/Dockerfile .
FROM nginx:1.27-alpine
COPY proyecto/visor/nginx.conf /etc/nginx/conf.d/default.conf
COPY proyecto/visor /usr/share/nginx/html/visor
RUN cd /usr/share/nginx/html/visor && rm -rf tests __pycache__ *.py requirements.txt package.json Dockerfile nginx.conf
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/salud >/dev/null || exit 1
