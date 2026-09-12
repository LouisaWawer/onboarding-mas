"""
FastAPI-Endpunkte für den LangGraph-Agenten (siehe Auftrag). Enthält keine
Graph-Logik - nur HTTP-Fassade um agent/graph.py, orchestriert über
graph_runner.py.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from agent.logging_store import log_interaction

from .config import access_code_is_valid
from .events import SessionEventBus
from .graph_runner import (
    build_fresh_turn_input,
    build_preseed_states,
    derive_status,
    make_title,
    resolve_pending_suggestion,
    run_turn_in_background,
    session_has_live_anfrage,
    snapshot_interrupt_payload,
    to_resume_command,
)
from .rationale import build_rationale
from .models import (
    AcceptedResponse,
    AnfrageOut,
    AnfrageSummary,
    CreateSessionRequest,
    InterruptOut,
    MessageOut,
    PendingSuggestion,
    PostMessageRequest,
    Rationale,
    ResumeRequest,
    ScreenRequest,
    SeenRequest,
    SessionSnapshotResponse,
    ThreadSnapshotResponse,
)
from .preseed import PRESEED_TEMPLATES
from .store import Store
from .suggestion_policy import SUGGESTION_POLICY

router = APIRouter()


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _session_snapshot(store: Store, graph, session_id: str) -> SessionSnapshotResponse:
    # Pro Anfrage der Session den Status berechnen (Checkpoint + Override,
    # siehe derive_status()) - notwendig, damit ein Reload weiß, ob in
    # einer ANDEREN Anfrage etwas bereitliegt, nicht nur in der gerade
    # geöffneten (siehe Bericht an die Nutzerin: der periphere Punkt gilt
    # pro Anfrage, der Seitenreload ist in der Studie der Normalfall). Ein
    # graph.get_state()-Aufruf pro Anfrage - bei einer Handvoll Anfragen
    # pro Session unkritisch (siehe Bericht an die Nutzerin).
    rows = store.list_anfragen(session_id)
    summaries = []
    for row in rows:
        config = {"configurable": {"thread_id": row["thread_id"]}}
        snapshot = graph.get_state(config)
        status = derive_status(snapshot, row["status_override"])
        summaries.append(
            AnfrageSummary(
                thread_id=row["thread_id"],
                title=row["title"],
                created_at=row["created_at"],
                last_active_at=row["last_active_at"],
                status=status,
            )
        )
    pending = resolve_pending_suggestion(store, graph, session_id)
    return SessionSnapshotResponse(
        session_id=session_id,
        anfragen=summaries,
        active_thread_id=store.active_thread_id(session_id),
        pending_suggestion=PendingSuggestion(**pending) if pending else None,
    )


def _require_owned_anfrage(store: Store, thread_id: str, session_id: str) -> dict:
    """404 statt 403 bei fremder thread_id - siehe Auftrag Punkt 5: 'keine
    Daten preisgeben'. Gilt einheitlich auch für /message und /resume."""
    anfrage = store.get_anfrage(thread_id)
    if anfrage is None or anfrage["session_id"] != session_id:
        raise HTTPException(status_code=404, detail="Anfrage nicht gefunden.")
    return anfrage


async def _run_in_background(request: Request, session_id: str, thread_id: str, graph_input, *, is_resume: bool) -> None:
    app = request.app
    try:
        await asyncio.to_thread(
            run_turn_in_background,
            graph=app.state.graph,
            store=app.state.store,
            bus=app.state.event_bus,
            session_id=session_id,
            thread_id=thread_id,
            graph_input=graph_input,
            is_resume=is_resume,
        )
    finally:
        app.state.active_threads.discard(thread_id)


def _launch_background_run(request: Request, session_id: str, thread_id: str, graph_input, *, is_resume: bool) -> None:
    app = request.app
    app.state.active_threads.add(thread_id)
    task = asyncio.create_task(
        _run_in_background(request, session_id, thread_id, graph_input, is_resume=is_resume)
    )
    app.state.background_tasks.add(task)
    task.add_done_callback(app.state.background_tasks.discard)


# ---------------------------------------------------------------------------
# 1-2. Session
# ---------------------------------------------------------------------------


