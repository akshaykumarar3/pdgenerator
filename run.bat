@echo off
REM Wrapper to run the generator with the correct Python environment (Windows)
call venv\Scripts\activate
python generator.py %*
