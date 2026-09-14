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

import anthropic
from langgraph.types import Command

from agent.logging_store import log_interaction
from .config import DEFAULT_CONTROL_LEVEL, DEFAULT_TRANSPARENCY_LEVEL
from .events import SessionEventBus
from .preseed import PRESEED_TEMPLATES
from .rationale import build_execution_rationale, build_rationale
from .store import Store
from .suggestion_policy import SUGGESTION_POLICY

logger = logging.getLogger("api.graph_runner")

TITLE_MAX_LEN = 45

# Guideline 10 (lösungsorientierte Fehlerdarstellung): EIN Text für beide
# heute möglichen Fehlerarten, bewusst nicht zwei - siehe Bericht an die
# Nutzerin: es gibt aktuell KEINEN Codepfad, der ein "fachliches
# Scheitern" (ein Tool lehnt eine Aktion begründet ab) erzeugen könnte,
# AVAILABLE_TOOLS in tools.py hat keine Fehlerbedingungen. Ein zweiter
# Text kommt erst, wenn ein Tool tatsächlich einen solchen Fall hat -
# nicht vorher erfunden. Sagt, was Sache ist (erster Satz), dann was die
# Person tun kann (zweiter Satz) - keine Entschuldigungsfloskel, keine
# unbelegte Ursachenbehauptung.
ERROR_MESSAGE_TEXT = (
    "Da ist bei mir etwas schiefgelaufen, und ich konnte deine Anfrage "
    "nicht zu Ende bringen. Versuch es gern noch einmal."
)


