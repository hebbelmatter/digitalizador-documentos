#!/bin/bash
# Doble clic (macOS) para digitalizar comprobantes y consolidar la lista de espera.
cd "$(dirname "$0")"
# Se usa .venv/bin/python directamente (no "activate"), así la carpeta
# sigue funcionando aunque se mueva o se copie a otro lugar.
PY="$PWD/.venv/bin/python"
if ! "$PY" -c "import controles.cli, pandas, pytesseract, fitz" 2>/dev/null; then
  echo "Preparando el programa (sólo la primera vez o si se movió la carpeta)..."
  rm -rf .venv
  python3 -m venv .venv && "$PY" -m pip install --upgrade pip && "$PY" -m pip install -r requirements.txt
fi
echo ""
echo "1) Digitalizar comprobantes (PDF -> revision.xlsx)"
echo "2) Consolidar (revision.xlsx + Workflow + agenda -> Excel final)"
read -p "Opción: " op
if [ "$op" = "1" ]; then
  read -p "Carpeta o PDF (arrástralo aquí y presiona Enter): " entrada
  caffeinate -i "$PY" -m controles digitalizar "$(eval echo $entrada)" -o salida_controles  # no deja dormir al Mac
else
  read -p "Excel de Workflow (Controles_AAAA-MM-DD.xlsx, arrástralo aquí): " wf
  read -p "Carpeta con los reportes de agenda (arrástrala aquí): " ag
  "$PY" -m controles consolidar salida_controles/revision.xlsx --workflow "$(eval echo $wf)" --agenda "$(eval echo $ag)" -o salida_controles
  open salida_controles
fi
read -p "Listo. Presiona ENTER para cerrar."
