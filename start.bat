@echo off
chcp 65001 >nul 2>&1
title Kaddu - Vote confidentiel (local)
cd /d "%~dp0"

echo.
echo  ==========================================
echo   Kaddu - lancement local
echo  ==========================================
echo.

set PYCMD=
py --version >nul 2>&1 && set PYCMD=py
if "%PYCMD%"=="" ( python --version >nul 2>&1 && set PYCMD=python )
if "%PYCMD%"=="" ( python3 --version >nul 2>&1 && set PYCMD=python3 )
if "%PYCMD%"=="" (
  echo [ERREUR] Python introuvable. Installez-le depuis https://www.python.org/downloads/
  echo Cochez "Add Python to PATH" lors de l'installation.
  pause & exit /b 1
)
echo Python detecte : %PYCMD%
echo.

echo [1/2] Installation des dependances (flask, phe, gunicorn)...
%PYCMD% -m pip install -r requirements.txt --quiet 2>nul
echo        OK
echo.

echo [2/2] Demarrage...
echo.
echo  -----------------------------------------------
echo   Ouvrez votre navigateur sur :
echo   http://localhost:5000
echo  -----------------------------------------------
echo   (CTRL+C pour arreter)
echo.

%PYCMD% app.py
pause
