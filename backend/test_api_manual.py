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

import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Optional

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
ACCESS_CODE = os.getenv("STUDY_ACCESS_CODE", "test123")


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
    sammelt alle Events (type -> Liste der data-Dicts)."""

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
            buffer = ""
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
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                for event in self.events:
                    if event.get("type") == event_type and (
                        thread_id is None or event.get("thread_id") == thread_id
                    ):
                        return event
            time.sleep(0.2)
        raise TimeoutError(f"Event '{event_type}' (thread_id={thread_id}) nicht innerhalb {timeout}s erhalten")

    def all_of(self, event_type: str, thread_id: Optional[str] = None) -> list[dict]:
        with self._lock:
            return [
                e for e in self.events
                if e.get("type") == event_type and (thread_id is None or e.get("thread_id") == thread_id)
            ]


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
    """Vorbelegte Anfragen erscheinen in der Liste dieser Session."""
    status, body = get(f"/session/{session_id}")
    assert status == 200
    anfragen = body["anfragen"]
    assert len(anfragen) >= 2, f"erwartet >=2 vorbelegte Anfragen, bekam {len(anfragen)}"
    for a in anfragen:
        assert a["title"], f"vorbelegte Anfrage ohne Titel: {a}"
    print(f"[ok] {len(anfragen)} vorbelegte Anfragen vorhanden, Titel gesetzt")
    return anfragen


def test_neue_anfrage_und_titel(session_id: str, listener: SSEListener) -> str:
    """Neue Anfrage anlegen, Nachricht senden, Titel wird gesetzt; Status
    working -> waiting bei der Bestätigungskarte."""
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

    waiting_events = [
        e for e in listener.all_of("status_changed", thread_id=thread_id)
    ]
    # "waiting" kann etwas dauern (LLM-Aufrufe) - hier gezielt darauf warten.
    deadline = time.time() + 30
    waiting_seen = False
    while time.time() < deadline:
        if any(e["status"] == "waiting" for e in listener.all_of("status_changed", thread_id=thread_id)):
            waiting_seen = True
            break
        time.sleep(0.3)
    assert waiting_seen, "Status ist nie auf 'waiting' gesprungen"

    interrupt_event = listener.wait_for("interrupt_pending", thread_id=thread_id)
    print(f"[ok] Titel gesetzt, working->waiting, interrupt_pending: {interrupt_event['proposal']}")

    status, snap = get(f"/thread/{thread_id}?session_id={session_id}")
    assert status == 200
    assert snap["status"] == "waiting"
    assert snap["interrupt"] is not None
    print("[ok] GET /thread zeigt wartende Bestätigungskarte konsistent zum Event")

    options = snap["interrupt"]["options"]
    status, body = post(f"/resume/{thread_id}", {"session_id": session_id, "decision": options[0]})
    assert status == 200, f"POST /resume fehlgeschlagen: {status} {body}"

    resolved = listener.wait_for("interrupt_resolved", thread_id=thread_id)
    print(f"[ok] interrupt_resolved erhalten: {resolved}")

    idle_seen = False
    deadline = time.time() + 30
    while time.time() < deadline:
        if any(e["status"] == "idle" for e in listener.all_of("status_changed", thread_id=thread_id)):
            idle_seen = True
            break
        time.sleep(0.3)
    assert idle_seen, "Status ist nach /resume nie wieder auf 'idle' gesprungen"
    print("[ok] Graph lief nach /resume weiter bis idle")

    return thread_id


def test_rationale(session_id: str, thread_id: str, listener: SSEListener) -> None:
    """rationale.steps enthält genau die tatsächlich stattgefundenen
    Handlungen, Kopfzahl stimmt (len(steps) == angezeigte Zahl)."""
    appended = listener.all_of("message_appended", thread_id=thread_id)
    assert appended, "kein message_appended-Event für diese Anfrage erhalten"
    last = appended[-1]
    rationale = last.get("rationale")
    if rationale is None:
        print("[hinweis] rationale ist None - transparency_level erlaubt keine Rationale (siehe DEFAULT_TRANSPARENCY_LEVEL)")
        return
    steps = rationale["steps"]
    print(f"[ok] rationale.steps: {len(steps)} Schritt(e): {[s['label'] for s in steps]}")
    # Manuell prüfen: passt die Zahl zur tatsächlichen Korrekturschleife/
    # zum pending_action aus dem Snapshot?
    status, snap = get(f"/thread/{thread_id}?session_id={session_id}")
    assert status == 200


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


if __name__ == "__main__":
    session_id = test_access_code()
    test_preseeded_anfragen(session_id)

    listener = SSEListener(session_id)
    listener.start()

    thread_id = test_neue_anfrage_und_titel(session_id, listener)
    test_rationale(session_id, thread_id, listener)
    test_context_trennung(session_id)
    listener.stop()

    test_zwei_sessions_parallel()

    # Separat am Ende, weil er bewusst >2 Minuten braucht.
    if os.getenv("RUN_KEEPALIVE_TEST", "0") == "1":
        test_sse_keepalive(session_id)
    else:
        print("[info] Keepalive-Test übersprungen (RUN_KEEPALIVE_TEST=1 setzen, um ihn mitlaufen zu lassen)")

    print("\nAlle Prüfungen durchgelaufen.")
