@echo off
setlocal
title CLEAPYFLY - AI Viral Video Clipping
cd /d "%~dp0\.."

echo.
echo   ==========================================
echo     CLEAPYFLY - one-time setup and launch
echo   ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo   [X] Python is required but was not found.
  echo       Install Python 3.10 or newer from https://www.python.org/downloads/
  echo       and tick "Add python.exe to PATH" during installation.
  echo.
  pause
  exit /b 1
)

if not exist "backend\.venv\" (
  echo   [1/3] Creating Python environment ^(one-time^)...
  python -m venv "backend\.venv"
  if errorlevel 1 (
    echo   [X] Could not create the Python environment.
    pause
    exit /b 1
  )
) else (
  echo   [1/3] Python environment ready.
)

call "backend\.venv\Scripts\activate.bat"
echo   [2/3] Checking dependencies...
python -m pip install -q --disable-pip-version-check -r "backend\requirements.txt"
if errorlevel 1 (
  echo   [X] Dependency installation failed. Check your internet connection.
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo   [X] Prebuilt web files are missing ^(frontend\dist^).
  echo       Re-download the CLEAPYFLY Setup ZIP or build the frontend with Node.js.
  pause
  exit /b 1
)

echo   [3/3] Starting CLEAPYFLY at http://127.0.0.1:8734
echo.
start "" http://127.0.0.1:8734
python backend\run_server.py

echo.
echo   CLEAPYFLY stopped.
pause
