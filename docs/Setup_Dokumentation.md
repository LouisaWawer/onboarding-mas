# Setup-Dokumentation: Onboarding-MAS-Prototyp

Stand: [Datum einfügen] – laufend zu ergänzen, während das Projekt wächst.

## Projektstruktur

```
onboarding-mas/                    (liegt auf ~/Desktop)
├── backend/                       Python/LangGraph/FastAPI
│   ├── .venv/                     virtuelle Python-Umgebung (nicht in Git)
│   ├── .env                       API-Key (nicht in Git)
│   └── server.py                  FastAPI-Server mit /ping-Route
├── sandbox-app/                   simulierte Firmenumgebung (Vite/React/TS)
│   └── src/
│       └── components/            Mock-Mail, -Intranet, -Tickets (im Aufbau)
├── shell/
│   └── tauri-app/                 Tauri-Shell mit Statuspunkt (React/TS)
│       └── src/App.tsx            enthält bereits Ping-Test zum Backend
└── .gitignore
```

## 1. Entwicklungsumgebung (macOS)

Installiert über Homebrew (`brew --version` → funktioniert):

| Tool | Zweck | Version geprüft mit |
|---|---|---|
| Python 3.12 | Backend (LangGraph, FastAPI) | `python3.12 --version` |
| Node.js | Sandbox-App & Tauri-Frontend | `node --version` (v26.7.0) |
| Rust / Cargo | Tauri-Kompilierung | `rustc --version` |
| Xcode Command Line Tools | von Rust/Tauri für macOS-Build benötigt | `xcode-select -p` |

**Hinweis**: Ursprüngliches System-Python war 3.9.6 (zu alt) – `python3.12` wird deshalb im Projekt immer explizit aufgerufen, nicht `python3`.

## 2. Backend (`backend/`)

**Virtuelle Umgebung angelegt und aktiviert:**
```
python3.12 -m venv .venv
source .venv/bin/activate
```

**Installierte Pakete:**
```
pip install langgraph langgraph-checkpoint-sqlite fastapi uvicorn python-dotenv anthropic
```

**`.env`-Datei** (nicht in Git, durch `.gitignore` geschützt):
```
ANTHROPIC_API_KEY=<eingetragen>
```

**`server.py`** – minimaler FastAPI-Server mit CORS-Freigabe und einer Test-Route:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/ping")
def ping():
    return {"status": "ok"}
```

**Server starten:**
```
uvicorn server:app --reload
```
→ läuft unter `http://127.0.0.1:8000`

*Noch offen*: LangGraph-State, Agentenrollen, Interrupt-Mechanik – bewusst zurückgestellt, bis die Interviewauswertung steht (siehe ADR-Vorlagen).

## 3. Sandbox-App (`sandbox-app/`)

Initialisiert mit:
```
npm create vite@latest . -- --template react-ts
```
(Linter: Oxlint, Paketmanager: npm)

**Status**: Grundgerüst läuft (`npm run dev` → `http://localhost:5173`, Standard-Vite/React-Startseite bestätigt).

*Gerade in Arbeit*: Mock-Komponenten für die simulierte Firmenumgebung
- `src/components/MockMail.tsx` – Mail-Liste mit Lese-/Ungelesen-Status
- `MockIntranet.tsx` – noch zu erstellen
- `MockTickets.tsx` – noch zu erstellen
- Tab-Navigation in `App.tsx` – noch zu verbinden

## 4. Tauri-Shell (`shell/tauri-app/`)

Initialisiert mit:
```
npm create tauri-app@latest
```
Konfiguration: Projektname `tauri-app`, Paketmanager npm, UI-Template React, UI-Flavor TypeScript.

**Wichtig**: Liegt eine Ebene tiefer als geplant – `shell/tauri-app/`, nicht direkt in `shell/`, weil der Tauri-Assistent automatisch einen Unterordner mit dem Projektnamen anlegt.

**App starten (Entwicklungsmodus):**
```
cd shell/tauri-app
npm run tauri dev
```
→ öffnet natives Fenster (kein Browser)

**`src/App.tsx`** wurde erweitert um einen Verbindungstest zum Backend (`useEffect` + `fetch` auf `/ping`), zusätzlich zum Standard-Tauri-Template (Greet-Funktion, Logos).

*Noch offen*: Statuspunkt-UI (Form-/Farbwechsel), Chat-Panel, Rive-Integration für Animation.

## 5. End-to-End-Smoke-Test ✅

Bestätigt funktionsfähig: FastAPI-Server (`/ping`-Route) wird erfolgreich aus der Tauri-App per `fetch` abgerufen. Anzeige im Tauri-Fenster: `Backend-Status: {"status":"ok"}`.

→ Damit ist bewiesen, dass Backend und Shell technisch miteinander kommunizieren können, bevor komplexere Logik (LangGraph-Stream) aufgesetzt wird.

## 6. Git

Repository initialisiert im Hauptordner `onboarding-mas/`. Bisherige Commits (chronologisch):

1. `Initiale Projektstruktur`
2. `Sandbox-App Grundgerüst mit Vite/React/TypeScript`
3. `Tauri-Shell Grundgerüst mit React/TypeScript`
4. `End-to-End Smoke-Test: FastAPI-Ping erfolgreich aus Tauri-App abgerufen`

**`.gitignore`** schützt: `.venv/`, `.env`, `node_modules/`, `dist/`, `target/`, `src-tauri/target/`, `.DS_Store`, `__pycache__/`, `*.pyc`

## 7. Offene nächste Schritte

- [ ] Sandbox-Firmenumgebung fertigstellen (Mock-Chat/Teams-Klon, Mock-Intranet, Mock-Tickets, Mock-Kalender, Seitenleisten-Navigation)
- [ ] Statuspunkt-UI mit Zustandswechseln (idle/aktiv/wartet) – ggf. mit Rive
  - [ ] Interrupt-/Bestätigungskarte als Overlay, das über dem Punkt erscheint – unabhängig vom aktuell aktiven Sandbox-Screen (nicht an die Chat-App gekoppelt)
- [ ] Nach Interviewauswertung: LangGraph-State, Agentenrollen, Interrupt-Mechanik, konkrete Prompt-Inhalte
- [ ] **Leitplanken für den eingebetteten Agenten** (siehe Chat-Verlauf "Leitplanken"):
  - [ ] System-Prompt mit klarer Rolle, Themengrenzen, Verhalten bei Unsicherheit
  - [ ] Tool-Zugriff technisch auf definierte Sandbox-Funktionen beschränken (nicht nur per Prompt)
  - [ ] Eskalations-Fallback als Standardweg bei Unsicherheit/Scope-Überschreitung festlegen
  - [ ] Pilot-Test / gezieltes Red-Teaming vor der eigentlichen Nutzerstudie
  - [ ] ADR-004 "Guardrail-Strategie" dokumentieren
- [ ] Logging-Infrastruktur für Interaktionsdaten (inkl. Kanalwahl DM vs. Statuspunkt-Panel)
- [ ] Testskript für die Nutzerstudie (siehe Szenario_Interaktionsdesign.md)

---

*Verweis: Technische Entscheidungen mit Begründung sind separat in den ADR-Vorlagen dokumentiert (`Projekt_Vorlagen_Prototyp.md`).*
