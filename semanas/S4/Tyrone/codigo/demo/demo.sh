#!/usr/bin/env bash
# Demo de e-sert en un comando (Linux/macOS). Usa el .venv de la demo o del backend si existe.
#   ./demo/demo.sh                 # remoto (VPS) con caída automática a local
#   ./demo/demo.sh --local         # plan B sin internet
set -euo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for VENV in "$AQUI/.venv" "$AQUI/../backend/.venv"; do
  if [ -f "$VENV/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    break
  fi
done
exec python "$AQUI/demo.py" "$@"
