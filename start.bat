@echo off
title Elizabeth AI
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m elizabeth.main
pause
