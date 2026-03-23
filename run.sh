#!/bin/bash
# PD Generator - Linux/macOS CLI Launcher
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "[ERROR] Virtual environment 'venv' not found."
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

source venv/bin/activate
python3 run.py "$@"
if [ $? -ne 0 ]; then
    echo "[CRASH] Generator exited with error. Check the logs."
fi
