@echo off
chcp 65001 >nul
setlocal
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ==========================================
echo  train_sim - environment setup
echo ==========================================
echo.

rem --- 1. Check Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Install Python 3.x first.
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo Found %%v

rem --- 2. Create virtual environment ---
if exist "venv\Scripts\python.exe" (
    echo [SKIP] venv already exists.
) else (
    echo [1/3] Creating virtual environment "venv" ...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)

rem --- 3. Install dependencies ---
echo [2/3] Installing dependencies from requirements.txt ...
"venv\Scripts\python.exe" -m pip install --upgrade pip
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. See messages above.
    pause
    exit /b 1
)

rem --- 4. Verify imports ---
echo [3/3] Verifying imports ...
"venv\Scripts\python.exe" -c "import pygame, OpenGL, numpy, numba, scipy, PIL, PyQt5; print('All dependencies OK')"
if errorlevel 1 (
    echo [ERROR] Verification failed. See messages above.
    pause
    exit /b 1
)

echo.
echo Setup complete. Use launch.bat / launch_editor.bat to start.
pause