def _classify_error(exc: Exception) -> str:
    """Nur für interaction_log.jsonl (NICHT für den Chat-Text, der bleibt
    für beide Fälle gleich, siehe ERROR_MESSAGE_TEXT) - unterscheidet
    bekannte Anthropic-SDK-Fehlerklassen (Netzwerk/Timeout/Rate-Limit/
    Auth - "technischer Ausfall") von allem anderen ("unexpected" -
    typischerweise ein Programmierfehler, kein Fehlerfall, den ein Tool
    selbst je auslösen könnte, siehe Moduldocstring-Hinweis oben).

    UNGEPRÜFT gegen das installierte anthropic-Paket - siehe Bericht an
    die Nutzerin, ausdrücklich als Rückfrage markiert statt geraten.
    `anthropic.APIError` ist die Basisklasse aller SDK-Fehler nach
    allgemeinem Kenntnisstand (APIConnectionError, APITimeoutError,
    RateLimitError, AuthenticationError etc. erben typischerweise davon),
    aber das ist hier NICHT gegen den tatsächlich installierten Code
    verifiziert. Vor dem ersten produktiven Einsatz dieser Funktion prüfen:
    `python -c "import anthropic; print(anthropic.APIError)"` - falls das
    fehlschlägt oder eine andere Hierarchie zutage tritt, diese Zeile
    anpassen."""
    if isinstance(exc, anthropic.APIError):
        return "api_error"
    return "unexpected"


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

    Bugfix (siehe Bericht an die Nutzerin): last_search_results/
    last_colleague/last_executed_action fehlten hier - graph.stream() merged
    das übergebene Dict nur PARTIELL in den bereits gecheckpointeten State
    (kein Reducer-Pattern, jeder nicht enthaltene Key behält seinen alten
    Wert), ein fehlender Key räumt also NICHTS auf. Ohne diese drei Zeilen
    hätte ein neuer Turn ihre Werte aus einem BELIEBIG früheren Turn desselben
    Threads geerbt, und rationale.py hätte daraus einen Schritt abgeleitet,
    der in diesem Durchlauf nie stattfand - der schlimmste Fehlertyp an
    dieser Stelle, weil er eine Quellenangabe für etwas Nichtstattgefundenes
    zeigt. Der zweite, kritischere Reset (zwischen Teilschritten DERSELBEN
    Nachricht) sitzt in supervisor_node, check_target=="next_subtask".
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
        "last_search_results": None,
        "last_colleague": None,
        "last_executed_action": None,
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
    zur Anzahl übergebener thread_ids (1:1, gleiche Reihenfolge).

    active_agent="__end__" ist Absicht, nicht der _base_state()-Default
    (""): eine vorbelegte Anfrage stellt eine BEREITS ABGESCHLOSSENE
    Konversation dar, keine mitten in der Zerlegung. Zusammen mit
    as_node="supervisor" bei graph.update_state() (siehe create_session()
    in routes.py) lässt das route_from_supervisor() auf END auflösen,
    statt dass LangGraph für einen historielosen Checkpoint next=
    ("supervisor",) annimmt - siehe Bericht an die Nutzerin: genau das
    ließ jede vorbelegte Anfrage fälschlich dauerhaft als "working"
    erscheinen (AnfrageSummary.status UND ThreadSnapshotResponse.status,
    beide lesen denselben Checkpoint über dieselbe derive_status())."""
    states = []
    for thread_id, template in zip(thread_ids, PRESEED_TEMPLATES):
        state = _base_state(
            thread_id=thread_id,
            messages=[dict(m) for m in template],
            sandbox_state={},
            pruefer_verdict="freigabe",
        )
        state["active_agent"] = "__end__"
        states.append(state)
    return states


def _initial_message_count(*, graph: Any, config: dict, graph_input: Any, is_resume: bool) -> int:
    """Anzahl Nachrichten, BEVOR dieser Lauf beginnt - Referenzwert für die
    Längenwachstum-Erkennung in run_turn_in_background()."""
    if is_resume:
        # graph_input ist ein Command(resume=...), hat keine eigenen
        # messages - der aktuelle Checkpoint-Stand ist die Referenz.
        snapshot = graph.get_state(config)
        values = snapshot.values or {}
        return len(values.get("messages") or [])
    # Frischer Turn: graph_input kommt aus build_fresh_turn_input() und
    # enthält die neue User-Nachricht bereits vollständig.
    return len(graph_input.get("messages") or [])


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

    Nachrichten-Erkennung über Längenwachstum von state["messages"]
    (nicht über eine Node-Namen-Allowlist): pruefer_node hängt nur bei
    verdict=="freigabe" an (bei "beanstandung" wächst die Liste nicht -
    kein Sonderfall nötig, das ergibt sich von selbst), escalate_node
    immer, execute_action_node bei tatsächlich ausgeführter Aktion. Jeder
    künftige Knoten, der ebenfalls an messages anhängt, wird dadurch
    automatisch erkannt, ohne dass diese Datei angepasst werden muss.

    Endstatus nach regulärem Abschluss ist "result" (peripheres Signal,
    Calm-Technology-Kern - siehe Bericht an die Nutzerin), NICHT "idle" -
    außer es wurde in diesem Lauf gar keine neue Nachricht angehängt (z.B.
    eine Ablehnung: human_review_node setzt pending_action=None,
    execute_action_node führt dann nichts aus, keine neue Nachricht). Ein
    "result"-Signal ohne etwas Neues zu zeigen wäre eine leere
    Benachrichtigung - genau das, was Calm Technology vermeiden soll -
    deshalb dort weiterhin "idle", kein Sonderfall im Code nötig, ergibt
    sich aus demselben any_message_appended-Flag.
    """
    config = {"configurable": {"thread_id": thread_id}}
    known_message_count = _initial_message_count(
        graph=graph, config=config, graph_input=graph_input, is_resume=is_resume
    )

    # Override aus einem VORHERIGEN Lauf darf nicht in diesen neuen Lauf
    # hineinwirken (siehe derive_status()-Docstring) - hier aktiv löschen,
    # nicht erst beim nächsten GET abklingen lassen.
    store.set_status_override(thread_id, None)
    bus.publish_threadsafe(
        session_id, {"type": "status_changed", "thread_id": thread_id, "status": "working"}
    )

    first_chunk = True
    any_message_appended = False
    last_completed_node: Optional[str] = None

    try:
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
                last_completed_node = node_name
                messages = node_state.get("messages") or []
                if len(messages) <= known_message_count:
                    continue
                new_messages = messages[known_message_count:]
                start_index = known_message_count
                known_message_count = len(messages)
                for offset, message in enumerate(new_messages):
                    any_message_appended = True
                    _publish_message(
                        node_name=node_name,
                        node_state=node_state,
                        message=message,
                        message_index=start_index + offset,
                        store=store,
                        bus=bus,
                        session_id=session_id,
                        thread_id=thread_id,
                    )

        # Stream regulär zu Ende (kein interrupt -> kein return oben) ->
        # dieser Lauf ist fertig, egal ob END erreicht oder alle
        # Teilschritte abgearbeitet sind.
        final_status = "result" if any_message_appended else "idle"
        if final_status == "result":
            store.set_status_override(thread_id, "result")
        bus.publish_threadsafe(
            session_id, {"type": "status_changed", "thread_id": thread_id, "status": final_status}
        )
    except Exception as exc:
        logger.exception("Graph-Lauf für thread_id=%s fehlgeschlagen", thread_id)

        # Randfall: wenn der Fehler auftritt, BEVOR auch nur ein Chunk
        # verarbeitet wurde, wurde interrupt_resolved beim Resume-Pfad nie
        # gesendet (siehe Schleife oben) - ohne dieses Event bliebe die
        # Bestätigungskarte im Frontend dauerhaft auf "waiting" stehen,
        # obwohl der Backend-Status längst auf "error" gesprungen ist.
        if is_resume and first_chunk:
            bus.publish_threadsafe(
                session_id, {"type": "interrupt_resolved", "thread_id": thread_id}
            )

        # Fehlermeldung MUSS in den Checkpoint, nicht nur als flüchtiges
        # SSE-Event - sonst zeigt ein Reload nach dem Fehler eine
        # Konversation, die kommentarlos aufhört (siehe Bericht an die
        # Nutzerin, Guideline 10). Der Knoten, der gerade lief, hat wegen
        # der Exception selbst nie fertig geschrieben - deshalb hier über
        # graph.update_state() von außen angehängt (dieselbe öffentliche
        # LangGraph-API wie in test_context_recheck.py, keine Umgehung).
        snapshot = graph.get_state(config)
        values = snapshot.values or {}
        messages = list(values.get("messages") or [])
        messages.append({"role": "assistant", "content": ERROR_MESSAGE_TEXT})
        graph.update_state(config, {"messages": messages})

        # Läuft NICHT über _publish_message(): die kommt aus einem echten
        # graph.stream()-Chunk, den es hier nie gab. rationale=None ist
        # richtig, nicht "vergessen" - das ist keine Vorschlags-/
        # Ausführungs-Nachricht, für die es einen Begründungsblock gäbe.
        bus.publish_threadsafe(
            session_id,
            {
                "type": "message_appended",
                "thread_id": thread_id,
                "message": {"role": "assistant", "content": ERROR_MESSAGE_TEXT},
                "rationale": None,
            },
        )

        log_interaction(
            category="error",
            node=last_completed_node,
            session_id=thread_id,
            task=values.get("current_task"),
            channel=values.get("channel"),
            error_kind=_classify_error(exc),
            error_type=type(exc).__name__,
            error_detail=str(exc),
        )

        store.set_status_override(thread_id, "error")
        bus.publish_threadsafe(
            session_id, {"type": "status_changed", "thread_id": thread_id, "status": "error"}
        )


