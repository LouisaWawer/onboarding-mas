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

**Tools** (`agent/tools.py`): `create_ticket`, `add_calendar_event`, `send_message`, `search_documents`, `create_onboarding_plan`, `update_onboarding_plan`, `reference_colleague` – geschlossene Liste (`AVAILABLE_TOOLS`), technische Leitplanke nach ADR-004. **Nicht alle sind über einen Graph-Pfad tatsächlich erreichbar** (geprüft, siehe Bericht an die Nutzerin – wichtig für Kapitel 6.1, sonst wird eine vorbereitete Registry-Zeile mit einer echten Fähigkeit verwechselt):
- **Erreichbar**: `create_ticket` (über `infrastructure_agent_node` → `execute_action_node`), `add_calendar_event` (über `scheduling_agent_node` → `execute_action_node`), `search_documents` (direkt in `info_agent_node`, nicht über den Bestätigungs-Umweg, da keine kritische Aktion).
- **Vorbereitet, aber unerreichbar**: `send_message`, `create_onboarding_plan`, `update_onboarding_plan` – kein Knoten in `graph.py` erzeugt jemals einen `pending_action` mit diesem Tool-Namen. `rationale.py` wusste das für `send_message` bereits selbst (eigener Kommentar dort), war aber bisher nirgends in dieser Doku festgehalten.
- **Sonderfall `reference_colleague`**: der Registry-Eintrag selbst wird nie über `execute_action_node` ausgeführt (kein `pending_action` nennt ihn), die dahinterliegende Fähigkeit (Kolleg:innen-Zuordnung) ist aber sehr wohl aktiv – `escalate_node` ruft dafür `find_colleague_for_topic()` (`colleague_data.py`) direkt auf, unter Umgehung der `AVAILABLE_TOOLS`-Registry. Funktional identisch, strukturell nicht über den generischen Tool-Dispatch.

**Klassifikation: Absicht vor Thema (`DECOMPOSE_TOOL`, `graph.py`)**: Die `category`-Beschreibung im Zerlegungs-Tool des Supervisors ordnet seit einer gezielten Schärfung ZUERST nach Absicht, danach nach Thema – vorher rein themenbasiert (VPN → `infrastructure`, Kalender → `scheduling`, unabhängig davon, ob die Nachricht eine Erklärung oder eine Handlung wollte). Grund für die Schärfung: die Kategorien selbst sind themenbasiert benannt, die Knoten dahinter aber handlungsbasiert gebaut (`infrastructure_agent_node`/`scheduling_agent_node` erzeugen echte Tickets/Termine, `info_agent_node` sucht nur nach, ohne etwas auszuführen). Eine reine Erklärfrage zum selben Thema ("Wie funktioniert VPN hier?") landete dadurch fälschlich im handlungsorientierten Knoten und bekam eine handlungsorientierte, teils selbstverneinende Antwort statt einer Erklärung. Die Tool-Beschreibung enthält seither für Infrastruktur/Kalender je ein Beispielpaar (Handlung vs. Erklärung zum selben Thema), das die Unterscheidung explizit vorführt statt sie implizit vorauszusetzen – bestätigt über sechs manuell nachgestellte Testfälle, inklusive des vorher falsch klassifizierten VPN-Beispiels.

