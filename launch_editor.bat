@echo off
chcp 65001 >nul
echo %~nx0
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
rem Editor requires PyQt5 (installed by setup.bat)
echo Starting scene editor...
"%PY%" scene_editor.py
pause