def _publish_message(
    *,
    node_name: str,
    node_state: dict,
    message: dict,
    message_index: int,
    store: Store,
    bus: SessionEventBus,
    session_id: str,
    thread_id: str,
) -> None:
    # execute_action_node braucht die EIGENE, Ausführungs-Modus-Ableitung
    # (state["last_executed_action"], nicht state["pending_action"] - siehe
    # rationale.build_execution_rationale) - alle anderen Knoten (pruefer,
    # escalate) nutzen weiterhin die allgemeine build_rationale().
    if node_name == "execute_action":
        rationale = build_execution_rationale(node_state)
    else:
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


def derive_status(snapshot: Any, status_override: Optional[str] = None) -> str:
    """Statuswert rein aus dem Checkpoint-Snapshot UND (nachrangig) einem
    Store-Override abgeleitet - KEINE separate Laufzeit-Registry, damit ein
    Reload/Anfragewechsel den Status allein aus GET /thread/GET /session
    rekonstruieren kann (siehe Auftrag Punkt 5).

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
    - sonst -> status_override, falls gesetzt (z.B. "result"/"error" -
      "wurde das gesehen" ist Interaktionsmetadatum, kein Graph-Zustand,
      lebt deshalb in Store, nicht im Checkpoint, siehe store.py). Checkpoint
      schlägt den Override IMMER (ein gerade wieder aktiver Lauf überschreibt
      eine alte, noch nicht gesehene Ergebnis-/Fehlermeldung in der Anzeige -
      der Override selbst wird beim nächsten Laufstart aktiv zurückgesetzt,
      siehe run_turn_in_background()).
    - sonst -> "idle".

    Bewusst KEINE feste Werteliste für status_override (kein `in (...)`-
    Whitelist-Check) - die Werteliste lebt einzig in `StatusValue`
    (api/models.py) und in den Stellen, die den Override tatsächlich setzen.

    Korrektur eines früheren Kommentars an dieser Stelle: "suggestion"
    läuft NICHT durch diese Funktion - es ist Session-, nicht
    Thread-gebunden (siehe session_has_live_anfrage()/
    resolve_pending_suggestion() unten, gleiches Vorrang-Prinzip, eine
    Ebene höher, eigener Store-Override auf `sessions` statt `anfragen`).
    """
    if snapshot.interrupts:
        return "waiting"
    if snapshot.next:
        return "working"
    if status_override:
        return status_override
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


