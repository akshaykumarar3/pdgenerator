@echo off
REM PD Generator - Windows CLI Launcher
cd /d "%~dp0"

IF NOT EXIST venv (
    echo [ERROR] Virtual environment 'venv' not found.
    echo Please run: python -m venv venv ^& venv\Scripts\activate ^& pip install -r requirements.txt
    pause
    exit /b 1
)

call venv\Scripts\activate
python generator.py %*
if %ERRORLEVEL% NEQ 0 (
    echo [CRASH] Generator exited with error. Check the logs.
    pause
)
