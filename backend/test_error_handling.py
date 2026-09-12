"""
API-Layer-Test für die Fehlerbehandlung in run_turn_in_background()
(backend/api/graph_runner.py) - Guideline 10 (lösungsorientierte
Fehlerdarstellung). Weder Black-Box-HTTP (test_api_manual.py) noch reiner
Graph-Test (test_graph.py/test_context_recheck.py): ruft
run_turn_in_background() direkt als Python-Funktion auf, mit einem echten
graph-Objekt (SqliteSaver, temporäres Verzeichnis - siehe unten), einem
echten Store und einem simplen Fake-Bus, der nur Events sammelt.

SIMULATION OHNE TEST-HOOK IN graph.py: agent.graph.client bzw.
agent.graph.log_interaction werden zur Laufzeit durch ein raisendes Objekt
ersetzt (Monkeypatch), IMMER über try/finally zurückgenommen - auch wenn
der jeweilige Test selbst fehlschlägt, sonst verseucht er nachfolgende
Läufe (siehe Bericht an die Nutzerin). Dieselbe Kategorie externe
Simulation wie graph.update_state() in test_context_recheck.py, kein
Hintereingang im Produktivcode.

Braucht einen echten ANTHROPIC_API_KEY in der Umgebung für den zweiten
Test (der bis zu einem echten ersten Interrupt läuft, bevor simuliert
wird) - wie test_context_recheck.py.

Ausführen: python test_error_handling.py
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import uuid

import agent.graph as graph_module
from agent.graph import build_graph
from api.graph_runner import ERROR_MESSAGE_TEXT, run_turn_in_background
from api.store import Store
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interaction_log.jsonl")


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


class _FakeBus:
    """Sammelt publish_threadsafe()-Aufrufe in Reihenfolge - das einzige,
    was run_turn_in_background() am bus-Objekt nutzt."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish_threadsafe(self, session_id: str, event: dict) -> None:
        self.events.append(event)


class _RaisingMessages:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def create(self, *args, **kwargs):
        raise self._exc


class _RaisingClient:
    """Ersatz für agent.graph.client - .messages.create() wirft immer."""

    def __init__(self, exc: Exception) -> None:
        self.messages = _RaisingMessages(exc)


@contextlib.contextmanager
def _patched_client(exc: Exception):
    original = graph_module.client
    graph_module.client = _RaisingClient(exc)
    try:
        yield
    finally:
        graph_module.client = original


@contextlib.contextmanager
def _patched_log_interaction(exc: Exception):
    original = graph_module.log_interaction

    def _raise(*args, **kwargs):
        raise exc

    graph_module.log_interaction = _raise
    try:
        yield
    finally:
        graph_module.log_interaction = original


def _fresh_state(thread_id: str, text: str, control_level: str = "medium") -> dict:
    return {
        "messages": [{"role": "user", "content": text}],
        "session_id": thread_id,
        "current_task": None,
        "active_agent": "",
        "transparency_level": "medium",
        "control_level": control_level,
        "check_target": "initial_request",
        "subtasks": [],
        "subtask_index": 0,
        "pruefer_verdict": None,
        "pruefer_issues": [],
        "correction_count": 0,
        "pending_action": None,
        "pending_action_snapshot": None,
        "context_changed": False,
        "change_description": None,
        "dot_status": "idle",
        "sandbox_state": {},
        "channel": "dm",
    }


def test_technischer_fehler_setzt_status_error_und_lumi_nachricht() -> None:
    """Frischer Lauf, client.messages.create() wirft sofort (beim allerersten
    Aufruf, in supervisor_node) - kein interrupt() war je im Spiel, also
    keine interrupt_resolved-Frage hier (das ist test_fehler_waehrend_resume
    unten). Prüft: status_changed('working') -> message_appended (Lumi-Text,
    KEINE rohe Exception, rationale=None) -> status_changed('error'),
    Fehlermeldung im Checkpoint persistiert, Store-Override gesetzt, ein
    'error'-Log-Eintrag mit unterscheidbarer error_kind."""
    session_id = str(uuid.uuid4())
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    tmp_dir = tempfile.mkdtemp()
    with SqliteSaver.from_conn_string(os.path.join(tmp_dir, "checkpoints.sqlite")) as checkpointer:
        graph = build_graph(checkpointer)
        store = Store(os.path.join(tmp_dir, "app_meta.sqlite"))
        store.create_session(session_id)
        store.create_anfrage(thread_id, session_id)
        bus = _FakeBus()

        log_entries_before = len(_read_log_entries())

        with _patched_client(RuntimeError("simulierter Verbindungsfehler")):
            run_turn_in_background(
                graph=graph, store=store, bus=bus, session_id=session_id,
                thread_id=thread_id,
                graph_input=_fresh_state(thread_id, "Ich brauche VPN-Zugang, kannst du das einrichten?"),
                is_resume=False,
            )

        types = [e["type"] for e in bus.events]
        assert types[0] == "status_changed" and bus.events[0]["status"] == "working", bus.events[:1]
        assert "interrupt_resolved" not in types, (
            f"kein Interrupt war je offen (frischer Lauf) - interrupt_resolved wäre falsch: {types}"
        )

        message_events = [e for e in bus.events if e["type"] == "message_appended"]
        assert message_events, f"keine Fehlermeldung als message_appended published: {types}"
        message_event = message_events[0]
        assert message_event["rationale"] is None
        assert message_event["message"]["content"] == ERROR_MESSAGE_TEXT
        assert "RuntimeError" not in message_event["message"]["content"], (
            "rohe Exception im Chat-Text - darf nicht, siehe Guideline 10"
        )
        print(f"[ok] Lumi-Nachricht ohne rohe Exception: {message_event['message']['content']!r}")

        assert types[-1] == "status_changed" and bus.events[-1]["status"] == "error", (
            f"erwartet letztes Event status_changed('error'), bekam: {bus.events[-1]}"
        )
        print("[ok] status_changed-Reihenfolge: working -> message_appended -> error")

        assert store.get_status_override(thread_id) == "error"
        print("[ok] Store-Override auf 'error' gesetzt")

        snapshot = graph.get_state(config)
        persisted_messages = snapshot.values.get("messages") or []
        assert persisted_messages[-1]["content"] == ERROR_MESSAGE_TEXT, (
            "Fehlermeldung wurde NICHT in den Checkpoint persistiert - ein Reload "
            "würde die Konversation kommentarlos abbrechen zeigen"
        )
        print("[ok] Fehlermeldung im Checkpoint persistiert (reload-sicher)")

        log_entries_after = _read_log_entries()
        new_error_entries = [
            e for e in log_entries_after[log_entries_before:]
            if e.get("category") == "error" and e.get("session_id") == thread_id
        ]
        assert len(new_error_entries) == 1, f"erwartet genau 1 'error'-Log-Eintrag: {new_error_entries}"
        assert new_error_entries[0].get("error_kind") in ("api_error", "unexpected"), new_error_entries[0]
        print(f"[ok] error-Log-Eintrag: {new_error_entries[0].get('error_kind')} / {new_error_entries[0].get('error_type')}")

    print("\n=== technischer Fehler (frischer Lauf): GRÜN ===")


