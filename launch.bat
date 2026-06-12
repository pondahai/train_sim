@echo off
chcp 65001 >nul
echo %~nx0
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
echo Starting train simulator (loads scene.txt)...
"%PY%" main.py
pause
