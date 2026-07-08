# Schrittweise – KI-Mathe-Tutor für die Schweizer Oberstufe

> **Mathe verstehen. Nicht abschreiben.** Ein Tutor, der die Lösung nie direkt
> verrät, sondern über eine **Hinweis-Leiter** (4 Stufen) zum eigenen Denken führt.
> Für Sek-I-Schüler:innen (12–15 J.), passend zum **Lehrplan 21**.

Der visuelle Massstab ist `design/referenz.html` (im Browser öffnen).

## Prinzipien (nicht verhandelbar)

- **Nie die Lösung verraten.** Hinweis-Leiter: (1) aktivierende Frage, (2) kleiner
  Tipp, (3) Teilschritt vorgemacht, (4) volle Lösung – erst nach ≥ 2 echten
  eigenen Versuchen. Der System-Prompt erzwingt das (auch bei Betteln).
- **Privacy by Design.** Eltern sehen nur **Aggregate** (Selbständigkeit %,
  gelöste Aufgaben, aktive Tage, Themen-Trends) – nie Transkripte. Aggregate
  liegen in einer separaten Tabelle; aus der Eltern-Rolle gibt es technisch
  keinen Zugriff auf Nachrichten.
- **Themen sind manuelle Container** – keine automatische Klassifikation.
- **SymPy prüft Mathe, das LLM macht Pädagogik.** Jede Antwort wird deterministisch
  verifiziert; das Ergebnis geht als Kontext ans LLM.

## Tech-Stack

| Bereich | Wahl |
|---|---|
| Frontend | React + Vite, Formeln via **KaTeX** |
| Backend | Python + **FastAPI** |
| Mathe | **SymPy** |
| KI | Anthropic API – `claude-haiku-4-5` (Standard), `claude-sonnet-4-6` (komplex), Prompt-Caching |
| DB | SQLite → via **SQLAlchemy** (Postgres/Supabase = Config-Wechsel) |
| Auth | Magic-Link (passwortlos) + JWT |
| Deployment | **Vercel** (Serverless-Function + Static Build) oder Render |

## Deployment auf Vercel

Das Repo importieren (`vercel.json` regelt Build & Routing). **Pflicht-Umgebungs­variablen**
im Vercel-Dashboard (Settings → Environment Variables):

| Variable | Wert | Zweck |
|---|---|---|
| `JWT_SECRET` | langer Zufallswert (`openssl rand -hex 32`) | Token-Signatur – **Platzhalter verweigert den Start** |
| `DATABASE_URL` | Supabase Session-Pooler-URL (`postgresql://…pooler.supabase.com:5432/postgres`) | dauerhafte DB (sonst flüchtiges SQLite in `/tmp`) |
| `MAGIC_LINK_DEV_RETURN` | `false` (Produktion) | ohne SMTP `true` **nur** zusammen mit `ALLOW_INSECURE_DEV_LOGIN=true` |
| `FRONTEND_BASE_URL` | `https://<projekt>.vercel.app` | korrekte Magic-Link-URL (wird sonst von Vercel abgeleitet) |
| `ANTHROPIC_API_KEY` | `sk-ant-…` | echter Tutor (ohne Key: deterministischer Mock) |
| `SMTP_*` | Zugang (z. B. Brevo) | Magic-Link per Mail statt Dev-Rückgabe |

Sicherheits-Guard: In Produktion (Env `VERCEL`/`RENDER` gesetzt) bricht der Start hart
ab, wenn `JWT_SECRET` der Platzhalter ist oder der Dev-Login ohne bewusste Freigabe
aktiv wäre. Uploads liegen auf Vercel in `/tmp` (flüchtig) – für dauerhaften Foto-Upload
Objekt-Storage anbinden.

## Projektstruktur

```
backend/          FastAPI-App
  app/
    models.py     Datenmodell (users, topics, exercises, attempts, messages,
                  progress_aggregates, parent_links, magic_links)
    routers/      auth, topics, exercises, attempts, parents, quota
    services/     sympy-Verifikation, OCR-Interface, Tutor (LLM), Aggregate
  requirements.txt
  .env.example
frontend/         React + Vite
  src/screens/    Landing, Login, Lernen, Themen, Eltern, Preise, Einstellungen
  src/components/ AppShell (Sidebar), NewTaskModal
  .env.example
design/referenz.html   Visueller Massstab
```

## Am einfachsten testen: GitHub Codespaces (ohne Installation)

1. Repo auf GitHub öffnen.
2. Grüner Button **«Code» → Tab «Codespaces» → «Create codespace on main»**.
3. 2–3 Minuten warten (Einrichtung läuft automatisch, Server starten von selbst).
4. Unten im Tab **«Ports»** bei **5173 (Schrittweise App)** auf das
   Globus-Symbol «Open in Browser» klicken – fertig.

Im Login-Screen den Tab **«Neu hier»** nehmen (Dev-Modus loggt ohne E-Mail ein).

## Lokal starten mit einem Befehl

- **Mac/Linux:** `./start.sh`
- **Windows:** Doppelklick auf `start.bat`

