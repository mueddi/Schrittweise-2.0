#!/usr/bin/env bash
# Einmalige Einrichtung im Codespace: Backend-Venv + Frontend-Pakete.
set -e
cd "$(dirname "$0")/.."

echo "==> Backend einrichten"
cd backend
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
[ -f .env ] || cp .env.example .env

echo "==> Frontend einrichten"
cd ../frontend
npm install --no-audit --no-fund

echo "==> Fertig. Server starten automatisch (siehe .devcontainer/run.sh)."