@router.post("/session", response_model=SessionSnapshotResponse)
async def create_session(body: CreateSessionRequest, request: Request) -> SessionSnapshotResponse:
    if not access_code_is_valid(body.access_code):
        raise HTTPException(status_code=403, detail="Ungültiger Zugangscode.")

    store: Store = request.app.state.store
    graph = request.app.state.graph
    bus: SessionEventBus = request.app.state.event_bus

    session_id = str(uuid.uuid4())
    store.create_session(session_id)

    thread_ids = [str(uuid.uuid4()) for _ in PRESEED_TEMPLATES]
    preseed_states = build_preseed_states(thread_ids)
    for thread_id, state, template in zip(thread_ids, preseed_states, PRESEED_TEMPLATES):
        config = {"configurable": {"thread_id": thread_id}}
        # as_node="supervisor": siehe build_preseed_states() (graph_runner.py)
        # - ohne as_node berechnet LangGraph next=("supervisor",) für einen
        # historielosen Checkpoint, die Anfrage zeigt dann dauerhaft
        # "working" statt "idle" (Bug, siehe Bericht an die Nutzerin).
        graph.update_state(config, state, as_node="supervisor")
        title = make_title(template[0]["content"])
        store.create_anfrage(thread_id, session_id, title=title)

        # Rationale-Spiegel auch für vorbelegte Anfragen (siehe Auftrag
        # Punkt 3), sonst zeigt GET /thread hier rationale: null, obwohl
        # eine live geführte Anfrage an derselben Stelle etwas anzeigen
        # würde - ein für die Studie sichtbarer Unterschied. Dieselbe
        # build_rationale()-Funktion wie beim Live-Lauf: die aktuellen
        # Templates haben kein pending_action/last_search_results/
        # last_colleague, ergeben also ehrlich {"steps": []} statt etwas
        # Erfundenem - kein Sonderfall nötig, falls ein künftiges Template
        # doch einen dieser Werte mitbringt.
        last_message_index = len(template) - 1
        rationale = build_rationale(state)
        if rationale is not None:
            store.save_message_rationale(thread_id, last_message_index, rationale)

        bus.publish_threadsafe(
            session_id, {"type": "anfrage_created", "thread_id": thread_id, "title": title}
        )

    return _session_snapshot(store, graph, session_id)


@router.get("/session/{session_id}", response_model=SessionSnapshotResponse)
async def get_session(session_id: str, request: Request) -> SessionSnapshotResponse:
    store: Store = request.app.state.store
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    graph = request.app.state.graph
    return _session_snapshot(store, graph, session_id)


# ---------------------------------------------------------------------------
# 3. Neue Anfrage
# ---------------------------------------------------------------------------


@router.post("/session/{session_id}/anfrage", response_model=AnfrageOut)
async def create_anfrage(session_id: str, request: Request) -> AnfrageOut:
    store: Store = request.app.state.store
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")

    thread_id = str(uuid.uuid4())
    row = store.create_anfrage(thread_id, session_id, title=None)
    request.app.state.event_bus.publish_threadsafe(
        session_id, {"type": "anfrage_created", "thread_id": thread_id, "title": None}
    )
    return AnfrageOut(**row)


# ---------------------------------------------------------------------------
# 5. Thread-Snapshot
# ---------------------------------------------------------------------------


@router.get("/thread/{thread_id}", response_model=ThreadSnapshotResponse)
async def get_thread(thread_id: str, session_id: str, request: Request) -> ThreadSnapshotResponse:
    store: Store = request.app.state.store
    _require_owned_anfrage(store, thread_id, session_id)

    graph = request.app.state.graph
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    values = snapshot.values or {}
    messages_raw = values.get("messages") or []

    rationales = store.get_all_rationales(thread_id)
    messages = [
        MessageOut(
            role=m["role"],
            content=m["content"],
            rationale=Rationale(**rationales[i]) if i in rationales else None,
        )
        for i, m in enumerate(messages_raw)
    ]

    interrupt_payload = snapshot_interrupt_payload(snapshot)
    status_override = store.get_status_override(thread_id)

    return ThreadSnapshotResponse(
        thread_id=thread_id,
        session_id=session_id,
        status=derive_status(snapshot, status_override),
        messages=messages,
        interrupt=InterruptOut(**interrupt_payload) if interrupt_payload else None,
    )


# ---------------------------------------------------------------------------
# 6. SSE-Event-Stream
# ---------------------------------------------------------------------------


