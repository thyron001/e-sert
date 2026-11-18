#!/usr/bin/env bash
# Arranque del contenedor de la app `api` en el VPS.
#
# Con ESERT_GUI=1 (por defecto) levanta además una pantalla virtual para ver sumo-gui en el
# navegador (https://sumo.tesisucuenca.com):
#   Xvfb :99 → fluxbox → x11vnc (solo localhost, con contraseña, con control) → noVNC en :6080
# La simulación de la demo (POST /api/v1/demo/iniciar) abre sumo-gui en esa pantalla.
# La contraseña de VNC es ESERT_CLAVE_VNC (VNC solo usa los primeros 8 caracteres). Sin ella no se
# levanta la pantalla: nunca se publica un VNC sin contraseña.
set -euo pipefail

if [ "${ESERT_GUI:-1}" = "1" ] && [ -n "${ESERT_CLAVE_VNC:-}" ]; then
  export DISPLAY=:99
  RES="${ESERT_GUI_RESOLUCION:-1600x900x24}"
  Xvfb :99 -screen 0 "$RES" -nolisten tcp >/tmp/xvfb.log 2>&1 &
  for _ in $(seq 1 50); do [ -S /tmp/.X11-unix/X99 ] && break; sleep 0.1; done
  # fluxbox maximiza todas las ventanas (sumo-gui ocupa toda la pantalla)
  mkdir -p /root/.fluxbox
  printf '[app] (name=.*)\n  [Maximized]\t{yes}\n[end]\n' > /root/.fluxbox/apps
  fluxbox >/tmp/fluxbox.log 2>&1 &
  mkdir -p /root/.vnc
  x11vnc -storepasswd "$ESERT_CLAVE_VNC" /root/.vnc/clave >/dev/null 2>&1
  x11vnc -display :99 -rfbauth /root/.vnc/clave -localhost -rfbport 5900 -forever -shared \
         -noxdamage -quiet -bg -o /tmp/x11vnc.log
  # index.html → vnc.html con reconexión automática y escalado a la ventana
  cat > /tmp/novnc_index.html <<'HTML'
<!doctype html><meta charset="utf-8"><title>e-sert · SUMO</title>
<meta http-equiv="refresh" content="0; url=vnc.html?autoconnect=1&resize=scale&reconnect=1">
HTML
  mkdir -p /tmp/novnc && cp -r /usr/share/novnc/. /tmp/novnc/ && cp /tmp/novnc_index.html /tmp/novnc/index.html
  websockify --web /tmp/novnc 6080 localhost:5900 >/tmp/websockify.log 2>&1 &
  echo "pantalla :99 y noVNC en :6080 listos"
else
  echo "sin pantalla de sumo-gui (ESERT_GUI=${ESERT_GUI:-1}, ESERT_CLAVE_VNC $( [ -n "${ESERT_CLAVE_VNC:-}" ] && echo definida || echo vacía ))"
fi

exec python3 -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips "*"
