"""
Orchestriert Graph-Läufe für die API-Schicht: baut die state-Dicts, die
graph.py erwartet (siehe agent/state.py), konsumiert graph.stream() in
einem Worker-Thread und published Events über den SessionEventBus.

WICHTIG: Hier steckt bewusst KEINE Graph-Logik - nur Aufruf-Orchestrierung
von außen (graph.stream(), graph.get_state(), graph.update_state()).
agent/graph.py wird nicht verändert.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from langgraph.types import Command

from .config import DEFAULT_CONTROL_LEVEL, DEFAULT_TRANSPARENCY_LEVEL
from .events import SessionEventBus
from .preseed import PRESEED_TEMPLATES
from .rationale import build_rationale
from .store import Store

logger = logging.getLogger("api.graph_runner")

TITLE_MAX_LEN = 45


def make_title(first_user_text: str) -> str:
    """Gekürzte erste Nutzernachricht, ca. 45 Zeichen + Ellipse. KEIN
    LLM-Aufruf (siehe Auftrag Punkt 4)."""
    text = " ".join(first_user_text.strip().split())
    if len(text) <= TITLE_MAX_LEN:
        return text
    return text[:TITLE_MAX_LEN].rstrip() + "…"


def _base_state(
    *,
    thread_id: str,
    messages: list[dict],
    sandbox_state: dict,
    channel: str = "dm",
    pruefer_verdict: Optional[str] = None,
) -> dict:
    """Vollständiges OnboardingState-Dict (siehe agent/state.py) mit den
    Feldern für einen NEUEN Durchlauf ("Ersteingang"). Gleiche Feldliste
    wie test_graph.py's initial_state, damit nichts fehlt, was ein Knoten
    per state[...] (ohne .get) erwartet.

    state["session_id"] trägt hier bewusst die LangGraph-thread_id (=
    "Anfrage"), NICHT die API-Session-ID - siehe Bericht an die Nutzerin,
    das ist eine reine Namensüberschneidung zwischen den beiden Ebenen.
    """
    return {
        "messages": messages,
        "session_id": thread_id,
        "current_task": None,
        "active_agent": "",
        "transparency_level": DEFAULT_TRANSPARENCY_LEVEL,
        "control_level": DEFAULT_CONTROL_LEVEL,
        "check_target": "initial_request",
        "subtasks": [],
        "subtask_index": 0,
        "pruefer_verdict": pruefer_verdict,
        "pruefer_issues": [],
        "correction_count": 0,
        "pending_action": None,
        "pending_action_snapshot": None,
        "draft_response": None,
        "context_changed": False,
        "change_description": None,
        "dot_status": "idle",
        "sandbox_state": sandbox_state,
        "channel": channel,
    }


def build_fresh_turn_input(
    *, thread_id: str, current_values: dict, user_text: str, channel: str
) -> dict:
    """State-Input für einen NEUEN Nutzer-Turn auf einem (ggf. bereits
    bestehenden) Thread: bestehende messages + sandbox_state bleiben
    erhalten, alle Pro-Turn-Felder (Korrekturschleife, pending_action,
    Zerlegung, ...) werden zurückgesetzt - sonst würde ein neuer Turn
    versehentlich mitten in der Teilschritt-/Korrekturschleife des
    VORHERIGEN Turns weiterlaufen."""
    existing_messages = list(current_values.get("messages") or [])
    existing_messages.append({"role": "user", "content": user_text})
    sandbox_state = current_values.get("sandbox_state") or {}
    return _base_state(
        thread_id=thread_id,
        messages=existing_messages,
        sandbox_state=sandbox_state,
        channel=channel,
    )


def build_preseed_states(thread_ids: list[str]) -> list[dict]:
    """Ein vollständiges State-Dict pro Template aus preseed.py, passend
    zur Anzahl übergebener thread_ids (1:1, gleiche Reihenfolge)."""
    states = []
    for thread_id, template in zip(thread_ids, PRESEED_TEMPLATES):
        states.append(
            _base_state(
                thread_id=thread_id,
                messages=[dict(m) for m in template],
                sandbox_state={},
                pruefer_verdict="freigabe",
            )
        )
    return states


def run_turn_in_background(
    *,
    graph: Any,
    store: Store,
    bus: SessionEventBus,
    session_id: str,
    thread_id: str,
    graph_input: Any,
    is_resume: bool,
) -> None:
    """Läuft in einem Worker-Thread (siehe routes.py: asyncio.to_thread).
    Konsumiert graph.stream(..., stream_mode="updates") und published
    Events - siehe events.py für die Thread-Safety-Begründung von
    publish_threadsafe().

    stream_mode="updates" liefert pro abgeschlossenem Knoten
    {node_name: <von der Node-Funktion zurückgegebener State>} - JEDER
    Knoten in graph.py mutiert `state` in-place und gibt ihn komplett
    zurück (kein Reducer-Pattern), daher ist node_state hier bereits der
    VOLLSTÄNDIGE State-Snapshot direkt nach diesem Knoten, nicht nur ein
    Teil-Update.
    """
    config = {"configurable": {"thread_id": thread_id}}

    bus.publish_threadsafe(
        session_id, {"type": "status_changed", "thread_id": thread_id, "status": "working"}
    )

    try:
        first_chunk = True
        for chunk in graph.stream(graph_input, config, stream_mode="updates"):
            if is_resume and first_chunk and "__interrupt__" not in chunk:
                bus.publish_threadsafe(
                    session_id, {"type": "interrupt_resolved", "thread_id": thread_id}
                )
            first_chunk = False

            if "__interrupt__" in chunk:
                interrupt_obj = chunk["__interrupt__"][0]
                payload = interrupt_obj.value or {}
                bus.publish_threadsafe(
                    session_id,
                    {
                        "type": "interrupt_pending",
                        "thread_id": thread_id,
                        "proposal": payload.get("proposal"),
                        "options": payload.get("options", []),
                        "change_notice": payload.get("change_notice"),
                    },
                )
                bus.publish_threadsafe(
                    session_id,
                    {"type": "status_changed", "thread_id": thread_id, "status": "waiting"},
                )
                return

            for node_name, node_state in chunk.items():
                _handle_node_output(
                    node_name=node_name,
                    node_state=node_state,
                    store=store,
                    bus=bus,
                    session_id=session_id,
                    thread_id=thread_id,
                )

        # Stream regulär zu Ende (kein interrupt -> kein return oben) ->
        # dieser Lauf ist fertig, egal ob END erreicht oder alle
        # Teilschritte abgearbeitet sind.
        bus.publish_threadsafe(
            session_id, {"type": "status_changed", "thread_id": thread_id, "status": "idle"}
        )
    except Exception:
        logger.exception("Graph-Lauf für thread_id=%s fehlgeschlagen", thread_id)
        bus.publish_threadsafe(
            session_id, {"type": "status_changed", "thread_id": thread_id, "status": "idle"}
        )


def _handle_node_output(
    *,
    node_name: str,
    node_state: dict,
    store: Store,
    bus: SessionEventBus,
    session_id: str,
    thread_id: str,
) -> None:
    appended = False
    if node_name == "pruefer" and node_state.get("pruefer_verdict") == "freigabe":
        appended = True
    elif node_name == "escalate":
        appended = True
    # node_name == "pruefer" mit verdict != "freigabe": beanstandeter
    # Entwurf, draft_response bleibt bewusst unsichtbar (siehe pruefer_node)
    # - kein Event, kein Spiegel-Eintrag.

    if not appended:
        return

    messages = node_state.get("messages") or []
    if not messages:
        return

    message_index = len(messages) - 1
    message = messages[-1]
    rationale = build_rationale(node_state)
    if rationale is not None:
        store.save_message_rationale(thread_id, message_index, rationale)

    store.touch_anfrage(thread_id)
    bus.publish_threadsafe(
        session_id,
        {
            "type": "message_appended",
            "thread_id": thread_id,
            "message": {"role": message["role"], "content": message["content"]},
            "rationale": rationale,
        },
    )


def to_resume_command(decision: str) -> Command:
    return Command(resume=decision)


def derive_status(snapshot: Any) -> str:
    """Statuswert rein aus dem Checkpoint-Snapshot abgeleitet (StateSnapshot
    aus graph.get_state()) - KEINE separate Laufzeit-Registry, damit ein
    Reload/Anfragewechsel den Status allein aus GET /thread rekonstruieren
    kann (siehe Auftrag Punkt 5).

    - snapshot.interrupts nicht leer -> "waiting" (ein interrupt() wartet,
      strukturell eindeutig aus dem Checkpoint lesbar).
    - snapshot.next nicht leer (aber kein interrupt) -> "working": der
      nächste Knoten ist geplant, aber sein Schritt-Checkpoint wurde noch
      nicht geschrieben, was bei diesem Graphen (keine interrupt_before/
      after-Konfiguration, nur explizite interrupt()-Aufrufe) in der Praxis
      genau dem Zeitraum entspricht, in dem der Hintergrund-Lauf gerade
      aktiv ist. Randfall: nach einem Serverabsturz mitten im Lauf bliebe
      das dauerhaft auf "working" stehen, bis die nächste Nachricht
      gesendet wird - für einen Ein-Prozess-Prototyp ohne Reconnect-Logik
      (siehe "NICHT BAUEN") akzeptiert, siehe Bericht an die Nutzerin.
    - sonst -> "idle".
    """
    if snapshot.interrupts:
        return "waiting"
    if snapshot.next:
        return "working"
    return "idle"


def snapshot_interrupt_payload(snapshot: Any) -> Optional[dict]:
    if not snapshot.interrupts:
        return None
    value = snapshot.interrupts[0].value or {}
    return {
        "proposal": value.get("proposal"),
        "options": value.get("options", []),
        "change_notice": value.get("change_notice"),
    }