def session_has_live_anfrage(store: Store, graph: Any, session_id: str) -> bool:
    """True, wenn IRGENDEINE Anfrage der Session gerade 'waiting' oder
    'working' ist - Vorrang-Regel für Vorschläge (dürfen laufende/
    wartende Anfragen nicht überschreiben, siehe Bericht an die
    Nutzerin). Genutzt sowohl zur SCHREIBZEIT (POST /session/{id}/screen:
    kein neuer Vorschlag, wenn gerade etwas läuft) als auch zur LESEZEIT
    (resolve_pending_suggestion() unten: ein bereits gesetzter Vorschlag
    wird unterdrückt, wenn DANACH woanders ein Lauf startet) - der
    Lesezeit-Fall ist der wichtigere der beiden, siehe Bericht an die
    Nutzerin, weil dort sonst ein veralteter Vorschlag angezeigt würde,
    obwohl gerade etwas läuft."""
    for row in store.list_anfragen(session_id):
        config = {"configurable": {"thread_id": row["thread_id"]}}
        snapshot = graph.get_state(config)
        status = derive_status(snapshot, row["status_override"])
        if status in ("waiting", "working"):
            return True
    return False


def resolve_pending_suggestion(store: Store, graph: Any, session_id: str) -> Optional[dict]:
    """{'screen':..., 'text':...} oder None - wendet den LESEZEIT-Vorrang
    an (siehe session_has_live_anfrage): die gespeicherte Spalte
    (pending_suggestion_screen) bleibt unangetastet, wird aber NICHT
    angezeigt, solange irgendetwas in der Session aktiv ist. Sobald die
    Session wieder ruhig ist, taucht derselbe Vorschlag unverändert
    wieder auf - die Unterdrückung ist eine reine Anzeige-Entscheidung,
    kein Löschen (siehe Bericht an die Nutzerin, eigener Testfall dafür:
    test_vorschlag_wird_bei_laufender_anfrage_lesezeitig_unterdrueckt_und_kehrt_zurueck)."""
    screen = store.get_pending_suggestion(session_id)
    if screen is None:
        return None
    if session_has_live_anfrage(store, graph, session_id):
        return None
    suggestion = SUGGESTION_POLICY.get(screen)
    if suggestion is None:
        return None
    return {"screen": screen, "text": suggestion["displayed"]}
