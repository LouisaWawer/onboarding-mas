"""
Manueller Testablauf für die FastAPI-Schicht (backend/api/ + server.py).
Nutzt nur die Standardbibliothek (kein requests/httpx, da nicht Teil der
bisher installierten Pakete - siehe Setup_Dokumentation.md Abschnitt 2).

Voraussetzung: Server läuft bereits, z.B.
    cd backend && source .venv/bin/activate
    STUDY_ACCESS_CODE=test123 uvicorn server:app --reload

Ausführen (in einem zweiten Terminal):
    STUDY_ACCESS_CODE=test123 python test_api_manual.py

Deckt die im Auftrag geforderten Prüfpunkte ab (siehe Docstrings der
einzelnen Testfunktionen). Bricht bei einer fehlgeschlagenen Prüfung mit
AssertionError ab - das ist gewollt, damit sofort klar ist, WELCHER Schritt
nicht wie erwartet lief.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Optional

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
ACCESS_CODE = os.getenv("STUDY_ACCESS_CODE", "test123")
# Nur sinnvoll auswertbar, wenn Server und Testskript dieselbe Maschine/
# denselben Checkout nutzen (siehe backend/agent/logging_store.py: LOG_FILE
# liegt relativ zu graph.py, hier fest relativ zu diesem Skript nachgebaut -
# beide liegen in backend/).
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interaction_log.jsonl")


# Bewusst UNABHÄNGIG von agent/criticality_policy.py nachgebildet statt
# importiert (dieses Skript ist ein reiner HTTP-Black-Box-Client, siehe
# Moduldocstring) - prüft dadurch wirklich das über die API beobachtbare
# Verhalten gegen die dokumentierte Policy, nicht nur, dass der Code mit
# sich selbst übereinstimmt.
EXPECTED_TOOL_CRITICALITY = {
    "create_ticket": True,
    "add_calendar_event": False,
}

# Bewusst UNABHÄNGIG von agent/graph.py nachgebildet - siehe Begründung
# bei EXPECTED_TOOL_CRITICALITY oben.
WEEKDAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]

# Bewusst UNABHÄNGIG von api/suggestion_policy.py nachgebildet - siehe
# Begründung bei EXPECTED_TOOL_CRITICALITY oben.
SUGGESTION_TEXTS = {
    "calendar": {
        "displayed": "Wenn du einen Termin eintragen willst, mache ich das gern für dich.",
        "submitted": "Ich möchte einen Termin eintragen.",
    },
    "tickets": {
        "displayed": "Wenn du etwas von einem Team brauchst, kann ich daraus ein Ticket machen.",
        "submitted": "Ich brauche etwas von einem Team und möchte eine Anfrage stellen.",
    },
    "hub": {
        "displayed": "Wenn du nicht findest wonach du suchst, frag mich direkt.",
        "submitted": "Ich suche etwas in der Wissensdatenbank und finde es nicht.",
    },
    "intranet": {
        "displayed": "Falls du wissen willst, wer hier wofür zuständig ist: frag mich.",
        "submitted": "Wer ist bei Nordlicht wofür zuständig?",
    },
}


def _read_log_entries() -> list[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


# --- kleine HTTP-Helfer (stdlib-only) ---------------------------------------


def _request(method: str, path: str, body: Optional[dict] = None) -> tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        return e.code, (json.loads(raw) if raw else None)


def get(path: str) -> tuple[int, Any]:
    return _request("GET", path)


def post(path: str, body: Optional[dict] = None) -> tuple[int, Any]:
    return _request("POST", path, body)


class SSEListener:
    """Liest GET /events/{session_id} in einem Hintergrund-Thread und
    sammelt alle Events in Empfangsreihenfolge (self.events) - die Liste
    dient auch zur Reihenfolge-Prüfung zwischen mehreren Events
    (wait_for_after), nicht nur zur reinen Existenz-Prüfung."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events: list[dict] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()
        time.sleep(0.3)  # kurz warten, bis die Verbindung wirklich steht

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        url = f"{BASE_URL}/events/{self.session_id}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            for raw_line in resp:
                if self._stop.is_set():
                    return
                line = raw_line.decode("utf-8").rstrip("\n")
                if line.startswith(":"):
                    continue  # Keepalive-Kommentar
                if line.startswith("data:"):
                    payload = line[len("data:"):].strip()
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    with self._lock:
                        self.events.append(event)

    def wait_for(self, event_type: str, thread_id: Optional[str] = None, timeout: float = 20.0) -> dict:
        _, event = self.wait_for_after(event_type, -1, thread_id=thread_id, timeout=timeout)
        return event

    def wait_for_after(
        self,
        event_type: str,
        after_index: int,
        thread_id: Optional[str] = None,
        status: Optional[str] = None,
        session_scoped: bool = False,
        timeout: float = 20.0,
    ) -> tuple[int, dict]:
        """Wie wait_for, aber nur Events MIT INDEX > after_index in
        self.events - für Reihenfolge-Prüfungen zwischen mehreren Events
        (z.B. "kommt X wirklich NACH Y"). Gibt (index, event) zurück, damit
        der zurückgegebene Index als after_index für die nächste Prüfung
        in derselben Kette weiterverwendet werden kann.

        session_scoped=True filtert auf thread_id IS NULL - für die
        session-gebundenen status_changed-Events der "suggestion"-Funktion
        (siehe Bericht an die Nutzerin), die denselben Status-Wortschatz
        wie thread-gebundene Events teilen (z.B. "idle") und sich sonst
        nicht eindeutig zuordnen ließen."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                for idx, event in enumerate(self.events):
                    if idx <= after_index:
                        continue
                    if event.get("type") != event_type:
                        continue
                    if thread_id is not None and event.get("thread_id") != thread_id:
                        continue
                    if session_scoped and event.get("thread_id") is not None:
                        continue
                    if status is not None and event.get("status") != status:
                        continue
                    return idx, event
            time.sleep(0.2)
        raise TimeoutError(
            f"Event '{event_type}' (thread_id={thread_id}, status={status}, "
            f"session_scoped={session_scoped}) nach Index {after_index} "
            f"nicht innerhalb {timeout}s erhalten"
        )

    def all_of(self, event_type: str, thread_id: Optional[str] = None) -> list[dict]:
        with self._lock:
            return [
                e for e in self.events
                if e.get("type") == event_type and (thread_id is None or e.get("thread_id") == thread_id)
            ]


# --- gemeinsamer Vorlauf für die Resume-Tests -------------------------------


def _start_anfrage_and_wait_for_interrupt(session_id: str, listener: SSEListener, text: str) -> tuple[str, dict]:
    """Legt eine neue Anfrage an, sendet `text`, wartet bis der Graph an
    einem interrupt() wartet (status "waiting" + interrupt_pending-Event).
    Gibt (thread_id, interrupt_pending-Event) zurück - gemeinsamer Vorlauf
    für die Bestätigungs- und die Ablehnungs-Prüfung."""
    status, body = post(f"/session/{session_id}/anfrage")
    assert status == 200
    thread_id = body["thread_id"]

    status, body = post(f"/message/{thread_id}", {"session_id": session_id, "text": text})
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"

    # 120s: deckelt den Worst Case ab (MAX_CORRECTION_ATTEMPTS=2 in graph.py,
    # gemessen ~50-60s für 2 Korrekturrunden, siehe Bericht an die Nutzerin) -
    # mit Reserve für allgemeine Latenzschwankungen.
    loop_start = time.time()
    waiting_seen = False
    deadline = loop_start + 120
    while time.time() < deadline:
        if any(e["status"] == "waiting" for e in listener.all_of("status_changed", thread_id=thread_id)):
            waiting_seen = True
            break
        time.sleep(0.3)
    assert waiting_seen, f"kein 'waiting' nach {time.time() - loop_start:.1f}s"

    interrupt_event = listener.wait_for("interrupt_pending", thread_id=thread_id, timeout=5.0)
    return thread_id, interrupt_event


# --- Testschritte ------------------------------------------------------------


def test_access_code() -> str:
    """Session mit gültigem Code anlegen, ohne Code abgelehnt."""
    status, body = post("/session", {"access_code": "definitiv-falsch"})
    assert status == 403, f"erwartet 403 bei falschem Code, bekam {status}"

    status, body = post("/session", {"access_code": ACCESS_CODE})
    assert status == 200, f"Session-Anlage fehlgeschlagen: {status} {body}"
    session_id = body["session_id"]
    print(f"[ok] Session angelegt: {session_id}")
    return session_id


def test_preseeded_anfragen(session_id: str) -> list[dict]:
    """Vorbelegte Anfragen erscheinen in der Liste dieser Session, mit
    Titel, UND als 'idle' statt 'working' - explizite Regressionsprüfung,
    kein Nebenprodukt (siehe Bericht an die Nutzerin): graph.update_state()
    ohne as_node ließ jede vorbelegte Anfrage dauerhaft 'working' zeigen,
    seit dem AnfrageSummary.status-Feld aus einem früheren Auftrag
    unbemerkt - erst die 'suggestion'-Funktion (session_has_live_anfrage)
    machte den Fehler überhaupt sichtbar."""
    status, body = get(f"/session/{session_id}")
    assert status == 200
    anfragen = body["anfragen"]
    assert len(anfragen) >= 2, f"erwartet >=2 vorbelegte Anfragen, bekam {len(anfragen)}"
    for a in anfragen:
        assert a["title"], f"vorbelegte Anfrage ohne Titel: {a}"
        assert a["status"] == "idle", (
            f"vorbelegte Anfrage zeigt Status '{a['status']}' statt 'idle' - "
            f"siehe Bericht an die Nutzerin (graph.update_state ohne as_node): {a}"
        )
    print(f"[ok] {len(anfragen)} vorbelegte Anfragen vorhanden, Titel gesetzt, Status 'idle'")
    return anfragen


def test_neue_anfrage_und_titel(session_id: str, listener: SSEListener) -> str:
    """Neue Anfrage anlegen, Nachricht senden, Titel wird gesetzt; Status
    working -> waiting bei der Bestätigungskarte. Reine Vorlauf-/
    Titel-Prüfung - der eigentliche Resume-Pfad (Bestätigung/Ablehnung)
    wird in test_bestaetigung_* / test_ablehnung_* separat geprüft."""
    status, body = post(f"/session/{session_id}/anfrage")
    assert status == 200
    thread_id = body["thread_id"]
    assert body["title"] is None

    status, body = post(
        f"/message/{thread_id}",
        {"session_id": session_id, "text": "Ich brauche VPN-Zugang, kannst du das einrichten?"},
    )
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"

    titled = listener.wait_for("anfrage_titled", thread_id=thread_id)
    assert titled["title"].startswith("Ich brauche VPN-Zugang"), titled

    working = listener.wait_for("status_changed", thread_id=thread_id)
    assert working["status"] == "working", working

    # 120s: deckelt den Worst Case ab (MAX_CORRECTION_ATTEMPTS=2 in graph.py,
    # gemessen ~50-60s für 2 Korrekturrunden, siehe Bericht an die Nutzerin) -
    # mit Reserve für allgemeine Latenzschwankungen.
    loop_start = time.time()
    waiting_seen = False
    deadline = loop_start + 120
    while time.time() < deadline:
        if any(e["status"] == "waiting" for e in listener.all_of("status_changed", thread_id=thread_id)):
            waiting_seen = True
            break
        time.sleep(0.3)
    assert waiting_seen, f"kein 'waiting' nach {time.time() - loop_start:.1f}s"

    interrupt_event = listener.wait_for("interrupt_pending", thread_id=thread_id)
    print(f"[ok] Titel gesetzt, working->waiting, interrupt_pending: {interrupt_event['proposal']}")

    status, snap = get(f"/thread/{thread_id}?session_id={session_id}")
    assert status == 200
    assert snap["status"] == "waiting"
    assert snap["interrupt"] is not None
    print("[ok] GET /thread zeigt wartende Bestätigungskarte konsistent zum Event")

    return thread_id


def test_rationale(session_id: str, thread_id: str, listener: SSEListener) -> None:
    """rationale.steps der ERSTEN (Vorschlags-)Nachricht enthält genau die
    tatsächlich stattgefundenen Handlungen, Kopfzahl stimmt (len(steps) ==
    angezeigte Zahl)."""
    appended = listener.all_of("message_appended", thread_id=thread_id)
    assert appended, "kein message_appended-Event für diese Anfrage erhalten"
    first = appended[0]
    rationale = first.get("rationale")
    if rationale is None:
        print("[hinweis] rationale ist None - transparency_level erlaubt keine Rationale (siehe DEFAULT_TRANSPARENCY_LEVEL)")
        return
    steps = rationale["steps"]
    print(f"[ok] rationale.steps (Vorschlag): {len(steps)} Schritt(e): {[s['label'] for s in steps]}")
    labels = [s["label"] for s in steps]
    assert not any(l.endswith("erstellt") or l.endswith("eingetragen") for l in labels), (
        f"Vorschlags-Nachricht trägt bereits ein Ausführungs-Label: {labels}"
    )


def test_bestaetigung_liefert_ausfuehrungs_schritt(session_id: str, listener: SSEListener) -> str:
    """(a) BESTÄTIGUNG: nach POST /resume mit Zustimmung kommt
    interrupt_resolved, danach ein ZWEITES message_appended für dieselbe
    thread_id, danach status_changed "result" (nicht mehr "idle" - siehe
    Bericht an die Nutzerin: peripheres Signal nach Abschluss, solange
    noch niemand POST /thread/{id}/seen aufgerufen hat) - genau in dieser
    Reihenfolge. Die rationale.steps dieser zweiten Nachricht tragen ein
    Ausführungs-Label ("... erstellt"/"... eingetragen"/"... gesendet"),
    nicht das Vorschlags-Label der Nachricht davor."""
    thread_id, interrupt_event = _start_anfrage_and_wait_for_interrupt(
        session_id, listener, "Ich brauche VPN-Zugang, kannst du das einrichten?"
    )

    # (2) KRITIKALITÄT AUS POLICY: is_critical kommt jetzt aus einer festen
    # Tool-Zuordnung, nicht mehr vom Modell - deshalb hier eine einzelne
    # Prüfung gegen den erwarteten Policy-Wert statt mehrfacher Läufe (die
    # Stabilität ist durch die Herkunft aus einer festen Tabelle bereits
    # strukturell garantiert, kein empirischer Beleg über N Durchläufe nötig
    # - siehe Bericht an die Nutzerin).
    actual_critical = interrupt_event["proposal"]["is_critical"]
    assert actual_critical == EXPECTED_TOOL_CRITICALITY["create_ticket"], (
        f"is_critical für create_ticket weicht von der Policy ab: "
        f"erwartet {EXPECTED_TOOL_CRITICALITY['create_ticket']}, bekam {actual_critical}"
    )
    print(f"[ok] is_critical policy-konform: create_ticket -> {actual_critical}")

    options = interrupt_event["options"]
    confirm_option = next(
        (o for o in options if "bestätig" in o.lower() and "trotzdem" not in o.lower()), None
    )
    assert confirm_option, f"keine (einfache) Bestätigungs-Option in {options} gefunden"

    appended_before = len(listener.all_of("message_appended", thread_id=thread_id))
    assert appended_before == 1, f"erwartet genau 1 message_appended (Vorschlag) vor /resume, bekam {appended_before}"

    # -1-Offset: after_index ist der Index des LETZTEN bereits bekannten
    # Events (len(events) selbst wäre der Index, den das NÄCHSTE Event
    # bekommt, und würde durch "idx <= after_index" fälschlich mit
    # ausgeschlossen - siehe wait_for_after()).
    baseline = len(listener.events) - 1
    status, body = post(f"/resume/{thread_id}", {"session_id": session_id, "decision": confirm_option})
    assert status == 200, f"POST /resume fehlgeschlagen: {status} {body}"

    idx_resolved, _ = listener.wait_for_after("interrupt_resolved", baseline, thread_id=thread_id, timeout=30.0)
    idx_message, message_event = listener.wait_for_after(
        "message_appended", idx_resolved, thread_id=thread_id, timeout=30.0
    )
    idx_result, _ = listener.wait_for_after(
        "status_changed", idx_message, thread_id=thread_id, status="result", timeout=30.0
    )
    print(
        f"[ok] Reihenfolge stimmt: interrupt_resolved(#{idx_resolved}) "
        f"-> message_appended(#{idx_message}) -> result(#{idx_result})"
    )

    rationale = message_event.get("rationale")
    assert rationale is not None, "Bestätigungsnachricht hat keine rationale (transparency_level?)"
    labels = [s["label"] for s in rationale["steps"]]
    execution_labels = [l for l in labels if l.endswith("erstellt") or l.endswith("eingetragen") or l.endswith("gesendet")]
    assert execution_labels, f"kein Ausführungs-Label in der Bestätigungsnachricht gefunden: {labels}"
    proposal_labels = [l for l in labels if l.endswith("vorgeschlagen") or l.endswith("vorbereitet")]
    assert not proposal_labels, f"Vorschlags-Label taucht in der Bestätigungsnachricht (fälschlich) auf: {labels}"
    print(f"[ok] Ausführungs-Label bestätigt: {labels}")
    print(f"[ok] Bestätigungstext: {message_event['message']['content']!r}")

    return thread_id


def test_seen_setzt_result_auf_idle_zurueck(session_id: str, thread_id: str, listener: SSEListener) -> None:
    """POST /thread/{id}/seen setzt 'result' (aus
    test_bestaetigung_liefert_ausfuehrungs_schritt) auf 'idle' zurück -
    sowohl live per SSE-Event als auch in GET /thread danach. Prüft
    zusätzlich, dass die Antwort NICHT blind 'idle' behauptet, sondern den
    tatsächlich aktuellen (Checkpoint-)Status published (siehe
    post_seen())."""
    status, snap = get(f"/thread/{thread_id}?session_id={session_id}")
    assert status == 200
    assert snap["status"] == "result", f"erwartet 'result' vor /seen, bekam {snap['status']}"

    baseline = len(listener.events) - 1
    status, body = post(f"/thread/{thread_id}/seen", {"session_id": session_id})
    assert status == 200, f"POST /seen fehlgeschlagen: {status} {body}"

    idx_idle, _ = listener.wait_for_after(
        "status_changed", baseline, thread_id=thread_id, status="idle", timeout=10.0
    )
    print(f"[ok] /seen: status_changed 'idle' empfangen (#{idx_idle})")

    status, snap = get(f"/thread/{thread_id}?session_id={session_id}")
    assert status == 200
    assert snap["status"] == "idle", f"erwartet 'idle' nach /seen, bekam {snap['status']}"
    print("[ok] GET /thread bestätigt 'idle' nach /seen")


def test_mehrere_anfragen_result_gleichzeitig_in_session_snapshot(session_id: str, listener: SSEListener) -> None:
    """Zwei Anfragen derselben Session erreichen unabhängig voneinander
    'result', OHNE dass eine davon per /seen quittiert wird - GET /session
    muss BEIDE korrekt zeigen, nicht nur die zuletzt aktive (siehe Bericht
    an die Nutzerin: 'result' gilt pro Anfrage, das Backend kürt keinen
    Gewinner - welcher Zustand am peripheren Punkt sichtbar wird, ist eine
    Frontend-Entscheidung)."""
    status, a = post(f"/session/{session_id}/anfrage")
    assert status == 200
    thread_a = a["thread_id"]
    status, body = post(f"/message/{thread_a}", {"session_id": session_id, "text": "Wie beantrage ich Urlaub?"})
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"
    listener.wait_for_after("status_changed", -1, thread_id=thread_a, status="result", timeout=30.0)

    status, b = post(f"/session/{session_id}/anfrage")
    assert status == 200
    thread_b = b["thread_id"]
    status, body = post(f"/message/{thread_b}", {"session_id": session_id, "text": "Wie beantrage ich Urlaub?"})
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"
    listener.wait_for_after("status_changed", -1, thread_id=thread_b, status="result", timeout=30.0)

    status, snap = get(f"/session/{session_id}")
    assert status == 200
    statuses = {row["thread_id"]: row["status"] for row in snap["anfragen"]}
    assert statuses.get(thread_a) == "result", f"Anfrage A nicht als 'result' im Session-Snapshot: {statuses}"
    assert statuses.get(thread_b) == "result", f"Anfrage B nicht als 'result' im Session-Snapshot: {statuses}"
    print(f"[ok] GET /session zeigt beide Anfragen unabhängig als 'result': {thread_a[:8]}…, {thread_b[:8]}…")


def test_interrupt_raised_geloggt_kein_duplikat_bei_resume(session_id: str, listener: SSEListener) -> None:
    """(1) LOGGING-LÜCKE: ein frisch ausgelöster, noch nicht bestätigter
    Interrupt hinterlässt jetzt einen "interrupt_raised"-Eintrag in
    interaction_log.jsonl - VOR der Bestätigung, nicht erst danach. Und beim
    Resume darf KEIN zweiter Eintrag entstehen. Kein state-Dedup mehr nötig:
    announce_confirmation_node (graph.py) läuft als eigener, VOR dem
    interrupt() abgeschlossener Graph-Schritt und wird deshalb bei einem
    Resume nicht erneut durchlaufen (siehe dortiger Docstring). Liest die
    Logdatei direkt (stdlib, kein Test-Only-Endpoint nötig) - nur
    aussagekräftig, wenn Server und Testskript denselben
    interaction_log.jsonl-Pfad sehen (lokaler Lauf, siehe LOG_PATH)."""
    thread_id, interrupt_event = _start_anfrage_and_wait_for_interrupt(
        session_id, listener, "Ich brauche VPN-Zugang, kannst du das einrichten?"
    )

    entries = _read_log_entries()
    raised_before = [
        e for e in entries
        if e.get("category") == "interrupt_raised" and e.get("session_id") == thread_id
    ]
    assert len(raised_before) == 1, (
        f"erwartet genau 1 'interrupt_raised'-Eintrag für thread_id={thread_id} "
        f"VOR der Bestätigung, gefunden: {len(raised_before)}"
    )
    assert raised_before[0].get("proposal", {}).get("tool") == "create_ticket", raised_before[0]
    print(f"[ok] interrupt_raised geloggt VOR Bestätigung: {raised_before[0]['proposal']['tool']}")

    options = interrupt_event["options"]
    confirm_option = next(
        (o for o in options if "bestätig" in o.lower() and "trotzdem" not in o.lower()), None
    )
    assert confirm_option, f"keine Bestätigungs-Option in {options} gefunden"

    status, body = post(f"/resume/{thread_id}", {"session_id": session_id, "decision": confirm_option})
    assert status == 200, f"POST /resume fehlgeschlagen: {status} {body}"

    listener.wait_for("interrupt_resolved", thread_id=thread_id, timeout=30.0)
    listener.wait_for("message_appended", thread_id=thread_id, timeout=30.0)

    entries_after = _read_log_entries()
    raised_after = [
        e for e in entries_after
        if e.get("category") == "interrupt_raised" and e.get("session_id") == thread_id
    ]
    assert len(raised_after) == 1, (
        f"erwartet weiterhin genau 1 'interrupt_raised'-Eintrag NACH dem Resume "
        f"(kein Duplikat durch Replay) für thread_id={thread_id}, gefunden: {len(raised_after)}"
    )
    confirm_entries = [
        e for e in entries_after
        if e.get("category") == "confirm" and e.get("node") == "human_review"
        and e.get("session_id") == thread_id
    ]
    assert len(confirm_entries) == 1, f"erwartet genau 1 'confirm'-Eintrag: {confirm_entries}"
    print("[ok] kein doppelter interrupt_raised-Eintrag nach Resume, genau 1 confirm-Eintrag")


def test_ablehnung_kein_zweites_message_appended(session_id: str, listener: SSEListener) -> None:
    """(b) ABLEHNUNG, wichtigerer Fall: nach POST /resume mit Ablehnung
    kommt interrupt_resolved und danach DIREKT status_changed "idle" -
    NICHT "result" (siehe Bericht an die Nutzerin: ein Abschluss ohne neue
    Nachricht bekommt kein peripheres Signal, sonst wäre es eine leere
    Benachrichtigung genau gegen den Calm-Technology-Grundsatz) -, OHNE
    zweites message_appended. Prüft AKTIV die Abwesenheit einer weiteren
    Nachricht (Zeitfenster zwischen den beiden Events UND eine kurze
    Nachbeobachtung danach) - nicht nur, dass irgendwann "idle" erscheint.
    Wenn das Frontend nach interrupt_resolved auf eine Nachricht wartet,
    hängt es bei jeder Ablehnung - das soll dieser Test aufdecken."""
    thread_id, interrupt_event = _start_anfrage_and_wait_for_interrupt(
        session_id, listener, "Ich brauche einen neuen Laptop, kannst du das einrichten?"
    )
    options = interrupt_event["options"]
    reject_option = next((o for o in options if "ablehn" in o.lower()), None)
    assert reject_option, f"keine Ablehnungs-Option in {options} gefunden"

    appended_before = len(listener.all_of("message_appended", thread_id=thread_id))
    assert appended_before == 1, f"erwartet genau 1 message_appended (Vorschlag) vor /resume, bekam {appended_before}"

    # -1-Offset: after_index ist der Index des LETZTEN bereits bekannten
    # Events (len(events) selbst wäre der Index, den das NÄCHSTE Event
    # bekommt, und würde durch "idx <= after_index" fälschlich mit
    # ausgeschlossen - siehe wait_for_after()).
    baseline = len(listener.events) - 1
    status, body = post(f"/resume/{thread_id}", {"session_id": session_id, "decision": reject_option})
    assert status == 200, f"POST /resume fehlgeschlagen: {status} {body}"

    idx_resolved, _ = listener.wait_for_after("interrupt_resolved", baseline, thread_id=thread_id, timeout=30.0)
    idx_idle, _ = listener.wait_for_after(
        "status_changed", idx_resolved, thread_id=thread_id, status="idle", timeout=30.0
    )

    # Aktive Prüfung 1: zwischen interrupt_resolved und idle darf KEIN
    # message_appended für diese Anfrage liegen.
    between = [
        e for idx, e in enumerate(listener.events)
        if idx_resolved < idx < idx_idle
        and e.get("type") == "message_appended"
        and e.get("thread_id") == thread_id
    ]
    assert not between, f"message_appended zwischen interrupt_resolved und idle gefunden: {between}"

    # Aktive Prüfung 2: kurze Nachbeobachtung, falls doch noch verzögert
    # etwas nachkäme (reines "idle wurde erreicht" reicht nicht als Beweis,
    # dass NICHTS mehr kommt).
    time.sleep(2)
    appended_after = listener.all_of("message_appended", thread_id=thread_id)
    assert len(appended_after) == appended_before, (
        f"nach Ablehnung ist trotzdem eine weitere Nachricht gekommen: "
        f"vorher {appended_before}, jetzt {len(appended_after)}: {appended_after}"
    )
    print(
        f"[ok] Ablehnung: interrupt_resolved(#{idx_resolved}) -> idle(#{idx_idle}) direkt, "
        f"kein zweites message_appended (auch nicht nach 2s Nachbeobachtung)"
    )


def test_wissensdatenbank_durchsucht_mit_quelle(session_id: str, listener: SSEListener) -> None:
    """(A1) Organisatorische Frage im Zuständigkeitsbereich -> info_agent ->
    search_documents. rationale.steps muss einen "Wissensdatenbank
    durchsucht"-Schritt enthalten UND mind. einer davon muss eine gefüllte
    source (Titel+Pfad) tragen. Ein Schritt OHNE source (durchgeführte, aber
    ergebnislose Suche) zählt hier ausdrücklich als TEILERFOLG, nicht als
    Erfolg - die Quellenangabe ist das eigentlich nachprüfbare Element,
    siehe Auftrag."""
    status, body = post(f"/session/{session_id}/anfrage")
    assert status == 200
    thread_id = body["thread_id"]

    status, body = post(f"/message/{thread_id}", {"session_id": session_id, "text": "Wie beantrage ich Urlaub?"})
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"

    message_event = listener.wait_for("message_appended", thread_id=thread_id, timeout=30.0)
    rationale = message_event.get("rationale")
    assert rationale is not None, "keine rationale (transparency_level?)"
    steps = rationale["steps"]

    search_steps = [s for s in steps if s["label"] == "Wissensdatenbank durchsucht"]
    assert search_steps, (
        f"kein 'Wissensdatenbank durchsucht'-Schritt gefunden - Ableitung greift "
        f"nicht (oder die Frage wurde nicht als 'info' kategorisiert): {steps}"
    )

    with_source = [s for s in search_steps if s.get("source") and s["source"].get("title")]
    without_source = [s for s in search_steps if s not in with_source]
    if without_source and not with_source:
        raise AssertionError(
            f"TEILERFOLG, kein Erfolg: 'Wissensdatenbank durchsucht' kam vor, aber "
            f"OHNE source (Titel/Pfad) - die Suche lief, fand aber nichts oder die "
            f"source-Befüllung ist kaputt: {without_source}"
        )
    assert with_source, f"kein Schritt mit befüllter source gefunden: {search_steps}"
    source = with_source[0]["source"]
    assert source.get("title") and source.get("path"), f"source unvollständig (Titel/Pfad fehlt): {source}"
    print(f"[ok] Wissensdatenbank durchsucht MIT Quelle: {source}")


def test_eskalation_an_passende_person(session_id: str, listener: SSEListener) -> None:
    """(A2) Frage außerhalb der Zuständigkeit -> escalate_node.
    rationale.steps muss einen "An <Person> übergeben"-Schritt enthalten,
    und die Person muss zum Thema passen (hier: Gehaltsfrage -> HR/Anna
    Schmidt, siehe colleague_data.py). Hinweis: die Kategorisierung
    ('other' statt 'info'/'infrastructure'/'scheduling') liegt beim LLM
    und ist nicht 100% deterministisch wie jeder Test, der auf einer
    LLM-Entscheidung aufbaut."""
    status, body = post(f"/session/{session_id}/anfrage")
    assert status == 200
    thread_id = body["thread_id"]

    status, body = post(
        f"/message/{thread_id}",
        {"session_id": session_id, "text": "Ich habe eine Frage zu meinem Gehalt, kannst du mir dabei helfen?"},
    )
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"

    message_event = listener.wait_for("message_appended", thread_id=thread_id, timeout=30.0)
    rationale = message_event.get("rationale")
    assert rationale is not None, "keine rationale (transparency_level?)"
    steps = rationale["steps"]

    handoff_steps = [s for s in steps if s["label"].startswith("An ") and s["label"].endswith("übergeben")]
    assert handoff_steps, (
        f"kein 'An <Person> übergeben'-Schritt gefunden - entweder wurde die "
        f"Frage nicht als 'other' kategorisiert (LLM-Entscheidung), oder "
        f"find_colleague_for_topic() fand niemanden zum Teilschritt-Text: {steps}"
    )
    step = handoff_steps[0]
    passt_zum_thema = "HR" in (step.get("detail") or "") or "Anna" in step["label"]
    assert passt_zum_thema, f"Übergabe-Schritt passt nicht zum Thema Gehalt (erwartet HR/Anna Schmidt): {step}"
    print(f"[ok] Eskalation an passende Person: {step['label']} ({step.get('detail')})")


def test_medium_unterscheidet_ticket_und_kalender(session_id: str, listener: SSEListener) -> None:
    """(3) human_review_node berücksichtigt jetzt is_critical
    (_human_review_needs_interrupt in graph.py), DEFAULT_CONTROL_LEVEL ist
    "medium" - die Studienbedingung. Prüft NICHT nur jeden Fall für sich,
    sondern den KONTRAST: dieselbe Session, control_level="medium", zwei
    Anfragen unterschiedlicher Kritikalität - das eine wartet, das andere
    nicht.

      - create_ticket (is_critical=True)       -> Bestätigungskarte (waiting)
      - add_calendar_event (is_critical=False) -> autonomer Durchlauf, KEIN
        interrupt, human_review_node nimmt den autonomen Zweig.

    Prüft außerdem (statt anzunehmen), dass execute_action_node im
    autonomen Zweig GENAUSO die Bestätigungsnachricht + den
    Ausführungs-Rationale-Schritt erzeugt wie im bestätigten Zweig - siehe
    build_execution_rationale in rationale.py, die nur von
    state["last_executed_action"] abhängt, nicht davon, wie execute_action
    erreicht wurde."""

    # --- Teil 1: create_ticket (kritisch) -> muss weiterhin warten ---
    thread_id_ticket, interrupt_event = _start_anfrage_and_wait_for_interrupt(
        session_id, listener, "Ich brauche einen VPN-Zugang, kannst du das einrichten?"
    )
    ticket_is_critical = interrupt_event["proposal"]["is_critical"]
    assert ticket_is_critical == EXPECTED_TOOL_CRITICALITY["create_ticket"], (
        f"is_critical für create_ticket weicht von der Policy ab: "
        f"erwartet {EXPECTED_TOOL_CRITICALITY['create_ticket']}, bekam {ticket_is_critical}"
    )
    print(f"[ok] create_ticket (kritisch) wartet bei control_level=medium auf Bestätigung")

    options = interrupt_event["options"]
    confirm_option = next(
        (o for o in options if "bestätig" in o.lower() and "trotzdem" not in o.lower()), None
    )
    assert confirm_option, f"keine Bestätigungs-Option in {options} gefunden"
    status, body = post(f"/resume/{thread_id_ticket}", {"session_id": session_id, "decision": confirm_option})
    assert status == 200, f"POST /resume fehlgeschlagen: {status} {body}"
    listener.wait_for("interrupt_resolved", thread_id=thread_id_ticket, timeout=30.0)
    listener.wait_for("message_appended", thread_id=thread_id_ticket, timeout=30.0)

    # --- Teil 2: add_calendar_event (unkritisch) -> darf NICHT mehr warten ---
    status, body = post(f"/session/{session_id}/anfrage")
    assert status == 200
    thread_id_calendar = body["thread_id"]

    status, body = post(
        f"/message/{thread_id_calendar}",
        {"session_id": session_id, "text": "Kannst du am Donnerstag um 14 Uhr ein Team-Meeting in meinen Kalender eintragen?"},
    )
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"

    # Sync-Punkt: warten, bis überhaupt etwas passiert ist, bevor unten per
    # GET /thread gepollt wird (sonst evtl. Poll, bevor der Hintergrund-Lauf
    # überhaupt gestartet ist).
    listener.wait_for("message_appended", thread_id=thread_id_calendar, timeout=30.0)

    # "result", nicht "idle": es WURDE eine neue Nachricht angehängt (die
    # Ausführungsbestätigung), siehe Bericht an die Nutzerin.
    deadline = time.time() + 30
    status, snap = get(f"/thread/{thread_id_calendar}?session_id={session_id}")
    while snap["status"] != "result" and time.time() < deadline:
        time.sleep(0.3)
        status, snap = get(f"/thread/{thread_id_calendar}?session_id={session_id}")
    assert snap["status"] == "result", (
        f"erwartet autonomer Durchlauf bis 'result' für add_calendar_event bei "
        f"control_level=medium (is_critical=False), bekam {snap['status']}"
    )
    assert snap["interrupt"] is None, "add_calendar_event hat trotzdem einen interrupt hinterlassen"
    print("[ok] add_calendar_event (unkritisch) läuft bei control_level=medium autonom durch, keine Bestätigungskarte")

    execution_messages = [
        m for m in snap["messages"]
        if m.get("rationale") and any(s["label"] == "Termin eingetragen" for s in m["rationale"]["steps"])
    ]
    assert execution_messages, (
        "autonomer Kalender-Durchlauf hat KEINEN 'Termin eingetragen'-"
        "Ausführungsschritt in der Historie - die Rückmeldung fehlt genau "
        "dort, wo nicht bestätigt wurde"
    )
    confirmation_text = execution_messages[-1]["content"]
    assert "eingetragen" in confirmation_text.lower(), (
        f"Bestätigungstext im autonomen Zweig unerwartet: {confirmation_text!r}"
    )
    print(f"[ok] autonomer Zweig erzeugt trotzdem Bestätigungstext + Ausführungs-Rationale: {confirmation_text!r}")

    # --- Kontrast, explizit: nicht nur jeden Fall einzeln, sondern dass sie
    # sich UNTERSCHIEDLICH verhalten (dieselbe Session, dieselbe
    # control_level="medium"-Konfiguration). ---
    ticket_had_interrupt = True  # sonst wäre _start_anfrage_and_wait_for_interrupt oben bereits gescheitert
    calendar_had_interrupt = snap["interrupt"] is not None
    assert ticket_had_interrupt and not calendar_had_interrupt, (
        f"kein Kontrast beobachtet: ticket_had_interrupt={ticket_had_interrupt}, "
        f"calendar_had_interrupt={calendar_had_interrupt} - erwartet war ein "
        f"Unterschied zwischen kritisch (Ticket, muss warten) und "
        f"unkritisch (Kalender, darf nicht warten)"
    )
    print("[ok] Kontrast bestätigt: create_ticket wartet bei medium, add_calendar_event nicht")


def _wait_for_calendar_turn_to_settle(session_id: str, thread_id: str) -> dict:
    deadline = time.time() + 30
    status, snap = get(f"/thread/{thread_id}?session_id={session_id}")
    while snap["status"] not in ("result", "error") and time.time() < deadline:
        time.sleep(0.3)
        status, snap = get(f"/thread/{thread_id}?session_id={session_id}")
    assert status == 200
    return snap


def test_kalender_normalisierung_mehrere_formulierungen(session_id: str, listener: SSEListener) -> None:
    """Kalender-Normalisierung mit mehreren natürlichsprachlichen
    Formulierungen (siehe Bericht an die Nutzerin): das Modell übernimmt
    die Umrechnung auf weekday (0-4)/hour (volle Stunde 8-16), keine
    Parsing-Schicht im Frontend. add_calendar_event ist unkritisch
    (control_level=medium), läuft also autonom durch - direkt auf
    'result' gepollt, kein /resume nötig.

    "Dienstag halb drei" und "morgen früh um 9" sind mit der festen
    'heute'-Referenz (Mittwoch, SANDBOX_TODAY_DESCRIPTION in graph.py)
    eindeutig INNERHALB der Woche und werden deterministisch geprüft
    (weekday/hour exakt, UND dass die Bestätigung den aufgelösten/
    gerundeten Zeitpunkt tatsächlich nennt). "nächsten Donnerstag" ist im
    Deutschen echt zweideutig (diese oder nächste Woche) - dafür nur
    strukturelle Konsistenz geprüft, kein bestimmter Ausgang erzwungen,
    dieselbe Vorsicht wie bei jedem Test, der auf einer LLM-Entscheidung
    aufbaut (siehe test_eskalation_an_passende_person). "in drei Wochen"
    ist eindeutig AUSSERHALB der Woche und wird deshalb deterministisch
    auf die Wochen-Grenzen-Erklärung geprüft (Guideline: darf nicht wie
    ein technischer Fehler klingen)."""

    # --- "Dienstag halb drei" - eindeutig in der Woche, Rundung nötig ---
    status, body = post(f"/session/{session_id}/anfrage")
    assert status == 200
    thread_id = body["thread_id"]
    status, body = post(
        f"/message/{thread_id}",
        {"session_id": session_id, "text": "Kannst du am Dienstag halb drei ein kurzes Sync-Meeting eintragen?"},
    )
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"
    listener.wait_for("message_appended", thread_id=thread_id, timeout=30.0)
    snap = _wait_for_calendar_turn_to_settle(session_id, thread_id)
    assert snap["status"] == "result", f"erwartet 'result' für eindeutig-in-Woche-Termin, bekam {snap['status']}: {snap}"
    execution_messages = [
        m for m in snap["messages"]
        if m.get("rationale") and any(s["label"] == "Termin eingetragen" for s in m["rationale"]["steps"])
    ]
    assert execution_messages, f"kein Ausführungsschritt für 'Dienstag halb drei': {snap['messages']}"
    confirmation_text = execution_messages[-1]["content"]
    assert "Dienstag" in confirmation_text, f"Bestätigungstext nennt nicht 'Dienstag': {confirmation_text!r}"
    assert "14:00" in confirmation_text or "15:00" in confirmation_text, (
        f"Bestätigungstext nennt nicht die gerundete Uhrzeit (14:00 oder 15:00): {confirmation_text!r}"
    )
    print(f"[ok] 'Dienstag halb drei' -> {confirmation_text!r}")

    # --- "morgen früh um 9" - eindeutig in der Woche (heute=Mittwoch -> morgen=Donnerstag) ---
    status, body = post(f"/session/{session_id}/anfrage")
    assert status == 200
    thread_id2 = body["thread_id"]
    status, body = post(
        f"/message/{thread_id2}",
        {"session_id": session_id, "text": "Trag mir bitte morgen früh um 9 ein Standup ein."},
    )
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"
    listener.wait_for("message_appended", thread_id=thread_id2, timeout=30.0)
    snap2 = _wait_for_calendar_turn_to_settle(session_id, thread_id2)
    assert snap2["status"] == "result", f"erwartet 'result' für 'morgen früh um 9', bekam {snap2['status']}: {snap2}"
    execution_messages2 = [
        m for m in snap2["messages"]
        if m.get("rationale") and any(s["label"] == "Termin eingetragen" for s in m["rationale"]["steps"])
    ]
    # "heute" wird zur LAUFZEIT ermittelt (siehe Bericht an die Nutzerin) -
    # der Test muss dieselbe Rechnung unabhängig nachvollziehen, nicht eine
    # feste Erwartung annehmen. today_weekday>=4 deckt Freitag (morgen=
    # Samstag, nicht darstellbar), Samstag und Sonntag (heute selbst nicht
    # darstellbar) einheitlich ab.
    today_weekday = datetime.date.today().weekday()  # 0=Montag ... 6=Sonntag
    if today_weekday >= 4:
        assert not execution_messages2, (
            f"'morgen früh um 9' hätte an diesem Wochentag (Index {today_weekday}, "
            f"morgen ist Wochenende oder heute selbst ist bereits Wochenende) keinen "
            f"Eintrag erzeugen dürfen: {snap2['messages']}"
        )
        proposal_messages2 = [m for m in snap2["messages"] if m["role"] == "assistant"]
        assert proposal_messages2, f"keine Antwort für 'morgen früh um 9' erhalten: {snap2}"
        print(
            f"[ok] 'morgen früh um 9' korrekt als nicht darstellbar erkannt "
            f"(heute-Wochentag-Index={today_weekday}): {proposal_messages2[0]['content']!r}"
        )
    else:
        assert execution_messages2, f"kein Ausführungsschritt für 'morgen früh um 9': {snap2['messages']}"
        confirmation_text2 = execution_messages2[-1]["content"]
        expected_day_name = WEEKDAY_NAMES[today_weekday + 1]
        assert expected_day_name in confirmation_text2, (
            f"Bestätigungstext nennt nicht '{expected_day_name}' (heute="
            f"{WEEKDAY_NAMES[today_weekday]} -> morgen={expected_day_name}): {confirmation_text2!r}"
        )
        assert "09:00" in confirmation_text2, f"Bestätigungstext nennt nicht 09:00: {confirmation_text2!r}"
        print(f"[ok] 'morgen früh um 9' -> {confirmation_text2!r}")

    # --- "nächsten Donnerstag um 14 Uhr" - echt zweideutig, nur strukturelle
    # Konsistenz geprüft, kein bestimmter Ausgang erzwungen. ---
    status, body = post(f"/session/{session_id}/anfrage")
    assert status == 200
    thread_id3 = body["thread_id"]
    status, body = post(
        f"/message/{thread_id3}",
        {"session_id": session_id, "text": "Kannst du nächsten Donnerstag um 14 Uhr ein Meeting mit dem Team eintragen?"},
    )
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"
    listener.wait_for("message_appended", thread_id=thread_id3, timeout=30.0)
    snap3 = _wait_for_calendar_turn_to_settle(session_id, thread_id3)
    assert snap3["status"] == "result", f"erwartet 'result', bekam {snap3['status']}: {snap3}"
    execution_messages3 = [
        m for m in snap3["messages"]
        if m.get("rationale") and any(s["label"] == "Termin eingetragen" for s in m["rationale"]["steps"])
    ]
    if execution_messages3:
        confirmation_text3 = execution_messages3[-1]["content"]
        assert any(day in confirmation_text3 for day in WEEKDAY_NAMES), (
            f"Ausführungs-Bestätigung ohne erkennbaren Wochentag: {confirmation_text3!r}"
        )
        print(f"[ok] 'nächsten Donnerstag um 14 Uhr' als DIESE Woche interpretiert -> {confirmation_text3!r}")
    else:
        proposal_messages3 = [m for m in snap3["messages"] if m["role"] == "assistant"]
        assert proposal_messages3, f"keine Antwort für 'nächsten Donnerstag' erhalten: {snap3}"
        explanation = proposal_messages3[0]["content"]
        assert "Woche" in explanation, f"Erklärung erwähnt nicht die Wochen-Grenze des Prototyps: {explanation!r}"
        # KEIN Blocklist-Check auf Wörter wie "Störung"/"Fehler": ein
        # Substring-Check kann Negation nicht erkennen ("keine Störung" ist
        # GENAU die gewünschte Formulierung, würde aber denselben Treffer
        # wie "das ist eine Störung" liefern) - siehe Bericht an die
        # Nutzerin, ein echter Fund an genau dieser Stelle. Ob es sich wie
        # eine bewusste Grenze statt ein Defekt anhört, ist eine
        # Tonalitätsfrage, keine Keyword-Frage - der ausgedruckte Text ist
        # hier die eigentliche Prüfung, nicht ein Assert.
        print(f"[ok] 'nächsten Donnerstag um 14 Uhr' als AUSSERHALB der Woche interpretiert -> {explanation!r}")

    # --- "in drei Wochen" - eindeutig AUSSERHALB der Woche, deterministisch
    # geprüft (im Gegensatz zu 'nächsten Donnerstag' oben). ---
    status, body = post(f"/session/{session_id}/anfrage")
    assert status == 200
    thread_id4 = body["thread_id"]
    status, body = post(
        f"/message/{thread_id4}",
        {"session_id": session_id, "text": "Kannst du in drei Wochen einen Termin für ein Feedbackgespräch eintragen?"},
    )
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"
    listener.wait_for("message_appended", thread_id=thread_id4, timeout=30.0)
    snap4 = _wait_for_calendar_turn_to_settle(session_id, thread_id4)
    assert snap4["status"] == "result", f"erwartet 'result', bekam {snap4['status']}: {snap4}"

    execution_messages4 = [
        m for m in snap4["messages"]
        if m.get("rationale") and any(s["label"] == "Termin eingetragen" for s in m["rationale"]["steps"])
    ]
    assert not execution_messages4, (
        f"'in drei Wochen' hat trotzdem einen Kalendereintrag erzeugt - within_current_week "
        f"greift nicht: {snap4['messages']}"
    )
    proposal_messages4 = [m for m in snap4["messages"] if m["role"] == "assistant"]
    assert proposal_messages4, f"keine Antwort für 'in drei Wochen' erhalten: {snap4}"
    explanation4 = proposal_messages4[0]["content"]
    assert "Woche" in explanation4, f"Erklärung erwähnt nicht die Wochen-Grenze des Prototyps: {explanation4!r}"
    # Kein Blocklist-Check hier - siehe Begründung beim 'nächsten
    # Donnerstag'-Fall oben (Negation, z.B. "keine Störung", ist per
    # Substring-Match nicht von einer echten Fehlermeldung unterscheidbar).
    print(f"[ok] 'in drei Wochen' korrekt außerhalb der Woche erkannt, kein Eintrag: {explanation4!r}")


def test_context_trennung(session_id: str) -> None:
    """Zwei Anfragen derselben Session sind kontextgetrennt."""
    status, a = post(f"/session/{session_id}/anfrage")
    thread_a = a["thread_id"]
    status, r = post(f"/message/{thread_a}", {"session_id": session_id, "text": "Mein Lieblingscode-Wort ist Zimtstern."})
    assert status == 200
    time.sleep(8)  # Antwort abwarten (kein Event-Listener hier, bewusst simpel gehalten)

    status, b = post(f"/session/{session_id}/anfrage")
    thread_b = b["thread_id"]
    status, snap = get(f"/thread/{thread_b}?session_id={session_id}")
    assert snap["messages"] == [], "neue Anfrage hat bereits Nachrichten - Kontext nicht getrennt"
    print("[ok] neue Anfrage startet mit leerer Historie (Kontexttrennung strukturell durch eigene thread_id gegeben)")


def test_vorschlag_faellt_aus_wenn_anfrage_laeuft_kontrast_zu_ruhiger_session() -> None:
    """SCHREIBZEIT-Vorrang, als KONTRAST geprüft, nicht nur als Abwesenheit
    (siehe Bericht an die Nutzerin: eine reine Abwesenheits-Prüfung wäre
    auch dann grün, wenn Vorschläge grundsätzlich nicht funktionieren -
    genau das Muster, an dem der ursprüngliche G13-Zwei-Subtask-Test schon
    einmal scheiterte). Zwei VERSCHIEDENE Screens in derselben Session,
    damit "bereits vorgeschlagen" die beiden Fälle nicht vermischt: Teil 1
    (ruhige Session) MUSS einen Vorschlag auslösen, Teil 2 (Anfrage läuft)
    MUSS ausfallen."""
    _, session = post("/session", {"access_code": ACCESS_CODE})
    sid = session["session_id"]
    own_listener = SSEListener(sid)
    own_listener.start()

    # Teil 1: RUHIGE Session -> Vorschlag MUSS tatsächlich ankommen.
    baseline = len(own_listener.events) - 1
    status, body = post(f"/session/{sid}/screen", {"screen": "calendar"})
    assert status == 200, f"POST /screen fehlgeschlagen: {status} {body}"
    idx_suggestion, event = own_listener.wait_for_after(
        "status_changed", baseline, status="suggestion", session_scoped=True, timeout=10.0
    )
    assert event["screen"] == "calendar"
    print(f"[ok] Vorschlag kommt in ruhiger Session tatsächlich an (#{idx_suggestion}): {event['text']!r}")

    # Anfrage aktiv werden lassen (VPN-Ticket, wartet auf Bestätigung).
    thread_id, _ = _start_anfrage_and_wait_for_interrupt(
        sid, own_listener, "Ich brauche einen VPN-Zugang, kannst du das einrichten?"
    )

    # Teil 2: ANDERER Screen, Session jetzt NICHT ruhig -> fällt aus.
    baseline2 = len(own_listener.events) - 1
    status, body = post(f"/session/{sid}/screen", {"screen": "tickets"})
    assert status == 200, f"POST /screen fehlgeschlagen: {status} {body}"

    # Aktive Prüfung (nicht nur "kam nichts rechtzeitig"): kurze
    # Nachbeobachtung, dann Abwesenheit direkt geprüft - gleiches Prinzip
    # wie test_ablehnung_kein_zweites_message_appended.
    time.sleep(2)
    suggestion_events = [
        e for idx, e in enumerate(own_listener.events)
        if idx > baseline2 and e.get("type") == "status_changed" and e.get("status") == "suggestion"
    ]
    assert not suggestion_events, f"Vorschlag wurde trotz laufender Anfrage ausgelöst: {suggestion_events}"

    # Auch der VORHER gesetzte 'calendar'-Vorschlag muss jetzt unterdrückt
    # sein (Lesezeit-Vorrang greift ebenfalls, siehe eigener Test dafür).
    status, snap = get(f"/session/{sid}")
    assert status == 200
    assert snap.get("pending_suggestion") is None, (
        f"pending_suggestion sichtbar, obwohl eine Anfrage der Session läuft/wartet: {snap}"
    )
    print("[ok] Vorschlag fällt aus (Schreibzeit), solange eine Anfrage der Session läuft/wartet - im Kontrast zu Teil 1")

    own_listener.stop()


def test_vorschlag_wird_bei_laufender_anfrage_lesezeitig_unterdrueckt_und_kehrt_zurueck() -> None:
    """LESEZEIT-Vorrang - der wichtigere der beiden Fälle (siehe Bericht
    an die Nutzerin): ein BEREITS gesetzter Vorschlag wird unterdrückt,
    sobald DANACH irgendwo in der Session eine Anfrage aktiv wird - auch
    OHNE dass /seen je aufgerufen wurde. Prüft zusätzlich, dass die
    Unterdrückung reversibel ist (die gespeicherte Spalte wird nicht
    gelöscht, nur die ANZEIGE unterdrückt): sobald die andere Anfrage
    wieder ruht, taucht derselbe Vorschlag unverändert wieder auf - genau
    die Bedingung, die bei einem naiven Umbau (z.B. "Override beim Start
    eines Laufs überall löschen") still verschwinden würde."""
    _, session = post("/session", {"access_code": ACCESS_CODE})
    sid = session["session_id"]
    own_listener = SSEListener(sid)
    own_listener.start()

    baseline = len(own_listener.events) - 1
    status, body = post(f"/session/{sid}/screen", {"screen": "hub"})
    assert status == 200, f"POST /screen fehlgeschlagen: {status} {body}"

    idx_suggestion, event = own_listener.wait_for_after(
        "status_changed", baseline, status="suggestion", session_scoped=True, timeout=10.0
    )
    assert event["screen"] == "hub"
    assert event["text"] == SUGGESTION_TEXTS["hub"]["displayed"]
    print(f"[ok] Vorschlag erscheint (#{idx_suggestion}): {event['text']!r}")

    status, snap = get(f"/session/{sid}")
    assert status == 200
    assert snap["pending_suggestion"] == {"screen": "hub", "text": SUGGESTION_TEXTS["hub"]["displayed"]}
    print("[ok] GET /session zeigt pending_suggestion konsistent zum Event")

    # Jetzt, OHNE /seen aufzurufen, eine andere Anfrage der Session aktiv
    # werden lassen.
    thread_id, interrupt_event = _start_anfrage_and_wait_for_interrupt(
        sid, own_listener, "Ich brauche einen VPN-Zugang, kannst du das einrichten?"
    )

    status, snap = get(f"/session/{sid}")
    assert status == 200
    assert snap["pending_suggestion"] is None, (
        f"pending_suggestion trotz laufender/wartender Anfrage sichtbar - "
        f"Lesezeit-Vorrang fehlt: {snap}"
    )
    print("[ok] pending_suggestion lesezeitig unterdrückt, solange die andere Anfrage wartet")

    # Anfrage auflösen (bestätigen) - Session wieder ruhig.
    confirm_option = next(
        (o for o in interrupt_event["options"] if "bestätig" in o.lower() and "trotzdem" not in o.lower()), None
    )
    assert confirm_option
    status, body = post(f"/resume/{thread_id}", {"session_id": sid, "decision": confirm_option})
    assert status == 200
    own_listener.wait_for("interrupt_resolved", thread_id=thread_id, timeout=30.0)
    own_listener.wait_for("message_appended", thread_id=thread_id, timeout=30.0)
    own_listener.wait_for_after("status_changed", -1, thread_id=thread_id, status="result", timeout=30.0)

    status, snap = get(f"/session/{sid}")
    assert status == 200
    assert snap["pending_suggestion"] == {"screen": "hub", "text": SUGGESTION_TEXTS["hub"]["displayed"]}, (
        f"Vorschlag ist nach Ruhe der Session nicht zurückgekehrt - die gespeicherte "
        f"Spalte wurde offenbar destruktiv gelöscht statt nur unterdrückt: {snap}"
    )
    print("[ok] Vorschlag taucht unverändert wieder auf, sobald die Session wieder ruhig ist")

    own_listener.stop()


def test_vorschlag_erscheint_klick_erzeugt_anfrage_seen_setzt_zurueck() -> None:
    """Kompletter Weg: Screen melden -> Vorschlag erscheint (Event + GET
    /session) -> ein zweites Melden desselben Screens bleibt wirkungslos
    (genau einmal pro Screen pro Session) -> /seen -> Klick (neue Anfrage
    + Nachricht mit suggestion_screen) -> suggestion_accepted geloggt ->
    normale Bearbeitung läuft an."""
    _, session = post("/session", {"access_code": ACCESS_CODE})
    sid = session["session_id"]
    own_listener = SSEListener(sid)
    own_listener.start()

    baseline = len(own_listener.events) - 1
    status, body = post(f"/session/{sid}/screen", {"screen": "intranet"})
    assert status == 200, f"POST /screen fehlgeschlagen: {status} {body}"

    idx_suggestion, event = own_listener.wait_for_after(
        "status_changed", baseline, status="suggestion", session_scoped=True, timeout=10.0
    )
    assert event["screen"] == "intranet"
    assert event["text"] == SUGGESTION_TEXTS["intranet"]["displayed"]

    log_entries = _read_log_entries()
    shown_entries = [
        e for e in log_entries
        if e.get("category") == "suggestion_shown" and e.get("api_session_id") == sid and e.get("screen") == "intranet"
    ]
    assert len(shown_entries) == 1, f"erwartet genau 1 'suggestion_shown'-Log-Eintrag: {shown_entries}"
    assert shown_entries[0].get("session_id") is None, (
        f"session_id-Feld sollte bei suggestion_shown None sein (kein thread_id vorhanden), "
        f"api_session_id trägt die eigentliche ID: {shown_entries[0]}"
    )
    print("[ok] suggestion_shown geloggt, session_id=None, api_session_id=Session-ID")

    # Zweite Meldung desselben Screens -> kein zweiter Vorschlag, kein
    # zweiter Log-Eintrag (genau einmal pro Screen pro Session).
    baseline2 = len(own_listener.events) - 1
    status, body = post(f"/session/{sid}/screen", {"screen": "intranet"})
    assert status == 200
    time.sleep(2)
    duplicate_events = [
        e for idx, e in enumerate(own_listener.events)
        if idx > baseline2 and e.get("type") == "status_changed" and e.get("status") == "suggestion"
    ]
    assert not duplicate_events, f"Vorschlag ein zweites Mal ausgelöst: {duplicate_events}"
    shown_entries_after = [
        e for e in _read_log_entries()
        if e.get("category") == "suggestion_shown" and e.get("api_session_id") == sid and e.get("screen") == "intranet"
    ]
    assert len(shown_entries_after) == 1, f"erwartet weiterhin genau 1 Eintrag (kein Duplikat): {shown_entries_after}"
    print("[ok] zweite Meldung desselben Screens bleibt wirkungslos (einmal pro Screen pro Session)")

    # Panel geöffnet -> /seen -> Dot zurück auf idle.
    status, body = post(f"/session/{sid}/seen")
    assert status == 200, f"POST /seen fehlgeschlagen: {status} {body}"
    own_listener.wait_for_after(
        "status_changed", idx_suggestion, status="idle", session_scoped=True, timeout=10.0
    )
    status, snap = get(f"/session/{sid}")
    assert status == 200
    assert snap.get("pending_suggestion") is None
    print("[ok] /seen setzt pending_suggestion zurück, status_changed('idle') published")

    # Klick: neue Anfrage + hinterlegter Text, suggestion_screen markiert.
    status, anfrage = post(f"/session/{sid}/anfrage")
    assert status == 200
    thread_id = anfrage["thread_id"]

    status, body = post(
        f"/message/{thread_id}",
        {
            "session_id": sid,
            "text": SUGGESTION_TEXTS["intranet"]["submitted"],
            "suggestion_screen": "intranet",
        },
    )
    assert status == 200, f"POST /message fehlgeschlagen: {status} {body}"

    accepted_entries = [
        e for e in _read_log_entries()
        if e.get("category") == "suggestion_accepted" and e.get("api_session_id") == sid and e.get("screen") == "intranet"
    ]
    assert len(accepted_entries) == 1, f"erwartet genau 1 'suggestion_accepted'-Log-Eintrag: {accepted_entries}"
    print("[ok] suggestion_accepted geloggt")

    own_listener.wait_for("message_appended", thread_id=thread_id, timeout=30.0)
    print("[ok] normale Bearbeitung läuft nach Klick an (message_appended für die neue Anfrage)")

    own_listener.stop()


def test_screen_meldung_chat_ist_stiller_noop_unbekannt_ist_422(session_id: str, listener: SSEListener) -> None:
    """'chat' ist eine gültige Screen-ID (Literal-Typ), aber ohne Eintrag
    in SUGGESTION_POLICY - stiller No-Op, kein Fehler (siehe Bericht an
    die Nutzerin: dort Hilfe anzubieten ergibt keinen Sinn, man ist
    ohnehin bei Lumi). Eine ECHT unbekannte Screen-ID ist dagegen ein
    Klientenfehler (Tippfehler/Bug) und wird mit 422 abgelehnt, nicht
    stillschweigend geschluckt."""
    baseline = len(listener.events) - 1
    status, body = post(f"/session/{session_id}/screen", {"screen": "chat"})
    assert status == 200, f"'chat' sollte akzeptiert werden (200), kein Fehler: {status} {body}"
    time.sleep(1)
    suggestion_events = [
        e for idx, e in enumerate(listener.events)
        if idx > baseline and e.get("type") == "status_changed" and e.get("status") == "suggestion"
    ]
    assert not suggestion_events, f"'chat' hat fälschlich einen Vorschlag ausgelöst: {suggestion_events}"
    print("[ok] 'chat': stiller No-Op, kein Vorschlag")

    status, body = post(f"/session/{session_id}/screen", {"screen": "does-not-exist"})
    assert status == 422, f"erwartet 422 für unbekannte Screen-ID, bekam {status}: {body}"
    print("[ok] unbekannte Screen-ID wird mit 422 abgelehnt (Pydantic Literal)")


def test_zwei_sessions_parallel() -> None:
    """Zwei Sessions senden gleichzeitig eine Nachricht: beide bekommen nur
    ihre eigenen Events, keine 'database is locked', Session A kann Session
    Bs thread_id nicht abrufen."""
    _, session_a = post("/session", {"access_code": ACCESS_CODE})
    _, session_b = post("/session", {"access_code": ACCESS_CODE})
    sid_a, sid_b = session_a["session_id"], session_b["session_id"]

    listener_a = SSEListener(sid_a)
    listener_b = SSEListener(sid_b)
    listener_a.start()
    listener_b.start()

    _, anfrage_a = post(f"/session/{sid_a}/anfrage")
    _, anfrage_b = post(f"/session/{sid_b}/anfrage")
    thread_a, thread_b = anfrage_a["thread_id"], anfrage_b["thread_id"]

    def send(session_id, thread_id, text):
        status, body = post(f"/message/{thread_id}", {"session_id": session_id, "text": text})
        assert status == 200, (status, body)

    t1 = threading.Thread(target=send, args=(sid_a, thread_a, "Session A: Wie beantrage ich Urlaub?"))
    t2 = threading.Thread(target=send, args=(sid_b, thread_b, "Session B: Wie trage ich ein Meeting ein?"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    listener_a.wait_for("message_appended", thread_id=thread_a, timeout=40)
    listener_b.wait_for("message_appended", thread_id=thread_b, timeout=40)

    # Isolation: Session A darf NIE ein Event mit thread_b sehen und umgekehrt.
    assert not listener_a.all_of("message_appended", thread_id=thread_b)
    assert not listener_b.all_of("message_appended", thread_id=thread_a)
    print("[ok] beide Sessions liefen parallel, keine Event-Vermischung")

    status, _ = get(f"/thread/{thread_b}?session_id={sid_a}")
    assert status == 404, f"Session A konnte fremde thread_id abrufen (status={status})"
    print("[ok] Session A kann Session Bs thread_id nicht abrufen (404)")

    listener_a.stop()
    listener_b.stop()


def test_sse_keepalive(session_id: str) -> None:
    """SSE-Stream übersteht 2 Minuten Leerlauf (Keepalive greift)."""
    print("[info] warte 130s auf Keepalive-Kommentare - das dauert bewusst etwas...")
    listener = SSEListener(session_id)
    listener.start()
    time.sleep(130)
    # Kein harter Assert möglich (Kommentarzeilen werden nicht in .events
    # gesammelt) - Erfolgskriterium: der Thread ist nach 130s noch am
    # Leben und wirft keine Exception (sonst wäre die Verbindung
    # serverseitig/durch einen Timeout gekappt worden).
    assert listener._thread.is_alive(), "SSE-Verbindung ist vor Ablauf der 130s abgebrochen"
    listener.stop()
    print("[ok] SSE-Verbindung hat 130s Leerlauf überstanden")


# --- Testlauf-Buchführung ---------------------------------------------------
# Jeder einzelne Testschritt darf fehlschlagen, ohne den ganzen Prozess (und
# damit z.B. eine noch offene SSE-Verbindung, die für spätere Diagnose
# nützlich sein kann) mitzureißen - siehe Bericht an die Nutzerin zur
# vorherigen Fehlersuche, bei der genau das den Client vorzeitig verschwinden
# ließ.

_results: list[tuple[str, bool, str]] = []


def _run_test(fn, *args, **kwargs):
    name = fn.__name__
    try:
        result = fn(*args, **kwargs)
        _results.append((name, True, ""))
        return result
    except Exception as exc:
        print(f"[FAIL] {name}: {exc!r}")
        _results.append((name, False, repr(exc)))
        return None


if __name__ == "__main__":
    session_id = _run_test(test_access_code)
    _run_test(test_preseeded_anfragen, session_id)

    listener = SSEListener(session_id)
    listener.start()

    thread_id = _run_test(test_neue_anfrage_und_titel, session_id, listener)
    _run_test(test_rationale, session_id, thread_id, listener)
    thread_id_bestaetigt = _run_test(test_bestaetigung_liefert_ausfuehrungs_schritt, session_id, listener)
    _run_test(test_seen_setzt_result_auf_idle_zurueck, session_id, thread_id_bestaetigt, listener)
    _run_test(test_mehrere_anfragen_result_gleichzeitig_in_session_snapshot, session_id, listener)
    _run_test(test_interrupt_raised_geloggt_kein_duplikat_bei_resume, session_id, listener)
    _run_test(test_ablehnung_kein_zweites_message_appended, session_id, listener)
    _run_test(test_wissensdatenbank_durchsucht_mit_quelle, session_id, listener)
    _run_test(test_eskalation_an_passende_person, session_id, listener)
    _run_test(test_medium_unterscheidet_ticket_und_kalender, session_id, listener)
    _run_test(test_kalender_normalisierung_mehrere_formulierungen, session_id, listener)
    _run_test(test_context_trennung, session_id)
    _run_test(test_screen_meldung_chat_ist_stiller_noop_unbekannt_ist_422, session_id, listener)
    listener.stop()

    _run_test(test_vorschlag_faellt_aus_wenn_anfrage_laeuft_kontrast_zu_ruhiger_session)
    _run_test(test_vorschlag_wird_bei_laufender_anfrage_lesezeitig_unterdrueckt_und_kehrt_zurueck)
    _run_test(test_vorschlag_erscheint_klick_erzeugt_anfrage_seen_setzt_zurueck)

    _run_test(test_zwei_sessions_parallel)

    # Separat am Ende, weil er bewusst >2 Minuten braucht.
    if os.getenv("RUN_KEEPALIVE_TEST", "0") == "1":
        _run_test(test_sse_keepalive, session_id)
    else:
        print("[info] Keepalive-Test übersprungen (RUN_KEEPALIVE_TEST=1 setzen, um ihn mitlaufen zu lassen)")

    print("\n=== Zusammenfassung ===")
    for name, ok, err in _results:
        marker = "[ok]  " if ok else "[FAIL]"
        suffix = f" - {err}" if err else ""
        print(f"{marker} {name}{suffix}")

    passed = sum(1 for _, ok, _ in _results if ok)
    failed_names = [name for name, ok, _ in _results if not ok]
    print(f"\n{passed}/{len(_results)} Schritte grün.")

    if failed_names:
        print(f"Fehlgeschlagen: {', '.join(failed_names)}")
        sys.exit(1)
    else:
        print("Alle Prüfungen durchgelaufen.")