**Gemeinsame Wortvergleichslogik (`agent/text_matching.py`)**: Wortgrenzen-Tokenisierung, deutsche Stoppwortliste, Umlaut-Normalisierung (ä→a, ö→o, ü→u, ß→ss) und ein längenbasierter Präfix-Fallback (ab 6 gemeinsamen Zeichen) liegen zentral in einem gemeinsamen Modul, importiert sowohl von `knowledge_data.py` (`search_knowledge_and_intranet`) als auch von `colleague_data.py` (`find_colleague_for_topic`) – bewusst EINE Quelle statt zwei unabhängiger Kopien derselben Technik, um Drift zwischen beiden Stellen zu vermeiden. Zwei getrennte Befunde führten dorthin:
  - **Teilstring-Kollision**: der ursprüngliche beidseitige Teilstring-Vergleich traf "Regel" (aus dem VPN-Artikel, "...in der Regel noch am selben Tag...") gegen das Suchwort "Resturlaub-Regelung", weil "regel" als Zeichenkette in "regelung" enthalten ist – unabhängig davon, dass beide Wörter inhaltlich nichts miteinander zu tun haben. Reine Wortgrenzen allein hätten dafür einen echten Kompositum-Treffer gekostet ("Urlaubsregelung" hätte den Titel "Urlaub" nicht mehr getroffen), deshalb der Präfix-Fallback ab Mindestlänge 6 Zeichen: "urlaub" (6 Zeichen) zählt als Präfix von "urlaubsregelung", "regel" (5 Zeichen) bleibt zu kurz, um als Präfix von "regelung" zu zählen – exakt an der Grenze getrennt, die den einen Fall zulässt und den anderen ausschließt.
  - **Flexions-Lücke**: `find_colleague_for_topic` fand bei reiner Teilstring-Prüfung keine Zuständigkeit für Formulierungen wie "unbeschränkten Zugängen", weil "zugang" als Zeichenkette nicht in "zugängen" steckt (ä ≠ a, auch nach `.lower()`) – führte zur Eskalation ohne konkreten Ansprechpartner, obwohl eine zuständige Person existierte. Betraf strukturell auch die Wissensdatenbank-Suche über denselben Mechanismus, war dort bis dahin nur noch nicht aufgefallen.

**Bewusst NICHT gebaut: deterministischer Klassifikations-Override-Filter**: Nach der `DECOMPOSE_TOOL`-Schärfung wurde erwogen, zusätzlich einen regelbasierten Filter NACH der Modell-Klassifikation zu setzen (Fragewort-Liste gegen Handlungsverb-Liste, nach demselben Muster wie `criticality_policy.py`), der eine Kategorie im Zweifel auf `info` zurückstuft. Verworfen nach Abwägung: der Filter wäre genau bei den Formulierungen mit dem größten Verwechslungspotenzial wirkungslos geblieben – Sätze, die sowohl ein Frage- als auch ein Handlungswort enthalten (z.B. "Wie kann ich einen Termin eintragen lassen?", im Deutschen die übliche Höflichkeitsform für eine Handlungsbitte), lösen die Überschreibung nicht aus, weil ein Handlungswort vorhanden ist. Der Filter hätte also nur die Teilmenge "reine Frage, kein Handlungswort" abgedeckt – und genau dort lieferte die geschärfte Klassifikation bereits in allen getesteten Fällen korrekte Ergebnisse, ohne einen belegten Fehlerfall, den der Filter zusätzlich hätte auffangen müssen. Ohne einen Fall, den NUR der Filter löst, wäre er zusätzlicher Code ohne nachweisbaren Nutzen – bei begrenzter Restzeit bis zur Abgabe bewusst nicht gebaut (`category_override_policy.py` existiert nicht). Festgehalten hier, damit die Entscheidung nicht wie andere bewusste Nicht-Entscheidungen in diesem Projekt spurlos verschwindet (vgl. "vorbereitet, aber unerreichbar" im Tools-Absatz oben).

**Getestet und bestätigt funktionsfähig** (`test_pruefer.py`, `test_graph.py`):
- Vollständiger Kreislauf Supervisor → Sub-Agent → Prüfer → Kontext-Check → `interrupt()` → Bestätigung → Ausführung
- Mehrfach-Teilschritt-Zerlegung (eine Nachricht mit zwei Anliegen, unterschiedliche Kategorien, sequentielle Abarbeitung)
- Escalate-Pfad mit echtem, kolleg:innen-spezifischem Verweis

**Noch offen / in Arbeit**:
- Die FastAPI-Schicht selbst (`backend/api/`) ist gebaut UND getestet (`test_api_manual.py`, 19 grüne Tests über echte HTTP-Aufrufe – nicht mehr nur der Terminal-Test via `test_graph.py`). Offen ist die Anbindung der `sandbox-app` an diese Schicht: das Frontend ruft die Endpunkte aktuell nicht auf (siehe Abschnitt 8, neuer Punkt zur Sandbox-FastAPI-Anbindung).

