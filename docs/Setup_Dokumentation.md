# Setup-Dokumentation: Onboarding-MAS-Prototyp

Stand: 09.09.2026 – laufend zu ergänzen, während das Projekt wächst.

## Projektstruktur

```
onboarding-mas/                    (liegt auf ~/Projects, umgezogen von ~/Desktop
                                     wegen macOS-TCC-Berechtigungsproblemen)
├── backend/                       Python/LangGraph/FastAPI
│   ├── .venv/                     virtuelle Python-Umgebung (nicht in Git)
│   ├── .env                       API-Key (nicht in Git)
│   ├── server.py                  FastAPI-Server mit /ping-Route (noch ohne Graph-Anbindung)
│   ├── agent/                     LangGraph-Agent
│   │   ├── graph.py                Graph-Struktur (Supervisor/Sub-Agenten/Prüfer/Kontext-Check/...)
│   │   ├── state.py                State-Schema (OnboardingState)
│   │   ├── tools.py                AVAILABLE_TOOLS (geschlossene Tool-Liste, ADR-004)
│   │   ├── prompts_config.py       System-Prompt-Bausteine (Platzhalter-Formulierungen)
│   │   ├── colleague_data.py       Kolleg:innen-Daten für Eskalation/Verweise
│   │   ├── knowledge_data.py       Knowledge-Hub-/Intranet-Inhalte für search_documents
│   │   └── logging_store.py        log_interaction() -> interaction_log.jsonl
│   ├── test_graph.py              End-to-End-Terminaltest des Graphen
│   ├── test_pruefer.py            Test für pruefer_node
│   ├── interaction_log.jsonl      Log-Ausgabe von log_interaction() (generiert, aktuell in Git getrackt -
│   │                               nicht in .gitignore, siehe Abschnitt 6)
│   └── checkpoints.sqlite         SqliteSaver-Checkpoints (generiert, aktuell in Git getrackt -
│                                   nicht in .gitignore, siehe Abschnitt 6)
├── sandbox-app/                   simulierte Firmenumgebung (Vite/React/TS)
│   └── src/
│       ├── components/            geteilte UI-Bausteine (siehe docs/Komponenten.md)
│       ├── screens/                Chat, Tickets, Kalender, KnowledgeHub, Intranet
│       └── state/                  AppNotifications (Sidebar-Badges), ChatState (Lumi-Konversation)
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

*Update, Stand nach ausführlicher Backend-Entwicklungssitzung*: Die Zurückstellung wurde aufgehoben – LangGraph-Agent ist bereits substanziell gebaut und mehrfach end-to-end getestet, unabhängig von der Interviewauswertung (technische Struktur ist unabhängig von den noch ausstehenden Prompt-Feinheiten).

**Aktueller Graph-Aufbau** (`agent/graph.py`, `agent/state.py`):
- `supervisor_node`: zerlegt eingehende Nachrichten per Tool Use (erzwungenes `tool_choice`) in einen oder mehrere Teilschritte, jeweils einer Kategorie zugeordnet (`infrastructure` / `info` / `other`); routet, verwaltet Korrekturschleifen-Zähler und Teilschritt-Fortschritt
- `infrastructure_agent_node`: VPN/Zugänge, generiert Antwort-Entwurf + separate strukturierte Aktions-Extraktion (Tool Use) für `create_ticket`
- `info_agent_node`: allgemeine organisatorische Fragen, nutzt `search_documents` (Knowledge Hub/Intranet) als Grundlage, nennt Quelle in der Antwort
- `pruefer_node`: schlanke, regelbasierte Prüfung (Konfidenzwerte bei kritischen Aussagen, generische Floskeln); **wichtig**: Antwort-Entwürfe werden nur bei Freigabe permanent in die sichtbare Historie übernommen (`draft_response`-Mechanismus) – abgelehnte Entwürfe aus der Korrekturschleife bleiben unsichtbar für die Nutzer:in
- `context_check_node`: nimmt den Baseline-Snapshot des Sandbox-Zustands bei Zustimmung auf (G13, 1. Teil)
- `announce_confirmation_node`: loggt `interrupt_raised` genau einmal, bevor der erste `interrupt()` ausgelöst wird
- `human_review_node`: `interrupt()`-basierte Bestätigung, abhängig von Kontrollgrad UND Kritikalität (`is_critical`, siehe `criticality_policy.py`)
- `context_recheck_node`: vergleicht den Baseline-Snapshot gegen den Live-Zustand direkt vor der Ausführung (G13, 2. Teil, NACH der ersten Bestätigung) – bei Änderung zweiter Durchlauf über `updated_query_node` (Rückmeldung + Widerrufsmöglichkeit VOR Ausführung, Guideline 6), sonst direkte Ausführung
- `escalate_node`: generiert echte Antwort per LLM-Aufruf (nicht nur Platzhalter-Text), verweist auf echte Kolleg:innen-Daten (`colleague_data.py`)
- `execute_action_node`: führt bestätigte Aktion aus, kehrt zum Supervisor zurück (Mehrfach-Teilschritt-Schleife)

**Tools** (`agent/tools.py`): `create_ticket`, `add_calendar_event`, `send_message`, `search_documents`, `create_onboarding_plan`, `update_onboarding_plan`, `reference_colleague` – geschlossene Liste (`AVAILABLE_TOOLS`), technische Leitplanke nach ADR-004.

**Getestet und bestätigt funktionsfähig** (`test_pruefer.py`, `test_graph.py`):
- Vollständiger Kreislauf Supervisor → Sub-Agent → Prüfer → Kontext-Check → `interrupt()` → Bestätigung → Ausführung
- Mehrfach-Teilschritt-Zerlegung (eine Nachricht mit zwei Anliegen, unterschiedliche Kategorien, sequentielle Abarbeitung)
- Escalate-Pfad mit echtem, kolleg:innen-spezifischem Verweis

**Noch offen / in Arbeit**:
- FastAPI-Anbindung an die tatsächliche Sandbox-Chat-UI steht noch aus (aktuell nur Terminal-Test via `test_graph.py`)

**G13 "geänderter Kontext"-Fall – implementiert und auf Graph-Ebene getestet, im laufenden Betrieb aber nicht auslösbar** (Limitation für Kapitel 6.1): `context_recheck_node` erkennt eine Sandbox-Änderung zwischen erster Bestätigung und Ausführung korrekt und löst die zweite Bestätigung über `updated_query_node` aus (`test_context_recheck.py`, per `graph.update_state()` verifiziert – siehe dortiger Moduldocstring, was der Test beweist und was nicht). Im Studienbetrieb kann dieser Pfad aber aktuell durch keine echte Nutzeraktion ausgelöst werden: `sandbox_state` ändert sich ausschließlich durch `AVAILABLE_TOOLS`-Aufrufe innerhalb von `execute_action_node`, und ein einzelner Graph-Lauf ist strikt sequenziell – innerhalb DESSELBEN `graph.stream()`-Aufrufs kann nichts "nebenher" denselben Thread verändern, während ein `interrupt()` wartet. Ursache ist also das sequenzielle Ausführungsmodell, nicht ein fehlender Endpoint an sich – aber genau deshalb kann eine echte Nutzeraktion diesen Pfad nur über einen Kanal AUSSERHALB des laufenden Graph-Aufrufs auslösen (z.B. ein künftiger Endpoint, der `graph.update_state()` für den betroffenen Thread aufruft, während dessen `interrupt()` wartet – technisch möglich, siehe Test, aber aktuell existiert kein solcher Endpoint und keine Anbindung der Sandbox-UI (`sandbox-app/`) an `state["sandbox_state"]` in irgendeine Richtung, siehe Abschnitt 3).

**Bekannte technische Stolperfallen** (falls erneut relevant):
- Anthropic-API verlangt, dass Konversationen mit einer User-Nachricht enden – bei mehreren Sub-Agenten-Aufrufen hintereinander driftet das leicht auseinander, gelöst über `_messages_ending_with_user()` + `draft_response`-Mechanismus
- `SqliteSaver.from_conn_string()` ist in aktuellen LangGraph-Versionen ein Context-Manager, kein direktes Objekt – `build_graph()` nimmt daher einen `checkpointer`-Parameter entgegen, der Aufrufer verwaltet den `with`-Block
- `load_dotenv()` muss explizit aufgerufen werden, sonst bleibt `ANTHROPIC_API_KEY` trotz korrekt gefüllter `.env` leer

*Ursprünglich hier vorgesehen, jetzt überholt*: LangGraph-State, Agentenrollen, Interrupt-Mechanik – siehe oben, ist bereits umgesetzt.

## 3. Sandbox-App (`sandbox-app/`)

Initialisiert mit:
```
npm create vite@latest . -- --template react-ts
```
(Linter: Oxlint, Paketmanager: npm)

**Status**: Deutlich weiter als der ursprünglich hier beschriebene Mock-Stand. Alle fünf in `Szenario_Interaktionsdesign.md` (Abschnitt 1) festgelegten Apps sind als eigene Screens umgesetzt - bewusst **keine** E-Mail-Komponente (Design-Entscheidung dort, "keine E-Mail – nur interne Kommunikation"):

- `src/screens/Chat/Chat.tsx` – Konversationsliste (Onboarding-Assistent/Kanäle/Direktnachrichten) + Nachrichtenverlauf + Composer
- `src/screens/Tickets/Tickets.tsx` – Ticket-Tabelle mit Status (`TaskStatus`)
- `src/screens/Kalender/Kalender.tsx` – Wochenansicht Mo–Fr; „Neue Besprechung" öffnet kein Formular, sondern schickt eine Anfrage an Lumi in dieselbe Chat-Konversation (`useSendToLumi`)
- `src/screens/KnowledgeHub/KnowledgeHub.tsx` – Baumnavigation (`Tree`) + Artikel-Landing/gefilterte Ansicht/Detailansicht
- `src/screens/Intranet/Intranet.tsx` – Tabs Ankündigungen/Verzeichnis/Neu im Team/Über uns

Navigation über `Sidebar` (`src/components/Sidebar/`), Umschalten zwischen den fünf Screens direkt in `App.tsx` (lokaler State, kein Router). Geteilter Zustand über zwei React-Contexts in `src/state/`: `AppNotifications.tsx` (Sidebar-Benachrichtigungspunkte, jeder Screen meldet seinen Stand selbst über `useReportBadge`) und `ChatState.tsx` (eine gemeinsame Lumi-Konversation, damit z.B. der Kalender-Screen dort schreiben kann, ohne dass die Nutzer:in im Chat ist).

Geteilte UI-Komponenten (Avatar, StatusIndicator, ChatListItem, MessageBox, Tree, PreviewBlock, Filter, PushButton, TaskStatus, Sidebar/SidebarIcon, Topbar, UserWithStatus): siehe `docs/Komponenten.md` (ausführlich, mit Props) bzw. `docs/CODE_UEBERSICHT.md` (kompakte Tabelle).

*Hinweis zur früheren Planung*: `MockMail.tsx`/`MockIntranet.tsx`/`MockTickets.tsx` existieren nicht (mehr) im Code - der tatsächliche Aufbau folgt der Screen-pro-App-Struktur oben, nicht der ursprünglich hier notierten Mock-Komponenten-Liste.

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

## 7. Logging-Architektur: Interaktionskategorien

Für die Auswertung (Kapitel 5.2) muss jede Agent-Interaktion danach klassifizierbar sein, ob sie **erklärt** (Transparenz), **bestätigt** (Kontrolle) oder **autonom** handelt. Bewusste Design-Entscheidung: Diese Kategorien werden **strukturell im Graphen markiert**, nicht nachträglich aus dem generierten Text erraten (wäre fehleranfällig, bräuchte eine eigene, methodisch angreifbare Klassifikationsebene).

**Wichtige Klarstellung**: Die Nutzerstudie testet **eine** qualitative Variante (siehe `Szenario_Interaktionsdesign.md`), kein 3×3-Bedingungsvergleich wie die quantitative Vignetten-Studie. `transparency_level`/`control_level` im Code sind daher **feste Konfigurationswerte dieser einen Variante**, kein experimenteller Faktor, der gegeneinander getestet wird. Die Werte selbst sind aber nicht beliebig gewählt: `control_level` orientiert sich an der K0-Anomalie aus der quantitativen Studie (K0 zeigte die tendenziell beste Bewertung) – die Logging-Kategorien dienen dazu, **wie** sich diese eine, bewusst gewählte Konfiguration in echter Interaktion zeigt und anfühlt, nicht dem Vergleich mehrerer Konfigurationen untereinander.

**Kritikalität ist eine feste Policy, keine Modelleinschätzung**: `is_critical` (steuert L2/G3) wird nicht mehr pro Anfrage vom Modell geschätzt, sondern aus einer festen Tool-Zuordnung gelesen (`agent/criticality_policy.py`) – vorher lieferte dieselbe VPN-Anfrage über mehrere Läufe mal `true`, mal `false`, was zwei Testpersonen bei identischer Aufgabe unterschiedliches Systemverhalten hätte zeigen können. Die Zuordnung setzt die „Firmenrichtlinie als Untergrenze" aus Kapitel 4.4 um (`create_ticket`/`send_message` kritisch, `add_calendar_event` nicht; unbekannte Tools defaulten sicherheitshalber auf kritisch).

**Ableitung pro Kategorie:**

| Kategorie | Woher erkannt |
|---|---|
| `confirm` (bestätigt) | Jeder Knoten, der `interrupt()` aufruft – strukturell 100% eindeutig, keine Text-Analyse nötig |
| `autonomous` (autonom) | Jeder Knoten, der eine Aktion **ohne** vorherigen `interrupt()`-Aufruf direkt ausführt (ergibt sich aus dem Pfad der aktiven K-Variante) |
| `explain` (erklärt) | Direkt aus dem aktiven Transparenzgrad (T+/T0/T–) ableitbar, der ohnehin als Parameter an den Agenten übergeben wird – keine Erkennung im Nachhinein, sondern bekannt, bevor die Antwort überhaupt generiert wird |

Ein Schritt kann mehrere Kategorien gleichzeitig auslösen (z.B. „erklärt UND bestätigt" bei T+K+) → als Liste loggen, nicht als einzelner String.

**Beispiel-Implementierung:**

```python
def log_interaction(category, node, task=None, **extra):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "category": category,  # "explain" | "confirm" | "autonomous" (oder Liste)
        "node": node,
        "task": task,
        "condition": {"transparency": T_LEVEL, "control": K_LEVEL},
        **extra,
    }
    append_to_log(entry)

