# Kniff – Arbeitsanweisung

KI-Mathe-Tutor für die Schweizer Mittelstufe, Oberstufe und das Gymnasium.
Live: https://schrittweise-2-0.vercel.app · Repository: `mueddi/Schrittweise-2.0`

Der Betreiber ist **kein Programmierer**. Erkläre auf Deutsch, in ganzen Sätzen,
ohne Fachjargon – und wenn Fachbegriffe unvermeidlich sind, erkläre sie beim
ersten Mal. Er trifft die Entscheidungen; du lieferst Belege, keine Vermutungen.

## Die Regeln, die nicht verhandelbar sind

1. **Keine Geheimnisse ins Repository und keine in den Chat.** Weder
   `api/runtime-env.json` noch `.env` noch Token, Schlüssel oder Passwörter –
   auch nicht als Ausschnitt. Schlüssel*namen* sind in Ordnung, Werte nie.
2. **NIEMALS auf `main` pushen, mergen oder rebasen.** Nicht nach einem «ok»,
   nicht nach einer Ankündigung, nicht «weil es fertig ist». Arbeit geht
   ausschliesslich auf einen Zweig und wird dorthin gepusht. Der Zusammenführer
   ist **immer der Betreiber**, von Hand auf github.com. Am 31.07. habe ich
   zweimal nach einem «ok» selbst gemergt – er wollte das nicht. Es gibt keinen
   Fall, in dem dieser Punkt zur Diskussion steht.
3. **Nie ungefragt einen Pull Request anlegen.** Nur wenn er ausdrücklich
   darum bittet.
4. **Riskantes zuerst in die Vorschau.** Alles, was das Startverhalten, die
   Datenbank oder die Konfiguration betrifft, geht auf einen Zweig und wird
   dort geprüft, bevor es `main` sieht.
5. **Ein Commit, ein Thema.** Am 31.07. musste eine Änderung zurückgerollt
   werden und riss zwei fertige, geprüfte Aufräumungen mit. Riskantes und
   Harmloses gehören nicht zusammen.
6. **Messen statt vermuten.** Produktions-Datenbank (Supabase), Vercel-Laufzeit-
   protokolle und GitHub-Actions-Läufe sind zugänglich. Eine Behauptung ohne
   Beleg ist keine Antwort. Der Betreiber hat ausdrücklich erlaubt, die
   gespeicherten Chats in der Datenbank zu lesen.

## Wie eine Änderung live geht

```
Zweig  →  Vercel baut automatisch eine Vorschau  →  er schaut sie an
       →  Pull Request  →  283 Tests  →  sein Merge-Klick  →  live
```

* **Produktion ausschliesslich über `.github/workflows/deploy.yml`** (Test →
  Deploy → Smoke-Test). `vercel.json` setzt `git.deploymentEnabled {"main":
  false}`, damit Vercel `main` nicht an den Tests vorbei deployt – genau das
  hat am 31.07. einen fünfminütigen Ausfall verursacht.
* **In Vercel niemals «Promote to Production»** benutzen. Das umgeht die Tests.
* **Vorschau-Umgebung** (Vercel → Environment Variables, Umgebung *Preview*):
  `JWT_SECRET` (ein **anderer** als in Produktion – gleicher Wert hiesse, ein
  Ausweis aus der Vorschau gälte auch live), `DATABASE_URL` auf das eigene
  Supabase-Projekt **kniff-vorschau** (`fdgbeicshpttcqnhinso`, leer, eigene
  Tabellen) und `ANTHROPIC_API_KEY` (eigener Schlüssel, damit die Testkosten
  getrennt sichtbar sind – jede Testantwort kostet echtes Geld).
  E-Mail-Bestätigung ist dort abgeschaltet (`app/plattform.vorschau_defaults`),
  sonst käme man nicht hinein.
  **Vorher lief die Vorschau auf SQLite in `/tmp`** – die gehört jeweils nur
  einer Serverless-Instanz, also warf sie einen nach dem Anmelden sofort wieder
  raus. Nicht dorthin zurück.
* Vorschau-Adressen liegen hinter dem Vercel-Login. Aus einer Cloud-Sitzung
  sind sie oft nur per GET erreichbar oder gar nicht – dann den Betreiber
  bitten, die Zeile zu kopieren, statt zu raten.