**Statuspunkt-Status (sechs Werte)**: Der periphere Statuspunkt kennt inzwischen sechs Werte – `idle`/`working`/`waiting` (aus dem LangGraph-Checkpoint abgeleitet, `derive_status()` in `graph_runner.py`) sowie `result`/`error`/`suggestion` als zusätzliche Interaktionsmetadaten ohne Checkpoint-Entsprechung (ausführliche Begründung siehe Abschnitt 7). Mechanismen: ein `status_override` pro Anfrage in `app_meta.sqlite` (`result`/`error`, zurückgesetzt über `POST /thread/{id}/seen`), ein `pending_suggestion_screen` pro Session (`suggestion`, zurückgesetzt über `POST /session/{id}/seen`) sowie `POST /session/{id}/screen` als fester Auslöser für einen Vorschlag beim Screenwechsel (`api/suggestion_policy.py`).

**G13 "geänderter Kontext"-Fall – implementiert und auf Graph-Ebene getestet, im laufenden Betrieb aber nicht auslösbar** (Limitation für Kapitel 6.1): `context_recheck_node` erkennt eine Sandbox-Änderung zwischen erster Bestätigung und Ausführung korrekt und löst die zweite Bestätigung über `updated_query_node` aus (`test_context_recheck.py`, per `graph.update_state()` verifiziert – siehe dortiger Moduldocstring, was der Test beweist und was nicht). Im Studienbetrieb kann dieser Pfad aber aktuell durch keine echte Nutzeraktion ausgelöst werden: `sandbox_state` ändert sich ausschließlich durch `AVAILABLE_TOOLS`-Aufrufe innerhalb von `execute_action_node`, und ein einzelner Graph-Lauf ist strikt sequenziell – innerhalb DESSELBEN `graph.stream()`-Aufrufs kann nichts "nebenher" denselben Thread verändern, während ein `interrupt()` wartet. Ursache ist also das sequenzielle Ausführungsmodell, nicht ein fehlender Endpoint an sich – aber genau deshalb kann eine echte Nutzeraktion diesen Pfad nur über einen Kanal AUSSERHALB des laufenden Graph-Aufrufs auslösen (z.B. ein künftiger Endpoint, der `graph.update_state()` für den betroffenen Thread aufruft, während dessen `interrupt()` wartet – technisch möglich, siehe Test, aber aktuell existiert kein solcher Endpoint und keine Anbindung der Sandbox-UI (`sandbox-app/`) an `state["sandbox_state"]` in irgendeine Richtung, siehe Abschnitt 3).

**Bekannte technische Stolperfallen** (falls erneut relevant):
- Anthropic-API verlangt, dass Konversationen mit einer User-Nachricht enden – bei mehreren Sub-Agenten-Aufrufen hintereinander driftet das leicht auseinander, gelöst über `_messages_ending_with_user()` + `draft_response`-Mechanismus
- `SqliteSaver.from_conn_string()` ist in aktuellen LangGraph-Versionen ein Context-Manager, kein direktes Objekt – `build_graph()` nimmt daher einen `checkpointer`-Parameter entgegen, der Aufrufer verwaltet den `with`-Block
- `load_dotenv()` muss explizit aufgerufen werden, sonst bleibt `ANTHROPIC_API_KEY` trotz korrekt gefüllter `.env` leer
- Wenn ein Fehler auftritt, BEVOR im aktuellen Lauf auch nur ein `graph.stream()`-Chunk verarbeitet wurde (`run_turn_in_background()`, `graph_runner.py`): bei einem Resume MUSS `interrupt_resolved` trotzdem published werden, sonst bleibt die Bestätigungskarte im Frontend dauerhaft auf "waiting" stehen, obwohl der Status längst auf "error" gesprungen ist – die normale `interrupt_resolved`-Logik hängt am ersten erfolgreich verarbeiteten Chunk und würde in diesem Fall nie feuern. Eigener Test dafür: `test_error_handling.py::test_fehler_waehrend_resume_schliesst_bestaetigungskarte` – genau die Sorte Detail, die bei einem künftigen Umbau still wieder kaputtgeht, wenn niemand mehr an diesen Randfall denkt.
- `graph.update_state(config, state)` OHNE `as_node` auf einem historielosen (frisch angelegten, nie über `graph.stream()` gelaufenen) Checkpoint lässt LangGraph `next` auf den Graph-Einstiegspunkt setzen (`("supervisor",)`) statt leer – `derive_status()` liest das als "working", dauerhaft, auch wenn nie etwas läuft. Betraf jede vorbelegte Anfrage (`build_preseed_states()`/`create_session()`) seit Einführung von `AnfrageSummary.status`, unbemerkt bis zur "suggestion"-Funktion (`session_has_live_anfrage()` sah dadurch jede Session permanent als aktiv an). Fix: `active_agent="__end__"` im vorbelegten State PLUS `as_node="supervisor"` beim `update_state()`-Aufruf – damit löst `route_from_supervisor()` echt auf `END` auf, `next` wird leer. Regressionstest: `test_preseeded_anfragen` prüft jetzt explizit `status == "idle"`.

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

