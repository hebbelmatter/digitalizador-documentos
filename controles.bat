@echo off
rem Doble clic (Windows) para digitalizar comprobantes y consolidar la lista de espera.
cd /d "%~dp0"
if not exist .venv (
  echo Preparando el programa por primera vez...
  python -m venv .venv
  call .venv\Scripts\activate
  python -m pip install --upgrade pip
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
echo.
echo 1) Digitalizar comprobantes (PDF -^> revision.xlsx)
echo 2) Consolidar (revision.xlsx + Workflow + agenda -^> Excel final)
set /p op=Opcion: 
if "%op%"=="1" goto digitalizar
goto consolidar

:digitalizar
set /p entrada=Carpeta con los PDF: 
python -m controles digitalizar %entrada% -o salida_controles
goto fin

:consolidar
set /p wf=Excel de Workflow (Controles_AAAA-MM-DD.xlsx): 
set /p ag=Carpeta con los reportes de agenda: 
python -m controles consolidar salida_controles\revision.xlsx --workflow %wf% --agenda %ag% -o salida_controles
start "" salida_controles

:fin
pause
