# Schrittweise – KI-Mathe-Tutor für Mittelstufe, Oberstufe & Gymnasium

> **Mathe verstehen. Nicht abschreiben.** Ein Tutor, der die Lösung nie direkt
> verrät, sondern über eine **Hinweis-Leiter** (4 Stufen) zum eigenen Denken führt.
> Für Mittelstufe (4.–6. Klasse), Oberstufe (Lehrplan 21) und Gymnasium bis zur
> Matura. Die App ist zweisprachig (Deutsch/Englisch): Browser-Sprache wird beim
> ersten Besuch erkannt, manuell umstellbar (Landing/Login/Einstellungen); der
> Tutor antwortet in der gewählten Sprache.

Live: **https://schrittweise-2-0.vercel.app** · Der visuelle Massstab ist
`design/referenz.html` (im Browser öffnen).

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
| Frontend | React + Vite, Formeln via **KaTeX**, deterministische Skizzen (SVG) |
| Backend | Python + **FastAPI** |
| Mathe | **SymPy** |
| KI | Anthropic API – `claude-haiku-4-5` (Standard), `claude-sonnet-5` (Foto/Geometrie), Prompt-Caching (System + Aufgaben-Bild) |
| Handschrift/Foto | **Claude Vision** (liest Stift-Eingabe und Fotos; ohne API-Key: einfacher lokaler Fallback) |
| DB | **Supabase Postgres** (lokal SQLite) via SQLAlchemy |
| Auth | **E-Mail + Passwort** (scrypt) + JWT; Mail-Link nur für «Passwort vergessen» |
| Zahlung | **Stripe Checkout** (Karte/TWINT), signierter Webhook |
| Deployment | **Vercel** über GitHub Actions (Push auf `main` → Test → Deploy → Smoke-Test) |

## 💰 Preismodell (nutzungsbasiert)

**1 Token = 1 Rappen verrechnete KI-Leistung.** Jede Tutor-Antwort bucht
`max(1, aufgerundet(echte Kosten × USD_CHF_RATE × BILLING_MARGIN))` Tokens ab –
eine normale Antwort ≈ 1 Token, eine Foto-/Geometrie-Antwort ≈ 3–5. Auch die
Handschrift-Erkennung wird so abgerechnet; die KI-Suche der Bibliothek ist
gratis (gedrosselt).

- **Gratis:** 50 Tokens pro Konto und Monat (`FREE_MONTHLY_TOKENS`).
- **Pakete:** Schnupper CHF 2 → 200 Tokens · Starter CHF 9 → 900 · Power
  CHF 19 → 1900 (definiert in `backend/app/routers/pay.py`).
- **Marge:** `BILLING_MARGIN=3.0` – Schüler zahlen das Dreifache der echten
  Anthropic-Kosten; du kannst nie draufzahlen.
- **Qualitäts-Option:** `ANTHROPIC_MODEL_DEFAULT=claude-sonnet-5` im
  `RUNTIME_ENV_JSON` hebt auch den Text-Chat aufs starke Modell (bis
  31.08.2026 Einführungspreis ≈ 2× Haiku; dank Caching kaum Mehrkosten).
  Jederzeit rückgängig – Wirkung unter Admin → Kosten vergleichen.
- Admin- und Schul-Konten sind unbegrenzt und gratis.

## 🔧 Admin-Bereich (nur Betreiber-Konto)

In der Sidebar sichtbar, sobald `users.is_admin = TRUE`:

- **📊 Kosten** – echte KI-Kosten (Ø/Min/Max pro Aufgabe, nach Typ/Modell),
  verrechnete Tokens (Einnahmen-Deckung) und «Letzte Störungen»
  (KI-/OCR-/Webhook-Ausfälle, zusätzlich per Mail bei konfiguriertem SMTP).
