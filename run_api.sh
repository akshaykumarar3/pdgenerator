#!/bin/bash
# PD Generator - Linux/macOS API Server Launcher
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "[ERROR] Virtual environment 'venv' not found."
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

echo "[LAUNCH] Starting PD Generator API Server..."
export API_PORT=410
source venv/bin/activate
python3 -m api_server
