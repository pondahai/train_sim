@echo off
chcp 65001 >nul
echo %~nx0
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
rem Editor requires PyQt5 (pip install PyQt5)
echo Starting scene editor...
python scene_editor.py
pause
