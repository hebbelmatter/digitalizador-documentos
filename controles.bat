@echo off
rem Doble clic (Windows) para digitalizar comprobantes y consolidar la lista de espera.
cd /d "%~dp0"
rem Se usa .venv\Scripts\python.exe directamente: sigue funcionando si se mueve la carpeta.
set "PY=%~dp0.venv\Scripts\python.exe"
"%PY%" -c "import controles.cli, pandas, pytesseract, fitz" 2>nul
if errorlevel 1 (
  echo Preparando el programa ^(solo la primera vez o si se movio la carpeta^)...
  if exist .venv rmdir /s /q .venv
  python -m venv .venv
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r requirements.txt
)
echo.
echo 1) Digitalizar comprobantes (PDF -^> revision.xlsx)
echo 2) Consolidar (revision.xlsx + Workflow + agenda -^> Excel final)
set /p op=Opcion: 
if "%op%"=="1" goto digitalizar
goto consolidar

:digitalizar
set /p entrada=Carpeta o PDF: 
"%PY%" -m controles digitalizar %entrada% -o salida_controles
goto fin

:consolidar
set /p wf=Excel de Workflow (Controles_AAAA-MM-DD.xlsx): 
set /p ag=Carpeta con los reportes de agenda: 
"%PY%" -m controles consolidar salida_controles\revision.xlsx --workflow %wf% --agenda %ag% -o salida_controles
start "" salida_controles

:fin
pause