@router.get("/events/{session_id}")
async def stream_events(session_id: str, request: Request) -> StreamingResponse:
    store: Store = request.app.state.store
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    bus: SessionEventBus = request.app.state.event_bus

    async def event_generator():
        queue = await bus.subscribe(session_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                except asyncio.TimeoutError:
                    # Alle 20-30s ein Keepalive-Kommentar, siehe Auftrag
                    # Punkt 6 - sonst schließen Proxy-Read-Timeouts die
                    # Verbindung in langen Leerlaufphasen.
                    yield ": keepalive\n\n"
                    continue
                yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            # Bewusst dauerhaft (kein Debug-Artefakt): macht sichtbar, wenn
            # eine Anfrage-Verbindung während eines laufenden Graph-
            # Durchgangs verschwindet (z.B. Seitenreload) - in der Studie
            # der Normalfall, nicht der Fehlerfall. GET /thread liefert dem
            # neu verbindenden Client den korrekten Zustand ohnehin aus dem
            # Checkpoint nach, unabhängig von dieser Zeile.
            print(f"[sse] t={time.time():.3f} session_id={session_id} unsubscribing", flush=True)
            await bus.unsubscribe(session_id, queue)

    headers = {
        # ZWINGEND hinter einem Reverse-Proxy, siehe Auftrag Punkt 6 - ohne
        # diesen Header puffern viele Proxys den Stream und alle Events
        # kommen auf einmal an.
        "X-Accel-Buffering": "no",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


# ---------------------------------------------------------------------------
# 7-8. Nachricht senden / Interrupt auflösen
# ---------------------------------------------------------------------------


@router.post("/message/{thread_id}", response_model=AcceptedResponse)
async def post_message(thread_id: str, body: PostMessageRequest, request: Request) -> AcceptedResponse:
    store: Store = request.app.state.store
    _require_owned_anfrage(store, thread_id, body.session_id)

    if body.suggestion_screen:
        # Nachricht stammt aus einem angeklickten Vorschlag (siehe
        # Bericht an die Nutzerin) - Annahmequote ist ein Datenpunkt für
        # die Auswertung (Guideline 21). Räumt den Session-Override
        # defensiv/idempotent mit auf, falls das Frontend aus irgendeinem
        # Grund kein /seen davor aufgerufen hat (normalerweise bereits
        # beim Öffnen des Panels geschehen).
        log_interaction(
            category="suggestion_accepted",
            node=None,
            session_id=None,
            api_session_id=body.session_id,
            screen=body.suggestion_screen,
        )
        store.set_pending_suggestion(body.session_id, None)

    if thread_id in request.app.state.active_threads:
        raise HTTPException(status_code=409, detail="Diese Anfrage läuft gerade schon.")

    graph = request.app.state.graph
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    if snapshot.interrupts:
        raise HTTPException(
            status_code=409,
            detail="Diese Anfrage wartet auf eine Bestätigung - siehe /resume.",
        )

    current_values = snapshot.values or {}
    is_first_message = not current_values.get("messages")

    graph_input = build_fresh_turn_input(
        thread_id=thread_id,
        current_values=current_values,
        user_text=body.text,
        channel=body.channel,
    )

    if is_first_message:
        title = make_title(body.text)
        if store.set_title_if_empty(thread_id, title):
            request.app.state.event_bus.publish_threadsafe(
                body.session_id,
                {"type": "anfrage_titled", "thread_id": thread_id, "title": title},
            )

    store.touch_anfrage(thread_id)
    _launch_background_run(request, body.session_id, thread_id, graph_input, is_resume=False)
    return AcceptedResponse()


@router.post("/resume/{thread_id}", response_model=AcceptedResponse)
async def post_resume(thread_id: str, body: ResumeRequest, request: Request) -> AcceptedResponse:
    store: Store = request.app.state.store
    _require_owned_anfrage(store, thread_id, body.session_id)

    if thread_id in request.app.state.active_threads:
        raise HTTPException(status_code=409, detail="Diese Anfrage läuft gerade schon.")

    graph = request.app.state.graph
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    if not snapshot.interrupts:
        raise HTTPException(
            status_code=409, detail="Diese Anfrage wartet gerade auf keine Bestätigung."
        )

    graph_input = to_resume_command(body.decision)
    store.touch_anfrage(thread_id)
    _launch_background_run(request, body.session_id, thread_id, graph_input, is_resume=True)
    return AcceptedResponse()


# ---------------------------------------------------------------------------
# 9. Ergebnis/Fehler zur Kenntnis genommen ("result"/"error" -> "idle")
# ---------------------------------------------------------------------------


@router.post("/thread/{thread_id}/seen", response_model=AcceptedResponse)
async def post_seen(thread_id: str, body: SeenRequest, request: Request) -> AcceptedResponse:
    """Löscht den Status-Override (result ODER error - beides ist 'zur
    Kenntnis genommen', siehe Bericht an die Nutzerin) und published den
    dadurch tatsächlich aktuellen Status - NICHT blind 'idle', falls die
    Anfrage in der Zwischenzeit (seltener Randfall) längst wieder aktiv
    ist (working/waiting), bliebe eine feste 'idle'-Meldung sonst falsch."""
    store: Store = request.app.state.store
    _require_owned_anfrage(store, thread_id, body.session_id)

    store.set_status_override(thread_id, None)

    graph = request.app.state.graph
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    current_status = derive_status(snapshot, None)

    request.app.state.event_bus.publish_threadsafe(
        body.session_id,
        {"type": "status_changed", "thread_id": thread_id, "status": current_status},
    )
    return AcceptedResponse()


# ---------------------------------------------------------------------------
# 10. Proaktive Vorschläge beim Screenwechsel ("suggestion", Guideline 21)
# ---------------------------------------------------------------------------


@router.post("/session/{session_id}/screen", response_model=AcceptedResponse)
async def post_screen(session_id: str, body: ScreenRequest, request: Request) -> AcceptedResponse:
    """Meldet: die Testperson hat lange genug auf `body.screen` verweilt,
    um einen Vorschlag zu rechtfertigen (8-10s Verweildauer-Timer sitzt
    im FRONTEND, siehe Bericht an die Nutzerin - dieser Endpunkt bedeutet
    also "hier wurde lange genug verweilt", kein "jemand ist hier"-
    Heartbeat, wird entsprechend selten aufgerufen, nicht bei jeder
    Navigation).

    Stiller No-Op (200, kein Fehler) bei:
      - 'chat' (gültige Screen-ID, aber kein Eintrag in SUGGESTION_POLICY
        - dort Hilfe anzubieten ergibt keinen Sinn, man ist ohnehin bei
        Lumi)
      - diesem Screen wurde in dieser Session bereits einmal vorgeschlagen
      - irgendeine Anfrage der Session läuft/wartet gerade (SCHREIBZEIT-
        Vorrang - der Vorschlag fällt in diesen Fällen aus, statt
        nachgeholt zu werden)
    Eine ECHT unbekannte Screen-ID ist dagegen ein Klientenfehler und wird
    von ScreenRequest bereits mit 422 abgelehnt, bevor dieser Code läuft."""
    store: Store = request.app.state.store
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")

    screen = body.screen
    if screen not in SUGGESTION_POLICY:
        return AcceptedResponse()
    if store.has_screen_been_suggested(session_id, screen):
        return AcceptedResponse()

    graph = request.app.state.graph
    if session_has_live_anfrage(store, graph, session_id):
        return AcceptedResponse()

    store.mark_screen_suggested(session_id, screen)
    store.set_pending_suggestion(session_id, screen)

    log_interaction(
        category="suggestion_shown",
        node=None,
        session_id=None,
        api_session_id=session_id,
        screen=screen,
    )

    request.app.state.event_bus.publish_threadsafe(
        session_id,
        {
            "type": "status_changed",
            "thread_id": None,
            "status": "suggestion",
            "screen": screen,
            "text": SUGGESTION_POLICY[screen]["displayed"],
        },
    )
    return AcceptedResponse()


@router.post("/session/{session_id}/seen", response_model=AcceptedResponse)
async def post_session_seen(session_id: str, request: Request) -> AcceptedResponse:
    """Session-Geschwister zu POST /thread/{id}/seen: löscht einen
    ausstehenden Vorschlag. Das Frontend ruft dies auf, wenn entweder das
    Panel geöffnet ODER der Screen verlassen wird (siehe Bericht an die
    Nutzerin, "Zurück auf idle, sobald...") - dieser Endpunkt kennt nur
    "zur Kenntnis genommen/hinfällig geworden", nicht WARUM.

    Published 'idle' NUR, wenn die Session danach tatsächlich ruhig ist -
    sonst würde ein fälschliches 'idle' eine echte laufende/wartende
    Anfrage überschreiben (gleiches Prinzip wie beim Thread-seen oben,
    das ebenfalls den tatsächlichen Status statt eines festen Werts
    published)."""
    store: Store = request.app.state.store
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")

    store.set_pending_suggestion(session_id, None)

    graph = request.app.state.graph
    if not session_has_live_anfrage(store, graph, session_id):
        request.app.state.event_bus.publish_threadsafe(
            session_id,
            {"type": "status_changed", "thread_id": None, "status": "idle"},
        )
    return AcceptedResponse()