**Bekannte Limitation des Kalender-Screens** (Kapitel 6.1, gefunden bei der Kalender-Normalisierung, nicht Teil dieses Auftrags, hier nur festgehalten): `Kalender.tsx` ist NICHT datumsbewusst – Termine werden rein über `day` (0=Montag…4=Freitag) und `hour` (volle Stunde 8-16, siehe `kalenderData.ts`) platziert, unabhängig davon, welche Woche gerade angezeigt wird. Die Pfeilnavigation blättert die Wochenansicht, aber dieselben Termine erscheinen in jeder Woche identisch – es gibt keinen Abgleich gegen ein echtes Datum. Das Raster kennt außerdem nur Werktage (keine Wochenend-Spalten, `WEEKDAYS` hat 5 Einträge) und volle Stunden (kein Minutenraster, `HOURS = [8..16]`). Das Backend normalisiert entsprechend (siehe Abschnitt 7, `PROPOSE_CALENDAR_EVENT_TOOL`).

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

**Warum `explain` keinen eigenen `log_interaction()`-Aufruf bekommt**: Anders als `confirm`/`autonomous` wird `explain` bewusst nicht als eigener Log-Eintrag geschrieben – die Information steht bereits vollständig an anderer Stelle. Ob eine Antwort einen Begründungsblock mitbringt (`rationale`-Feld, gespeichert in `message_rationale`/ausgeliefert über `message_appended`-Events und `GET /thread/{id}`), hängt ausschließlich am konfigurierten `transparency_level` ab (`transparency_allows_rationale()`, `api/rationale.py`: `rationale` wird nur bei `high`/`medium` gebaut, bei `low` immer `None`) – und `transparency_level` ist für die gesamte Studienvariante ein fester, bekannter Konfigurationswert, kein Wert, der sich von Interaktion zu Interaktion ändert und deshalb protokolliert werden müsste. Für die Auswertung reicht damit die Kombination aus dem bekannten `transparency_level` und dem tatsächlich gespeicherten `rationale`-Inhalt selbst (leer vs. mit Schritten) – ein zusätzlicher `explain`-Log-Eintrag würde exakt dieselbe Information nur redundant ein zweites Mal festhalten.

**Hinweis zur API-Schicht (session_id vs. thread_id)**: Seit der FastAPI-Anbindung (`backend/api/`) trägt `state["session_id"]` im `interaction_log.jsonl` die LangGraph-`thread_id`, also eine einzelne **Anfrage** – NICHT die API-`session_id` aus `POST /session`, die eine **Testperson**/einen Durchlauf identifiziert und mehrere Anfragen enthalten kann. Welche Anfragen zu welcher Testperson gehören, steht deshalb nicht im Log selbst, sondern muss über die `anfragen`-Tabelle in `app_meta.sqlite` (Spalte `session_id`) nachgeschlagen werden. **Präzise Ausnahme**: bei den Kategorien `suggestion_shown` und `suggestion_accepted` (siehe unten) gibt es keine thread_id – dort ist `session_id` im Log-Eintrag `None`, und die tatsächliche API-`session_id` steht stattdessen im separaten Feld `api_session_id`. Bei ALLEN anderen Kategorien trägt `session_id` weiterhin die thread_id. Wer das Log auswertet, muss also nach `category` unterscheiden, welches Feld die ID trägt – ein `groupby(session_id)` über die gesamte Datei würde sonst zwei unterschiedliche ID-Räume vermischen.

**Hinweis zur Event-Auswertung (stream_mode="updates")**: Die SSE-Event-Schicht (`backend/api/graph_runner.py`) liest `graph.stream(..., stream_mode="updates")` und geht davon aus, dass jeder Knoten den vollständigen State zurückgibt statt eines Teil-Updates (kein Reducer-Pattern, siehe aktuelle Knoten-Implementierungen in `graph.py`) – wer das für einen Knoten ändert (z.B. durch `Annotated[..., reducer]`-Felder oder ein `return {"key": ...}`-Teil-Update statt `return state`), bricht die Event-Ableitung an dieser Stelle still, ohne dass `graph.py` selbst einen Fehler wirft.

