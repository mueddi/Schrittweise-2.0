#!/usr/bin/env bash
# Schrittweise mit EINEM Befehl lokal starten (Mac/Linux):  ./start.sh
# Richtet beim ersten Lauf alles ein, startet Backend + Frontend und
# oeffnet http://localhost:5173
set -e
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "❌ python3 fehlt – bitte Python 3.11+ installieren (python.org)"; exit 1; }
command -v npm >/dev/null || { echo "❌ npm fehlt – bitte Node.js 18+ installieren (nodejs.org)"; exit 1; }

echo "==> Backend einrichten (nur beim ersten Mal dauert das etwas)"
cd backend
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet -r requirements.txt
[ -f .env ] || cp .env.example .env
cd ..

echo "==> Frontend einrichten"
cd frontend
[ -d node_modules ] || npm install --no-audit --no-fund
cd ..

echo "==> Server starten (Beenden mit Ctrl+C)"
trap 'kill 0' EXIT
(cd backend && .venv/bin/uvicorn app.main:app --port 8000) &
sleep 2
(cd frontend && npm run dev) &
sleep 3

URL="http://localhost:5173"
echo ""
echo "✅ Schrittweise laeuft: $URL"
command -v open >/dev/null && open "$URL" || command -v xdg-open >/dev/null && xdg-open "$URL" || true
wait