def human_review_node(state):
    log_interaction(category="confirm", node="human_review", task=state["current_task"])
    decision = interrupt({...})
    ...

def build_response(state, transparency_level):
    explains = transparency_level in ("high", "medium")
    log_interaction(category="explain" if explains else "silent", node=state["current_node"])
    ...
```

**Vorteil für die Auswertung**: Lässt sich später direkt und zuverlässig auszählen (z.B. „wie oft wurde in der gewählten Konfiguration tatsächlich bestätigt vs. wie oft hätte laut Kritikalitätsregel bestätigt werden sollen"), ohne Interaktionsprotokolle manuell durchlesen und nachträglich kategorisieren zu müssen.

**Hinweis zur API-Schicht (session_id vs. thread_id)**: Seit der FastAPI-Anbindung (`backend/api/`) trägt `state["session_id"]` im `interaction_log.jsonl` die LangGraph-`thread_id`, also eine einzelne **Anfrage** – NICHT die API-`session_id` aus `POST /session`, die eine **Testperson**/einen Durchlauf identifiziert und mehrere Anfragen enthalten kann. Welche Anfragen zu welcher Testperson gehören, steht deshalb nicht im Log selbst, sondern muss über die `anfragen`-Tabelle in `app_meta.sqlite` (Spalte `session_id`) nachgeschlagen werden.

**Hinweis zur Event-Auswertung (stream_mode="updates")**: Die SSE-Event-Schicht (`backend/api/graph_runner.py`) liest `graph.stream(..., stream_mode="updates")` und geht davon aus, dass jeder Knoten den vollständigen State zurückgibt statt eines Teil-Updates (kein Reducer-Pattern, siehe aktuelle Knoten-Implementierungen in `graph.py`) – wer das für einen Knoten ändert (z.B. durch `Annotated[..., reducer]`-Felder oder ein `return {"key": ...}`-Teil-Update statt `return state`), bricht die Event-Ableitung an dieser Stelle still, ohne dass `graph.py` selbst einen Fehler wirft.

## 8. Offene nächste Schritte

- [ ] Sandbox-Firmenumgebung fertigstellen (Chat, Intranet, Knowledge Hub, Tickets, Kalender – Design in Figma vollständig, React-Umsetzung mit Claude Code weit fortgeschritten)
- [ ] Statuspunkt-UI mit Zustandswechseln (idle/aktiv/wartet) – ggf. mit Rive
  - [ ] Interrupt-/Bestätigungskarte als Overlay, das über dem Punkt erscheint – unabhängig vom aktuell aktiven Sandbox-Screen (nicht an die Chat-App gekoppelt)
- [x] ~~Nach Interviewauswertung: LangGraph-State, Agentenrollen, Interrupt-Mechanik~~ – technische Struktur bereits umgesetzt und getestet (siehe Abschnitt 2), unabhängig von Interviewauswertung; konkrete Prompt-Inhalte (Tonalität, Formulierungen) bleiben nach Interviewauswertung zu verfeinern (`prompts_config.py`, mit `[PLATZHALTER]` markiert)
- [ ] **Leitplanken für den eingebetteten Agenten**:
  - [x] System-Prompt mit klarer Rolle, Themengrenzen, Verhalten bei Unsicherheit (`ROLE_PROMPT`, Platzhalter-Formulierungen)
  - [x] Tool-Zugriff technisch auf definierte Sandbox-Funktionen beschränkt (`AVAILABLE_TOOLS`)
  - [x] Eskalations-Fallback als Standardweg bei Unsicherheit/Scope-Überschreitung (`escalate_node`)
  - [ ] Pilot-Test / gezieltes Red-Teaming vor der eigentlichen Nutzerstudie
  - [x] ADR-004 "Guardrail-Strategie" dokumentiert (`Projekt_Vorlagen_Prototyp.md`)
- [ ] Logging-Infrastruktur für Interaktionsdaten (inkl. Kanalwahl DM vs. Statuspunkt-Panel) – Kategorien-Architektur siehe Abschnitt 7, `log_interaction()` bereits an mehreren Knoten aufgerufen, noch nicht vollständig für alle Kategorien
- [x] Lumi-Avatar im Code geprüft: `Avatar.css` setzt `border-radius: 9999px` (voller Radius), `Avatar.tsx` kommentiert das explizit ("Lumi ist genauso rund wie die Personen-Avatare"). Kein 30%-Radius mehr vorhanden, keine Code-Änderung nötig – Doku-Punkt war der veraltete Teil.
- [ ] Testskript für die Nutzerstudie (siehe Szenario_Interaktionsdesign.md)
- [ ] **Backend, konkret als Nächstes**:
  - [x] Temporären Test-Hook aus `infrastructure_agent_node` entfernen – entfernt, Korrekturschleife mehrfach echt getestet
  - [x] Kontext-Check "geändert"-Fall end-to-end getestet – auf Graph-Ebene grün (`test_context_recheck.py`), im laufenden Betrieb aber nicht auslösbar, siehe G13-Hinweis in Abschnitt 2
  - [x] `scheduling_agent` (Kalender) ergänzt, `DECOMPOSE_TOOL`-Kategorien erweitert
  - [x] FastAPI-Endpoint gebaut, der den Graphen aus der echten Sandbox-Chat-UI heraus aufruft (`backend/api/`, `server.py`) – Frontend-Anbindung selbst (`sandbox-app` ruft ihn tatsächlich auf) steht noch aus, siehe Zeile oben

---

*Verweis: Technische Entscheidungen mit Begründung sind separat in den ADR-Vorlagen dokumentiert (`Projekt_Vorlagen_Prototyp.md`).*
