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

from .config import access_code_is_valid
from .events import SessionEventBus
from .graph_runner import (
    build_fresh_turn_input,
    build_preseed_states,
    derive_status,
    make_title,
    run_turn_in_background,
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
    PostMessageRequest,
    Rationale,
    ResumeRequest,
    SessionSnapshotResponse,
    ThreadSnapshotResponse,
)
from .preseed import PRESEED_TEMPLATES
from .store import Store

router = APIRouter()


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _session_snapshot(store: Store, session_id: str) -> SessionSnapshotResponse:
    rows = store.list_anfragen(session_id)
    return SessionSnapshotResponse(
        session_id=session_id,
        anfragen=[AnfrageSummary(**r) for r in rows],
        active_thread_id=store.active_thread_id(session_id),
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
        graph.update_state(config, state)
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

    return _session_snapshot(store, session_id)


@router.get("/session/{session_id}", response_model=SessionSnapshotResponse)
async def get_session(session_id: str, request: Request) -> SessionSnapshotResponse:
    store: Store = request.app.state.store
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    return _session_snapshot(store, session_id)


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

    return ThreadSnapshotResponse(
        thread_id=thread_id,
        session_id=session_id,
        status=derive_status(snapshot),
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
