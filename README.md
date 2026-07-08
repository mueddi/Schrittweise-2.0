# Schrittweise

**KI-Mathe-Tutor für die Schweizer Sekundarstufe I** — Mathe verstehen, nicht abschreiben.

Schrittweise ist ein Lern-Tutor für Sek-I-Schüler:innen (12–15 Jahre, Lehrplan 21),
der die Lösung nie direkt verrät. Stattdessen führt eine **Hinweis-Leiter** in vier
Stufen zum eigenen Denken:

1. Aktivierende Frage
2. Kleiner Tipp
3. Teilschritt vorgemacht
4. Volle Lösung — erst nach mindestens zwei echten eigenen Versuchen

Die Leiter wird vom Backend als Zustandsmaschine erzwungen und gilt auch dann,
wenn Schüler:innen um die Lösung betteln.

## Prinzipien

- **Nie die Lösung verraten.** Die Hinweis-Leiter ist im System-Prompt und im
  Backend verankert.
- **Privacy by Design.** Eltern sehen nur Aggregate (Selbständigkeit %, gelöste
  Aufgaben, aktive Tage, Themen-Trends) — nie Transkripte. Die Aggregate liegen
  in einer separaten Tabelle; aus der Eltern-Rolle gibt es technisch keinen
  Zugriff auf Nachrichten.
- **SymPy prüft Mathe, das LLM macht Pädagogik.** Jede Antwort wird
  deterministisch verifiziert; das Ergebnis geht als Kontext ans LLM.
- **Themen sind manuelle Container** — keine automatische Klassifikation.

## Features

- Hinweis-Leiter-Chat mit Streaming und KaTeX-Formeldarstellung
- Foto-Upload von Aufgaben mit OCR-Preview
- Themen-Verwaltung mit Fortschrittsanzeige
- Eltern-Dashboard (Verknüpfung per Code, nur Aggregate)
- Einfacher Login mit E-Mail + Passwort, Gratis-Kontingent + Preisseite
- Mock-Tutor ohne API-Key — die App ist auch ohne Anthropic-Key voll testbar

## Tech-Stack

| Bereich | Wahl |
|---|---|
| Frontend | React + Vite, Formeln via KaTeX |
| Backend | Python + FastAPI |
| Mathe-Verifikation | SymPy |
| KI | Anthropic API (Haiku als Standard, Sonnet für komplexe Aufgaben, Prompt-Caching) |
| Datenbank | SQLite → Postgres/Supabase via SQLAlchemy (nur Config-Wechsel) |
| Auth | E-Mail + Passwort (scrypt) + JWT; Magic-Link-Flows als Alternative im Code |
| Deployment | Vercel (Serverless + Static Build) oder Render (`render.yaml`-Blueprint) |

## Schnellstart

**Mit einem Befehl** (richtet beim ersten Lauf Venv, npm-Pakete und `.env` ein):

- Mac/Linux: `./start.sh`
- Windows: `start.bat`

Danach läuft die App auf http://localhost:5173. Voraussetzungen:
[Python 3.11+](https://python.org) und [Node.js 18+](https://nodejs.org).

**Manuell:**

```bash
# Backend (Terminal 1)
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # ANTHROPIC_API_KEY eintragen (optional, sonst Mock)
uvicorn app.main:app --reload --port 8000

# Frontend (Terminal 2)
cd frontend
npm install
npm run dev
```

Ohne SMTP läuft der Login im Dev-Modus: Der Magic-Link wird nach dem Absenden
direkt geöffnet — kein Mailserver nötig.

## Projektstruktur

```
backend/          FastAPI-App
  app/models.py   Datenmodell (users, topics, exercises, attempts, messages,
                  progress_aggregates, parent_links, magic_links)
  app/routers/    auth, topics, exercises, attempts, parents, quota
  app/services/   SymPy-Verifikation, OCR, Tutor (LLM), Aggregate
frontend/         React + Vite
  src/screens/    Landing, Login, Lernen, Themen, Eltern, Preise, Einstellungen
design/referenz.html   Visueller Massstab
api/index.py      Vercel-Serverless-Einstieg
render.yaml       Render-Blueprint (Frontend Static + Backend Docker inkl. Tesseract)
vercel.json       Vercel Build & Routing
```

## Deployment & Launch

Ausführliche Anleitungen (Vercel, Render, Supabase-Postgres, SMTP,
Launch-Checkliste, Sicherheits-Guards) stehen in
[SCHRITTWEISE.md](SCHRITTWEISE.md).

Wichtig: Secrets (`ANTHROPIC_API_KEY`, `JWT_SECRET`, `SMTP_*`, `DATABASE_URL`)
werden **nie committet** — nur als Umgebungsvariablen im Hosting-Dashboard
gesetzt. Die `.gitignore` schliesst `.env`-Dateien und `api/runtime-env.json`
aus. In Produktion verweigert die App den Start, wenn `JWT_SECRET` noch der
Platzhalter ist.
