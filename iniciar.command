#!/bin/bash
# Doble clic para abrir el digitalizador en macOS (o ./iniciar.command en Linux).
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Preparando el programa por primera vez..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi
python -m digitalizador web