- **👥 Nutzer** – Suche, Guthaben/Verbrauch, manuelle Token-Gutschrift oder
  -Korrektur mit Pflicht-Grund (jede Buchung protokolliert). Dein Werkzeug für
  Kulanz, Rückerstattungen und verpasste Webhooks.
- **💬 Feedback** – eingegangene Nutzer-Rückmeldungen.
- **📚 Bibliothek** – Arbeitsblätter hochladen/verwalten.

## 🚀 Deployment (Vercel über GitHub Actions)

**Der einzige Deploy-Weg:** Push auf `main` → `.github/workflows/deploy.yml`
läuft automatisch (Backend-Tests + Frontend-Build → Vercel-Deploy →
Smoke-Test gegen die Live-App). Es gibt KEIN manuelles Dashboard-Deployment.

**GitHub-Secrets** (Settings → Secrets and variables → Actions):

| Secret | Zweck |
|---|---|
| `VERCEL_TOKEN` | Deploy-Berechtigung |
| `RUNTIME_ENV_JSON` | JSON mit den Laufzeit-Variablen (siehe unten) – wird als Sidecar-Datei deployt, landet nie im Git |
| `ANTHROPIC_API_KEY` | überschreibt den Wert im JSON (einzeiliger Klartext, weniger Einfüge-Fehler) |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | schalten die Zahlung frei (optional bis zum Stripe-Go-live) |
| `DATABASE_URL` + `BACKUP_PASSWORD` | fürs wöchentliche DB-Backup (`backup.yml`, siehe `docs/BACKUP.md`) |

**Wichtige Laufzeit-Variablen** (im `RUNTIME_ENV_JSON`; vollständige Liste mit
Kommentaren in `backend/.env.example`):

| Variable | Zweck |
|---|---|
| `JWT_SECRET` | langer Zufallswert – Platzhalter verweigert den Start |
| `DATABASE_URL` | Supabase **Session pooler**-URL |
| `ANTHROPIC_API_KEY` | echter Tutor (ohne Key: deterministischer Mock) |
| `SUPABASE_URL` + `SUPABASE_ANON_KEY` | «Passwort vergessen»-Mails über Supabase Auth |
| `FRONTEND_BASE_URL` | `https://schrittweise-2-0.vercel.app` |
| `FREE_MONTHLY_TOKENS`, `BILLING_MARGIN`, `USD_CHF_RATE` | Preismodell (Defaults 50 / 3.0 / 0.90) |
| `REQUIRE_EMAIL_VERIFICATION` | E-Mail-Bestätigungs-Pflicht – **erst aktivieren, wenn der Mailversand nachweislich läuft** |
| `SMTP_*` + `ALERT_EMAIL` | eigener Mailversand; schaltet auch Betreiber-Alarm-Mails frei |

Supabase-Hinweise: Unter **Authentication → URL Configuration** die Site-URL
auf die Vercel-Domain und `…/login/verify` als Redirect eintragen. Der
eingebaute Supabase-Mailer ist gedrosselt (wenige Mails/Stunde) – für den
echten Betrieb unter **Authentication → SMTP Settings** einen eigenen Absender
(z. B. Brevo, gratis bis 300 Mails/Tag) hinterlegen.

Sicherheits-Guards ab Werk: Produktion bricht den Start hart ab bei
Platzhalter-`JWT_SECRET` oder aktivem Dev-Login; Registrierung mit IP-Limit +
Honeypot + AGB-Pflicht; Login-/Link-Rate-Limits; Chat-/OCR-Frequenzbremsen;
Passwort-Änderung invalidiert alle alten Tokens; Magic-Link-Tokens nur gehasht.

## 🗄️ Backup & Störungen

- **Backup:** `backup.yml` sichert die DB jeden Sonntag als (optional
  verschlüsseltes) GitHub-Artefakt, 90 Tage Aufbewahrung. Einrichtung und
  Wiederherstellung: **`docs/BACKUP.md`**.
