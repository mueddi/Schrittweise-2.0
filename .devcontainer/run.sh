#!/usr/bin/env bash
# Startet Backend (8000) und Frontend (5173) im Hintergrund – laeuft bei jedem
# Codespace-Start automatisch. Logs: /tmp/schrittweise-api.log / -web.log
cd "$(dirname "$0")/.."

# nicht doppelt starten
pgrep -f "uvicorn app.main:app" >/dev/null || (
  cd backend && nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    > /tmp/schrittweise-api.log 2>&1 &
)
pgrep -f "vite" >/dev/null || (
  cd frontend && nohup npm run dev -- --host \
    > /tmp/schrittweise-web.log 2>&1 &
)

echo "Schrittweise laeuft: Port 5173 (App) im Ports-Tab oeffnen."
exit 0
