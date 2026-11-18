#!/bin/bash
# Doble clic (macOS) para digitalizar comprobantes y consolidar la lista de espera.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Preparando el programa por primera vez..."
  python3 -m venv .venv && source .venv/bin/activate
  pip install --upgrade pip && pip install -r requirements.txt
else
  source .venv/bin/activate
fi
echo ""
echo "1) Digitalizar comprobantes (PDF -> revision.xlsx)"
echo "2) Consolidar (revision.xlsx + Workflow + agenda -> Excel final)"
read -p "Opción: " op
if [ "$op" = "1" ]; then
  read -p "Carpeta o PDF (arrástralo aquí y presiona Enter): " entrada
  caffeinate -i python -m controles digitalizar "$(eval echo $entrada)" -o salida_controles  # no deja dormir al Mac
else
  read -p "Excel de Workflow (Controles_AAAA-MM-DD.xlsx, arrástralo aquí): " wf
  read -p "Carpeta con los reportes de agenda (arrástrala aquí): " ag
  python -m controles consolidar salida_controles/revision.xlsx --workflow "$(eval echo $wf)" --agenda "$(eval echo $ag)" -o salida_controles
  open salida_controles
fi
read -p "Listo. Presiona ENTER para cerrar."