- **Störungen:** KI-/OCR-/Webhook-Fehler erscheinen unter Admin → Kosten
  («Letzte Störungen») und gehen per Mail an `ALERT_EMAIL`, sobald SMTP
  konfiguriert ist. Für Ausfall-Überwachung von aussen: Gratis-Monitor
  (z. B. UptimeRobot) auf `https://schrittweise-2-0.vercel.app/api/health`.

## Projektstruktur

```
backend/          FastAPI-App
  app/
    models.py     Datenmodell (users, topics, exercises, attempts, messages,
                  api_usage, payments, token_adjustments, alerts, …)
    routers/      auth, topics, exercises, attempts, parents, quota,
                  library, pay, feedback, admin
    services/     sympy-Verifikation, OCR (Claude Vision), Tutor (LLM),
                  quota (Token-Abrechnung), usage (Kosten), alert, Aggregate
  tests/          pytest-Suite (läuft als Deploy-Gate in der Pipeline)
frontend/         React + Vite
  src/screens/    Landing, Login, Lernen, Themen, Bibliothek, Eltern, Preise,
                  Einstellungen, Kosten (Admin), Nutzer (Admin), Rechtliches
  src/components/ AppShell, NewTaskModal, DrawPad, MathFigure, FeedbackModal
docs/BACKUP.md    Backup einrichten & wiederherstellen
design/referenz.html   Visueller Massstab
```

## Lokal starten mit einem Befehl

- **Mac/Linux:** `./start.sh`
- **Windows:** Doppelklick auf `start.bat`

Das Skript richtet beim ersten Lauf alles ein (Python-Venv, npm-Pakete,
`.env`), startet beide Server und öffnet http://localhost:5173.
Voraussetzungen: [Python 3.11+](https://python.org) und [Node.js 18+](https://nodejs.org).

Registrieren im Tab **«Neu hier»** (E-Mail + Passwort + AGB-Häkchen – lokal
darf die E-Mail erfunden sein). Ohne `ANTHROPIC_API_KEY` antwortet ein
deterministischer Übungs-Mock; «Passwort vergessen» gibt lokal den Link direkt
zurück (`MAGIC_LINK_DEV_RETURN=true` in der `.env`).

## Lokal starten (manuell)

**Backend** (Terminal 1):

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # ANTHROPIC_API_KEY eintragen (für den echten Chat)
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

## 🚀 Launch-Checkliste (Betreiber)

Rechtsseiten (Impressum/Datenschutz/AGB) sind ausgefüllt und decken das
Token-Modell ab; Tests, Backups, Alarme und Härtung sind eingebaut. Offen:

1. **Stripe scharfschalten:** Secret Key + Webhook-Signaturgeheimnis als
   GitHub-Secrets `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` eintragen
   (Webhook-URL: `https://schrittweise-2-0.vercel.app/api/pay/webhook`,
   Event `checkout.session.completed`). Erst Test-Modus mit Karte
   4242 4242 4242 4242, dann Live-Keys.
2. **Backup aktivieren:** GitHub-Secrets `DATABASE_URL` + `BACKUP_PASSWORD`
   setzen, einmal manuell laufen lassen (`docs/BACKUP.md`).
3. **Uptime-Monitor:** z. B. UptimeRobot auf `/api/health`.
4. **Eigener Mailversand:** Brevo-SMTP im Supabase-Dashboard hinterlegen
   (oder `SMTP_*` in `RUNTIME_ENV_JSON`); danach
   `REQUIRE_EMAIL_VERIFICATION=true` setzen – ab dann brauchen neue Konten
   die E-Mail-Bestätigung für KI-Nutzung und Käufe.
5. **Bibliothek füllen** (10–15 Arbeitsblätter) und optional eigene Domain
   (z. B. schrittweise.ch) in Vercel verbinden.

Hinweis Supabase free: Projekte pausieren nach ~1 Woche ohne Zugriff – bei
täglich genutzter App passiert das nicht.