## Tests

```
cd backend && python -m pytest -q          # 283 Tests, müssen alle grün sein
cd frontend && npm run build               # enthält die Browser-Dialog-Bremse
```

Bei reinen Streichungen darf **kein** bestehender Test angepasst werden müssen –
muss doch einer angefasst werden, war der Code nicht tot.

Fehlen die Abhängigkeiten im Container: `uv venv /tmp/kniff-venv` und
`uv pip install --python /tmp/kniff-venv/bin/python -r backend/requirements.txt pytest`.

## Wo was liegt

| Bereich | Datei |
|---|---|
| Anweisung an den Tutor (deutscher Fliesstext) | `backend/app/services/tutor.py` |
| Mathe-Prüfung | `backend/app/services/sympy_verifier.py` |
| Chat-Bildschirm | `frontend/src/screens/Lernen.jsx` |
| App-Dialoge (nie `window.confirm`!) | `frontend/src/lib/dialog.jsx` |
| Preise, Kontingent | `backend/app/config.py` |
| Farben, Schriften | `frontend/src/styles/theme.css` |
| Serverless-Einstieg (Vercel) | `api/index.py` |

Browser-Dialoge (`alert`, `confirm`, `prompt`) sind verboten und werden vom
Build abgewiesen (`frontend/scripts/keine-browser-dialoge.mjs`). Stattdessen
`useDialog()` aus `lib/dialog.jsx`.

## Offen (Stand 2. September 2026)

* **Die wöchentliche Sicherung ist noch nie gelaufen** – acht Läufe seit dem
  19.07., alle gescheitert am fehlenden GitHub-Secret `DATABASE_URL`
  (`.github/workflows/backup.yml`). Es existiert keine Kopie der Daten. Das ist
  der wichtigste offene Punkt; er muss die Secrets selbst anlegen.
* **Kein Zweig-Schutz auf `main`** – solange er fehlt, kann direkt live
  geschoben werden. Er will das ändern.
* **Keine Überwachung von aussen.** Zwei Ausfälle blieben unbemerkt, bis er
  zufällig hinschaute. Er muss UptimeRobot einrichten – Typ «Keyword», Adresse
  `…/api/health`, Stichwort `"status":"ok"`, Alarm wenn es FEHLT.
  Die Gegenstelle dafür steht: `main.py:health()` fasst die Datenbank an und
  antwortet bei einem Ausfall mit **503** und ohne das Wort `ok`.
* **Vercel läuft auf `hobby`** – dieser Tarif ist laut Vercels Bedingungen für
  nicht-kommerzielle Projekte. Vor dem Verkauf von Tokens klären.
* **Die Zahlung wurde nie durchgeführt:** im Live-Stripe-Konto stehen
  0 Checkout-Sitzungen. Vor dem Start einmal echt kaufen und nachzählen.
* **Impressum ohne Postadresse** (`frontend/src/screens/Rechtliches.jsx`) –
  nur Name und E-Mail. Für ein kommerzielles Schweizer Angebot zu wenig.

## Bekannte Schwächen (belegt, nicht behoben)

* **Die Bilderkennung ist das grösste Problem.** Von den letzten drei
  fotografierten Aufgaben waren zwei unbrauchbar gelesen (`Fg=` statt einer
  Physikaufgabe). Der Tutor kann nichts dafür – er bekommt nur, was die
  Texterkennung liefert.
* **Die Mathe-Prüfung urteilt selten:** 94 % der Antworten kommen als «nicht
  prüfbar» zurück, weil nur 15 von 52 Aufgaben einen Prüfausdruck haben.
  Symbolische Antworten (`x = 7y/3`) kann sie ohnehin nicht beurteilen.
* **Das «günstige» Modell ist teurer:** gemessen an 89 Chat-Runden kostet
  `claude-haiku-4-5` 1.29 Rappen pro Antwort, `claude-sonnet-5` 0.98 – Haikus
  Zwischenspeicher greift erst ab 4096 Token, unser Vorlauf liegt darunter.
* **`attempts.status` und `exams.model`** sehen tot aus, sind aber `NOT NULL`
  ohne Standardwert in der Produktion. Werden sie aus dem Modell entfernt,
  schlagen Einfügungen fehl. **Nicht anfassen.**
