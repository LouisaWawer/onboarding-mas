"""
Session-weiter Event-Bus für SSE (GET /events/{session_id}), siehe Auftrag
Punkt 6. In-Memory, EIN Prozess (siehe "NICHT BAUEN": keine horizontale
Skalierung) - reicht damit aus, kein Redis/Pub-Sub-Server nötig.

Thread-Safety: publish_threadsafe() wird aus einem Worker-Thread heraus
aufgerufen (graph.stream() läuft blockierend in asyncio.to_thread, siehe
graph_runner.py), subscribe()/unsubscribe() laufen dagegen auf dem
Event-Loop-Thread (normale async Request-Handler). Damit beide Seiten
dieselben Strukturen (das _subscribers-Dict UND die einzelnen Queues) nie
gleichzeitig aus verschiedenen Threads anfassen, wird JEDE Mutation über
loop.call_soon_threadsafe() auf den Event-Loop-Thread verlagert - kein Lock
nötig, weil dadurch effektiv alles einzeln auf dem Loop-Thread passiert.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class SessionEventBus:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    async def subscribe(self, session_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[session_id].add(q)
        return q

    async def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        self._subscribers[session_id].discard(q)
        if not self._subscribers[session_id]:
            del self._subscribers[session_id]

    def publish_threadsafe(self, session_id: str, event: dict[str, Any]) -> None:
        """Aus einem BELIEBIGEN Thread aufrufbar (siehe Modulkopf-Kommentar).
        Niemals direkt awaiten/aus async Code aufrufen - dafür gibt es
        keinen Vorteil ggü. publish_threadsafe, es müsste sonst nur
        umständlich zwischen den beiden Aufrufkontexten unterschieden
        werden."""
        self._loop.call_soon_threadsafe(self._deliver, session_id, event)

    def _deliver(self, session_id: str, event: dict[str, Any]) -> None:
        for q in list(self._subscribers.get(session_id, ())):
            q.put_nowait(event)
