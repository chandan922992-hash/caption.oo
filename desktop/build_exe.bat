@echo off
setlocal
title CLEAPYFLY - build Windows EXE
cd /d "%~dp0\.."

echo.
echo   This builds a single-file CLEAPYFLY.exe (Windows).
echo   Requirements: Python 3.10+ and the prebuilt frontend\dist folder.
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo   [X] Python is required. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo   [X] frontend\dist is missing. Use the CLEAPYFLY Setup ZIP ^(it ships prebuilt files^).
  pause
  exit /b 1
)

if not exist "backend\.venv\" (
  echo   Creating Python environment...
  python -m venv "backend\.venv"
)

call "backend\.venv\Scripts\activate.bat"
python -m pip install -q --disable-pip-version-check -r "backend\requirements.txt" pyinstaller
if errorlevel 1 (
  echo   [X] Could not install dependencies.
  pause
  exit /b 1
)

cd backend
python -m PyInstaller --noconfirm --onefile --name CLEAPYFLY ^
  --paths "." ^
  --add-data "..\frontend\dist;frontend_dist" ^
  run_server.py
if errorlevel 1 (
  echo   [X] EXE build failed.
  cd ..
  pause
  exit /b 1
)

cd ..
if not exist "installer" mkdir "installer"
copy /y "backend\dist\CLEAPYFLY.exe" "installer\CLEAPYFLY.exe" >nul

echo.
echo   Done! Single-file app created at:
echo     installer\CLEAPYFLY.exe
echo.
echo   Double-click it - CLEAPYFLY opens in your browser automatically.
echo   (First start may take a few seconds; data is saved in a "data" folder
echo    next to the exe.)
pause