**Statuspunkt: sechs Werte, "result"/"error"/"suggestion" als Interaktionsmetadatum (nicht Graph-Zustand)**: `status_changed.status` kennt `idle | working | waiting | result | error | suggestion` (Rive-ViewModel `AvatarData.status`, Werte 0/1/3/4/5/2). "result" ist der Calm-Technology-Kern der Arbeit: peripheres Signal nach Laufende, statt Benachrichtigung – Guideline 10 wird über "error" bedient (sichtbare, Lumi-tonige Fehlernachricht statt kommentarlosem Abbruch), Guideline 21 (proaktive Vorschläge, kalibrierte Einstiegsphase) über "suggestion". Alle drei brauchen eine Information, die ein LangGraph-Checkpoint strukturell nicht hat ("wurde das gesehen"/"steht ein Vorschlag an"), deshalb leben sie als Override-Spalten in `app_meta.sqlite`, nicht im Graph-State – `derive_status(snapshot, status_override)` (`graph_runner.py`) lässt den Checkpoint-Status (waiting/working) immer gewinnen, der Override greift nur, wenn der Checkpoint selbst "fertig" sagt. Bewusst kein `CHECK`-Constraint und keine feste Werteliste in `derive_status()` – ein künftiger weiterer Wert fügt sich als weiterer String ein, ohne dass der Mechanismus umgestellt werden muss.

"result"/"error" gelten pro Anfrage (`anfragen.status_override`, `POST /thread/{id}/seen` löscht ihn), nicht pro Session (mehrere Anfragen derselben Session können gleichzeitig "result" tragen) – welcher Zustand am EINEN peripheren Punkt gewinnt, ist eine Frontend-/Calm-Technology-Entscheidung, die das Backend nicht trifft. Das Backend liefert dafür nur vollständige Information: live über `status_changed` (trägt ohnehin `thread_id`), und bei einem Reload/Session-Load über `GET /session/{id}`, dessen `AnfrageSummary` ein `status`-Feld pro Anfrage trägt. Kostet einen `graph.get_state()`-Aufruf pro Anfrage in der Session – bei einer Handvoll Anfragen unkritisch. "result" feuert nur, wenn im Lauf tatsächlich eine neue Nachricht angehängt wurde (Flag in `run_turn_in_background()`) – eine Ablehnung ohne neue Nachricht bleibt "idle", sonst wäre "result" eine leere Benachrichtigung, genau das Gegenteil von Calm Technology.

**Fehlerursache technisch vs. fachlich – die Unterscheidung existiert im Code nicht**: `AVAILABLE_TOOLS` (`tools.py`) hat aktuell keine einzige Fehlerbedingung – jede Aktion "gelingt" strukturell immer. Jeder Fehler, der in `run_turn_in_background()` ankommt, stammt aus der Anthropic-API oder einem Programmierfehler, nie aus einem begründet ablehnenden Tool. Der Chat-Text ist deshalb bewusst EIN fester Satz für beide Fälle (`ERROR_MESSAGE_TEXT`, `graph_runner.py`) – ein zweiter, "fachlicher" Text kommt erst, wenn ein Tool tatsächlich einen solchen Fall hat, nicht vorher erfunden. Die Unterscheidung lebt trotzdem im `interaction_log.jsonl`-Eintrag (`category="error"`, `error_kind`: `api_error` vs. `unexpected`, je nach `anthropic`-SDK-Exception-Klasse) – für die Auswertung, nicht für die Testperson.

**"suggestion" – proaktive Vorschläge beim Screenwechsel (Guideline 21)**: fester Auslöser (`api/suggestion_policy.py`, vier Screens: `calendar`/`tickets`/`hub`/`intranet` – bewusst NICHT `chat`, dort ist Hilfe anzubieten sinnlos, man ist ohnehin bei Lumi), echte Antwort erst nach einem Klick (dieselbe Begründung wie bei `criticality_policy.py`: ein Graph-Durchlauf pro Screenwechsel würde 10-50s dauern und jede Testperson etwas anderes sehen lassen). `suggestion_policy.py` liegt in `api/`, nicht wie `criticality_policy.py` in `agent/` – `graph.py` sieht diese Tabelle nie, sie wird ausschließlich von der API-Schicht gelesen, bevor überhaupt eine Anfrage existiert.

