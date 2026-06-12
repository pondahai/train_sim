@echo off
chcp 65001 >nul
echo %~nx0
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo Starting train simulator (loads scene.txt)...
python main.py
pause