Das Skript richtet beim ersten Lauf alles ein (Python-Venv, npm-Pakete,
`.env`), startet beide Server und öffnet http://localhost:5173.
Voraussetzungen: [Python 3.11+](https://python.org) und [Node.js 18+](https://nodejs.org).

## Lokal starten (manuell)

**Backend** (Terminal 1):

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # ANTHROPIC_API_KEY eintragen (für den Chat)
uvicorn app.main:app --reload --port 8000
# API-Docs: http://localhost:8000/docs
```

**Frontend** (Terminal 2):

```bash
cd frontend
npm install
npm run dev
# App: http://localhost:5173  (Vite proxyt /api ans Backend)
```

Ohne SMTP läuft der Login im **Dev-Modus**: Der Magic-Link wird nach dem
Absenden direkt geöffnet – kein Mailserver nötig.

## 🚀 Launch-Checkliste

Die App ist technisch launch-fertig (Auth gehärtet, Rate-Limits, Postgres,
Rechtsseiten, CI). Vor dem offiziellen Start musst du als Betreiber:in nur noch:

1. **Rechtsseiten ausfüllen**: In `frontend/src/screens/Rechtliches.jsx` die
   orange markierten `[BITTE ERGÄNZEN]`-Platzhalter ersetzen (Name/Adresse,
   Kontakt-E-Mail, Hosting-Region) – und die Datenschutzerklärung idealerweise
   juristisch gegenlesen lassen (Zielgruppe sind Minderjährige!).
2. **SMTP-Zugang besorgen** (z.B. Brevo – gratis bis 300 Mails/Tag): Host,
   User, Passwort im Render-Dashboard als `SMTP_*` eintragen. Ohne SMTP gibt
   der Login in Produktion bewusst einen klaren Fehler statt unsicherem
   Dev-Login (`MAGIC_LINK_DEV_RETURN=false` ist im Blueprint gesetzt).
3. **`ANTHROPIC_API_KEY`** im Render-Dashboard setzen (echter KI-Tutor;
   ohne Key antwortet der deterministische Übungs-Mock).
4. **Datenbank bei Supabase anlegen** (dauerhaft gratis, 500 MB):
   1. [supabase.com](https://supabase.com) → kostenloses Konto → **New project**
      (Region **Frankfurt (eu-central-1)**, sicheres DB-Passwort merken).
   2. Im Projekt: **Connect** (oben) → Tab **Session pooler** → Connection-String
      kopieren (Format
      `postgresql://postgres.<projekt>:<PASSWORT>@aws-0-eu-central-1.pooler.supabase.com:5432/postgres`).
      Wichtig: **Session pooler**, nicht «Transaction pooler» und nicht
      «Direct connection» (die ist IPv6-only und von Render aus nicht erreichbar).
   3. Diesen String im Render-Dashboard als **`DATABASE_URL`** eintragen –
      fertig, die Tabellen legt die App beim ersten Start selbst an.
   *(Alternative: Render-eigenes Postgres – auskommentierter Block im
   `render.yaml`; der Gratis-Plan dort läuft allerdings nach 30 Tagen ab.)*
5. **Deployen** (Blueprint unten) und die gegenseitigen URLs eintragen.
6. Optional: eigene Domain in Render verbinden, Uploads-Persistenz (Disk)
   buchen. Hinweis Supabase free: Projekte pausieren nach ~1 Woche ohne
   Zugriff und lassen sich im Dashboard mit einem Klick wecken – bei täglich
   genutzter App passiert das nicht.

Sicherheit ab Werk: Magic-Link-Tokens nur gehasht gespeichert (einmalig,
30 Min gültig), Rate-Limit 5 Login-Anfragen/15 Min pro E-Mail,
Security-Header, Eingabe-Längenlimits, LLM-Verlauf gedeckelt,
Eltern sehen strukturell nie Transkripte (403 + separate Aggregat-Tabelle).

## Deployment (Render)

`render.yaml` im Repo-Root ist ein fertiger Blueprint (Frontend Static Site +
Backend Docker-Web-Service inkl. Tesseract fürs OCR):

1. In Render «New → Blueprint» auf dieses Repo zeigen.
2. Im Backend-Service `ANTHROPIC_API_KEY` setzen (`sync: false` – nie im Repo).
3. Nach dem ersten Deploy die echten URLs eintragen: Frontend `VITE_API_BASE` →
   Backend-URL, Backend `CORS_ORIGINS`/`FRONTEND_BASE_URL` → Frontend-URL, dann
   redeploy.

Hinweise:
- Ohne SMTP läuft der Magic-Link im Dev-Rückgabe-Modus. Für echten Betrieb
  `SMTP_*` setzen und `MAGIC_LINK_DEV_RETURN=false`.
- SQLite auf dem free tier ist **ephemer**. Für dauerhafte Daten Postgres
  anlegen und `DATABASE_URL` umstellen – dank SQLAlchemy nur ein Config-Wechsel.
- OCR (`pytesseract`) braucht das Tesseract-Binary; das Docker-Image bringt es
  mit. Lokal ohne Tesseract degradiert der Foto-Upload sauber (manuelle
  Korrektur im Preview).

## Stand: alle Phasen umgesetzt

- **Phase 1 – Fundament**: Datenmodell + Auto-Migration, Magic-Link-Auth (JWT,
  Rollen-Guards), App-Shell + Routing zu allen Screens im Design-Look.
- **Phase 2 – Kernschleife**: Hinweis-Leiter-Chat (Backend-Zustandsmaschine
  erzwingt die 4 Stufen), SymPy-Verifikation, LLM-Pädagogik (Haiku/Sonnet +
  Prompt-Caching), Streaming, KaTeX. Mock-Tutor ohne API-Key.
- **Phase 3 – Struktur**: Themen-CRUD + Fortschritt, Themen-Detail,
  Foto-Upload mit OCR-Preview (`OcrProvider`-Interface).
- **Phase 4 – Eltern & Kontingent**: Aggregate (separat, nie Transkripte),
  Eltern-Verknüpfung per Code, Eltern-Dashboard, Gratis-Kontingent + Preise.
- **Phase 5 – Feinschliff**: Responsive (Mobile-Navigation, Grid-Breakpoints),
  globales 401-Handling (Auto-Logout), Fehlerzustände, Render-Deployment.