Anders als "result"/"error" ist ein Vorschlag NICHT an eine thread_id gebunden – er entsteht, bevor es eine Anfrage gibt. Der Override lebt deshalb eine Ebene höher, auf `sessions.pending_suggestion_screen`, mit einer separaten `suggested_screens`-Tabelle für "genau einmal pro Screen pro Session" (überlebt das Löschen des Overrides). Der Vorrang vor working/waiting gilt an ZWEI Stellen, nicht nur einer: SCHREIBZEIT (`POST /session/{id}/screen` setzt gar keinen Override, wenn gerade etwas in der Session läuft) UND – der wichtigere Fall – LESEZEIT (`resolve_pending_suggestion()`: ein bereits gespeicherter Override wird nicht angezeigt, wenn DANACH woanders in derselben Session ein Lauf startet, obwohl die Spalte selbst unverändert bleibt und der Vorschlag nach Ruhe der Session unverändert wiederkehrt – eigener Testfall dafür, siehe `test_api_manual.py`).

Der 8-10s-Verweildauer-Timer sitzt im FRONTEND (ein `setTimeout`, der beim Screenwechsel aufgeräumt wird), nicht im Backend – `POST /session/{id}/screen` bedeutet dadurch "hier wurde schon lange genug verweilt", nicht "jemand ist hier gerade", und braucht keine eigene, cancelbare Backend-Zeitsteuerung. `POST /session/{id}/seen` (Geschwister zu `POST /thread/{id}/seen`) löscht den Override, aufgerufen vom Frontend entweder beim Öffnen des Panels ODER beim Verlassen des Screens – der Endpunkt kennt nur "hinfällig geworden", nicht warum.

Ein Klick auf den Vorschlag erzeugt bewusst eine NEUE Anfrage (`POST /session/{id}/anfrage` + `POST /message` mit dem hinterlegten Text, `suggestion_screen` im Body gesetzt), nicht die Fortsetzung einer aktiven – das ist nicht nur thematisch sauberer, sondern die einzige Option, die mit den bestehenden Konflikt-Guards in `post_message` überhaupt funktioniert: eine laufende/wartende Anfrage lehnt neue Nachrichten ohnehin mit 409 ab. `suggestion_screen` ist ein explizites Feld (kein Text-Abgleich gegen `suggestion_policy.py`), damit `suggestion_accepted` zuverlässig geloggt wird, auch wenn sich der Wortlaut später ändert.

**Kalender-Normalisierung: das Modell übernimmt die Umrechnung, nicht Frontend-Parsing**: `add_calendar_event` verlangte früher Freitext (`date`/`time`, wie das Modell sie aus der Nutzernachricht extrahierte, z.B. aus einem echten Testlauf `{'date': 'Donnerstag', 'time': '14:00'}`) – der Sandbox-Kalender (`Kalender.tsx`) arbeitet aber mit einem festen Raster (`weekday` 0-4, `hour` volle Stunde 8-16, siehe `kalenderData.ts`). Eine Parsing-Schicht im Frontend für natürlichsprachliche Zeitangaben ("nächsten Dienstag", "halb drei") wäre Aufwand mit offener Fehlerquote gewesen – stattdessen verlangt `PROPOSE_CALENDAR_EVENT_TOOL` (`graph.py`) direkt normalisierte Werte vom Modell, das ohnehin schon natürlichsprachliche Zeitangaben versteht (dieselbe Begründung wie bei `criticality_policy.py`: eine feste Struktur statt einer zweiten, fehleranfälligen Verarbeitungsschicht).

Rundung auf volle Stunden ist akzeptiert (kein Minutenraster), wird aber NICHT stillschweigend vorgenommen: `_execution_confirmation_text()` nennt den tatsächlich eingetragenen (gerundeten) Wochentag/Uhrzeit explizit in der Bestätigungsnachricht, damit eine Testperson sieht, was wirklich eingetragen wurde, nicht nur was sie gesagt hat.

