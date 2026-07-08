@echo off
REM Schrittweise mit EINEM Doppelklick lokal starten (Windows).
REM Voraussetzungen: Python 3.11+ (python.org) und Node.js 18+ (nodejs.org)
cd /d "%~dp0"

where python >nul 2>nul || (echo Python fehlt - bitte von python.org installieren ^(Haken bei "Add to PATH" setzen^) & pause & exit /b 1)
where npm >nul 2>nul || (echo Node.js fehlt - bitte von nodejs.org installieren & pause & exit /b 1)

echo == Backend einrichten (erster Lauf dauert etwas) ==
cd backend
if not exist .venv python -m venv .venv
call .venv\Scripts\pip install --quiet -r requirements.txt
if not exist .env copy .env.example .env >nul
cd ..

echo == Frontend einrichten ==
cd frontend
if not exist node_modules call npm install --no-audit --no-fund
cd ..

echo == Server starten ==
start "Schrittweise API" cmd /k "cd backend && .venv\Scripts\uvicorn app.main:app --port 8000"
timeout /t 3 /nobreak >nul
start "Schrittweise Web" cmd /k "cd frontend && npm run dev"
timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo Schrittweise laeuft: http://localhost:5173
echo Zum Beenden beide Konsolenfenster schliessen.
pause
