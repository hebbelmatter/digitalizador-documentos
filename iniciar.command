#!/bin/bash
# Doble clic para abrir el digitalizador en macOS (o ./iniciar.command en Linux).
cd "$(dirname "$0")"
PY="$PWD/.venv/bin/python"
if ! "$PY" -c "import digitalizador, flask" 2>/dev/null; then
  echo "Preparando el programa (sólo la primera vez o si se movió la carpeta)..."
  rm -rf .venv
  python3 -m venv .venv && "$PY" -m pip install --upgrade pip && "$PY" -m pip install -r requirements.txt
fi
"$PY" -m digitalizador web
