@echo off
REM PD Generator - Windows API Server Launcher
cd /d "%~dp0"

IF NOT EXIST venv (
    echo [ERROR] Virtual environment 'venv' not found.
    echo Please run: python -m venv venv ^& venv\Scripts\activate ^& pip install -r requirements.txt
    pause
    exit /b 1
)

echo [LAUNCH] Starting PD Generator API Server...
set API_PORT=410
call venv\Scripts\activate
python -m api_server
pause