def test_fehler_waehrend_resume_schliesst_bestaetigungskarte() -> None:
    """Der von der Nutzerin gefundene Randfall: wenn der Fehler auftritt,
    BEVOR auch nur ein Chunk des Resume-Laufs verarbeitet wurde, muss
    interrupt_resolved TROTZDEM published werden - sonst bleibt die
    Bestätigungskarte im Frontend auf 'waiting' stehen, obwohl der Status
    längst 'error' ist.

    Simuliert NICHT über agent.graph.client: im aktuellen Graphen gibt es
    zwischen einem interrupt()-Resume und dem ersten yield-baren Chunk
    KEINEN LLM-Aufruf (human_review_node/context_recheck_node/
    execute_action_node sind bei einem einzelnen Teilschritt reine
    Python-Logik) - ein Anthropic-Fehler könnte diesen Pfad also gar nicht
    erreichen, sondern nur NACH einem bereits erfolgreich verarbeiteten
    Chunk (z.B. beim zweiten Teilschritt) auftreten, was first_chunk
    bereits auf False gesetzt hätte. Stattdessen wird log_interaction
    gepatcht - die tatsächlich ERSTE Anweisung, die human_review_node nach
    der Rückkehr aus interrupt() ausführt - um die Exception zuverlässig
    an genau dieser Stelle zu platzieren, unabhängig davon, welches
    Subsystem dort in Zukunft tatsächlich zuerst drankäme."""
    session_id = str(uuid.uuid4())
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    tmp_dir = tempfile.mkdtemp()
    with SqliteSaver.from_conn_string(os.path.join(tmp_dir, "checkpoints.sqlite")) as checkpointer:
        graph = build_graph(checkpointer)
        store = Store(os.path.join(tmp_dir, "app_meta.sqlite"))
        store.create_session(session_id)
        store.create_anfrage(thread_id, session_id)

        # Echter Lauf (kein Patch) bis zum ersten Interrupt - braucht einen
        # echten ANTHROPIC_API_KEY, wie test_context_recheck.py.
        result = graph.invoke(
            _fresh_state(thread_id, "Ich brauche VPN-Zugang, kannst du das einrichten?"),
            config,
        )
        assert "__interrupt__" in result, f"erwartet ersten Interrupt (human_review), bekam: {result}"
        print("[ok] echter erster Interrupt (human_review) erreicht")

        bus = _FakeBus()
        with _patched_log_interaction(RuntimeError("simulierter Fehler direkt nach Resume")):
            run_turn_in_background(
                graph=graph, store=store, bus=bus, session_id=session_id,
                thread_id=thread_id, graph_input=Command(resume="bestätigen"),
                is_resume=True,
            )

        types = [e["type"] for e in bus.events]
        assert "interrupt_resolved" in types, (
            f"interrupt_resolved fehlt - Bestätigungskarte im Frontend würde auf "
            f"'waiting' hängen bleiben, obwohl der Status auf 'error' springt: {types}"
        )
        idx_resolved = types.index("interrupt_resolved")
        idx_error = next(
            i for i, e in enumerate(bus.events)
            if e["type"] == "status_changed" and e.get("status") == "error"
        )
        assert idx_resolved < idx_error, (
            f"interrupt_resolved muss VOR status_changed('error') kommen: {bus.events}"
        )
        print(f"[ok] Reihenfolge: interrupt_resolved(#{idx_resolved}) -> status_changed('error')(#{idx_error})")

    print("\n=== Fehler während Resume schließt Bestätigungskarte: GRÜN ===")


if __name__ == "__main__":
    test_technischer_fehler_setzt_status_error_und_lumi_nachricht()
    test_fehler_waehrend_resume_schliesst_bestaetigungskarte()
    print("\n2/2 Schritte grün.")