Termine außerhalb der darstellbaren Woche (andere Woche, Wochenende) lösen KEINE stille Nicht-Handlung aus: `within_current_week` im Tool-Schema lässt das Modell das selbst erkennen; der System-Prompt weist es an, das der Nutzer:in als bewusste Prototyp-Grenze zu erklären (nicht als technischen Fehler) und stattdessen einen Termin innerhalb der aktuellen Woche anzubieten – eine Testperson, die "nächsten Montag" sagt und nichts passiert, würde sonst etwas Falsches über das System lernen. Relative Zeitangaben ("morgen", "nächsten Donnerstag") brauchen dafür eine "heute"-Referenz.

**"heute" wird zur LAUFZEIT ermittelt (`_sandbox_today_weekday_name()`, `graph.py`), nicht fest hinterlegt** – ein fester Tag wäre irgendwann in der Vergangenheit relativ zum tatsächlichen Testzeitpunkt gelegen (unabhängig vom Abgabetermin: ein fiktiver Anker hat mit dem Tag, an dem eine Testperson tatsächlich sitzt, grundsätzlich nichts zu tun), und "morgen" hätte gegen ein fiktives Datum gerechnet. Bewusst NUR der Wochentags-**Name** im Prompt, kein Kalenderdatum: ein konkretes Datum ("heute ist der 23.09.2026") hat das Modell in einem echten Testlauf dazu verleitet, Kalenderdaten zu VERGLEICHEN ("Dienstag, 22.09. liegt vor dem 23.09., also schon vorbei, muss übernächste Woche gemeint sein") statt den genannten Wochentag einfach auf das Sandbox-Raster abzubilden – in dieser Ein-Wochen-Sandbox gibt es kein "vorbei", jeder genannte Wochentag (Montag–Freitag) ist gültig, unabhängig davon, ob er vor oder nach dem heutigen Wochentag liegt. Die reine Namens-Referenz umgeht das strukturell, weil es dem Modell keine zwei Kalenderdaten mehr gibt, die es gegeneinander abwägen könnte.

**Wochenende**: `datetime.date.today().weekday()` liefert dann 5/6, außerhalb des Mo-Fr-Rasters – kein Ersatzwert (z.B. "dann ist heute eben Montag"), sondern eine ehrliche Ansage im System-Prompt, dass gerade kein "heute" existiert. Ein Montag-Ersatz hätte für "morgen" eine KONKRET FALSCHE Antwort erzeugt (z.B. an einem Samstag: echtes Morgen ist Sonntag, Montag-Ersatz hätte "Dienstag" behauptet) statt nur eine fehlende – genau die Art stillschweigend falscher Annahme, die diese ganze Änderung vermeiden soll. Eine explizite Wochentags-Nennung ("trag das für Donnerstag ein") funktioniert am Wochenende trotzdem normal, da sie keine "heute"-Referenz braucht.

Die Bestätigungskarte erscheint im Nachrichtenverlauf — im Chat-Screen und im Statuspunkt-Panel —, nicht als globales Overlay über dem aktiven Sandbox-Screen. Wer sich gerade in einer anderen App bewegt, wird ausschließlich über den peripheren Statuspunkt (waiting) darauf hingewiesen und entscheidet selbst, wann er hinsieht. Das ist eine bewusste Umsetzung von Guideline 18 (Kontrollierbare Unterbrechung): Das System zeigt an, dass es wartet, unterbricht aber nicht. Der Preis ist, dass eine Bestätigung länger offen bleiben kann — diese Verzögerung ist in der Auswertung selbst ein Datenpunkt zur erlebten Kontrolle.

## 8. Offene nächste Schritte

