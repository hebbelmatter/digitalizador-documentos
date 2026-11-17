@echo off
REM Doble clic para abrir el digitalizador en Windows.
cd /d "%~dp0"
if not exist .venv (
  echo Preparando el programa por primera vez...
  py -3 -m venv .venv || python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
python -m digitalizador web
pause
