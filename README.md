# Lumi – Prototyp eines KI-Onboarding-Assistenten

Forschungsprototyp zur Bachelorarbeit **„Vom Interface zur Interaktion"**
(Louisa Wawer, Wilhelm Büchner Hochschule, 2026).

„Lumi" ist ein agentischer Onboarding-Assistent für neue Mitarbeitende der
fiktiven **Nordlicht Software GmbH**. Der Prototyp besteht aus einem
Multi-Agenten-System und einer simulierten Firmenumgebung (Chat, Intranet,
Knowledge Hub, Tickets, Kalender), in der Lumi tatsächlich handelt: Tickets
anlegen, Termine eintragen, Firmenwissen durchsuchen, an zuständige
Kolleg:innen eskalieren. Er diente als Erhebungsinstrument einer
qualitativen Nutzerstudie und ist kein produktionsreifes System.

## Stack

| Bereich | Technik |
|---|---|
| Agenten-Backend | Python 3.12, LangGraph (Supervisor, Sub-Agenten, Prüfer, Kontext-Check, `interrupt()`-Bestätigung), SQLite-Checkpoints |
| API | FastAPI, Server-Sent Events |
| Frontend | React 19, TypeScript, Vite |
| Modell | Anthropic Claude (über das offizielle Python-SDK) |

Unter `shell/tauri-app/` liegt zusätzlich ein Tauri-Grundgerüst als geplante
native App-Hülle. Es ist nicht fertiggestellt und wurde in der Studie **nicht**
eingesetzt – dort lief der Prototyp im Browser.

## Voraussetzungen

- Python 3.12 (das System-Python 3.9 von macOS ist zu alt – deshalb überall
  explizit `python3.12`)
- Node.js
- Ein eigener Anthropic-API-Schlüssel

## Einrichtung

**1. Backend-Umgebung**

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install langgraph langgraph-checkpoint-sqlite fastapi uvicorn python-dotenv anthropic
```

**2. `backend/.env` anlegen** (nicht im Repository enthalten):

```
ANTHROPIC_API_KEY=dein-schluessel
STUDY_ACCESS_CODE=ein-selbst-gewaehlter-code
```

`STUDY_ACCESS_CODE` schützt den API-Schlüssel vor Fremdnutzung. Die Variable
hat bewusst **keinen Vorgabewert**: Ist sie nicht gesetzt, schlägt jeder
Session-Start fehl, statt versehentlich offen zu stehen.

**3. `sandbox-app/.env` anlegen** – Vorlage: `sandbox-app/.env.example`

```
VITE_ACCESS_CODE=derselbe-code-wie-oben
```

Der Wert muss exakt dem `STUDY_ACCESS_CODE` entsprechen. Vite kompiliert
diese Variable beim Build fest ein – sie muss also **vor** dem nächsten
Schritt gesetzt sein.

## Starten

**1. Frontend bauen**

```bash
cd sandbox-app
npm install
npx vite build
```

Bewusst `npx vite build` und nicht `npm run build`: Das npm-Skript führt
zuerst `tsc -b` aus, dessen Typprüfung am aktuellen Stand noch fehlschlägt.
Der Vite-Build selbst läuft durch.

**2. Backend starten**

```bash
cd backend
source .venv/bin/activate
uvicorn server:app
```

Der Server erkennt `sandbox-app/dist/` und liefert das gebaute Frontend
selbst aus. Aufruf damit unter **http://127.0.0.1:8000** – Frontend und API
teilen sich eine Herkunft, weshalb das Frontend seine API-Pfade relativ
auflöst und ohne neuen Build auch hinter einer wechselnden Tunnel-Adresse
funktioniert.

Für die Frontend-Entwicklung lässt sich alternativ der Vite-Devserver
(`npm run dev`) parallel betreiben; dann ist `VITE_API_BASE_URL` in
`sandbox-app/.env` auf das Backend zu setzen.

## Studiendaten

Die Interaktionsprotokolle und Chatverläufe der Testpersonen sind aus
Datenschutzgründen **nicht** Teil dieses Repositories und durch `.gitignore`
ausgeschlossen. Beim ersten Start werden die Laufzeitdateien
(`interaction_log.jsonl`, `checkpoints.sqlite`, `app_meta.sqlite`) leer neu
angelegt.

## Dokumentation

Konzeption, Architekturentscheidungen, Inhalte der fiktiven Firma und die
Setup-Details liegen unter `docs/` – Einstieg über `docs/README.md`.

---

Stand: Abgabe 28.09.2026