- [x] Sandbox-Firmenumgebung fertigstellen (Chat, Intranet, Knowledge Hub, Tickets, Kalender – alle fünf Screens als eigene React-Komponenten umgesetzt, siehe Abschnitt 3/`CODE_UEBERSICHT.md`)
- [ ] Anbindung der Sandbox-App an die FastAPI-Schicht (Chat, Panel, Statuspunkt, Bestätigungskarte, Transparenzblock, Anfragen-Liste)
- [ ] Statuspunkt-UI mit Zustandswechseln – Backend-Seite fertig (sechs Statuswerte idle/working/waiting/result/error/suggestion, inkl. Rive-ViewModel-Zuordnung, siehe Abschnitt 7) und Rive-Dateien liegen vor, aber im FRONTEND nicht umgesetzt: die Sandbox-App hat bis heute keinen einzigen Aufruf an die FastAPI-Schicht, entsprechend existiert keine sichtbare Statuspunkt-UI (korrekt als offen geführt in Abschnitt 4 – die vorherige Version dieser Zeile hier in Abschnitt 8 widersprach dem fälschlich)
- [x] ~~Nach Interviewauswertung: LangGraph-State, Agentenrollen, Interrupt-Mechanik~~ – technische Struktur bereits umgesetzt und getestet (siehe Abschnitt 2), unabhängig von Interviewauswertung; konkrete Prompt-Inhalte (Tonalität, Formulierungen) bleiben nach Interviewauswertung zu verfeinern (`prompts_config.py`, mit `[PLATZHALTER]` markiert)
- [ ] **Leitplanken für den eingebetteten Agenten**:
  - [x] System-Prompt mit klarer Rolle, Themengrenzen, Verhalten bei Unsicherheit (`ROLE_PROMPT`, Platzhalter-Formulierungen)
  - [x] Tool-Zugriff technisch auf definierte Sandbox-Funktionen beschränkt (`AVAILABLE_TOOLS`)
  - [x] Eskalations-Fallback als Standardweg bei Unsicherheit/Scope-Überschreitung (`escalate_node`)
  - [ ] Pilot-Test / gezieltes Red-Teaming vor der eigentlichen Nutzerstudie
  - [x] ADR-004 "Guardrail-Strategie" dokumentiert (`Projekt_Vorlagen_Prototyp.md`)
- [x] Logging-Infrastruktur für Interaktionsdaten (inkl. Kanalwahl DM vs. Statuspunkt-Panel) – Kategorien-Architektur siehe Abschnitt 7. `log_interaction()` läuft an folgenden Stellen: `decomposition`, `correction_loop`, `pruefer_check`, `context_check`, `interrupt_raised`, `confirm`, `autonomous`, `escalate` (alle `agent/graph.py`), `error` (`api/graph_runner.py`), `suggestion_shown`/`suggestion_accepted` (`api/routes.py`). `explain` bekommt bewusst KEINEN eigenen Log-Eintrag – die Information steckt bereits in `transparency_level` (fester Konfigurationswert) + dem tatsächlich gespeicherten `rationale`-Inhalt, siehe Begründung in Abschnitt 7.
- [x] Lumi-Avatar im Code geprüft: `Avatar.css` setzt `border-radius: 9999px` (voller Radius), `Avatar.tsx` kommentiert das explizit ("Lumi ist genauso rund wie die Personen-Avatare"). Kein 30%-Radius mehr vorhanden, keine Code-Änderung nötig – Doku-Punkt war der veraltete Teil.
- [ ] Testskript für die Nutzerstudie (siehe Szenario_Interaktionsdesign.md)
- [ ] **Backend, konkret als Nächstes**:
  - [x] Temporären Test-Hook aus `infrastructure_agent_node` entfernen – entfernt, Korrekturschleife mehrfach echt getestet
  - [x] Kontext-Check "geändert"-Fall end-to-end getestet – auf Graph-Ebene grün (`test_context_recheck.py`), im laufenden Betrieb aber nicht auslösbar, siehe G13-Hinweis in Abschnitt 2
  - [x] `scheduling_agent` (Kalender) ergänzt, `DECOMPOSE_TOOL`-Kategorien erweitert
  - [x] FastAPI-Schicht gebaut (`backend/api/`): Sessions (`POST`/`GET /session`), Anfragen (`POST /session/{id}/anfrage`, `GET /thread/{id}`), SSE-Event-Stream (`GET /events/{session_id}`), Rationale-Spiegel (`store.py`/`rationale.py`), mehrbenutzerfähig (Session-/Anfrage-Trennung über `app_meta.sqlite`, 404 statt 403 bei fremder `thread_id`) – Frontend-Anbindung selbst (`sandbox-app` ruft die Endpunkte tatsächlich auf) steht noch aus, siehe Zeile oben

---

*Verweis: Technische Entscheidungen mit Begründung sind separat in den ADR-Vorlagen dokumentiert (`Projekt_Vorlagen_Prototyp.md`).*
