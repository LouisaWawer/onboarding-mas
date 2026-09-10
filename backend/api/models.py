"""
Pydantic-Schemas für die FastAPI-Schicht (backend/api/). Reine
Request-/Response-Formen - keine Graph-Logik hier, siehe agent/graph.py.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

StatusValue = Literal["idle", "working", "waiting"]


class CreateSessionRequest(BaseModel):
    access_code: str


class AnfrageSummary(BaseModel):
    thread_id: str
    title: Optional[str] = None
    created_at: str
    last_active_at: str


class SessionSnapshotResponse(BaseModel):
    """Antwort von POST /session und GET /session/{session_id} - dieselbe
    Form für beide, siehe Auftrag Punkt 2 ("eine Datenquelle, drei
    Ansichten")."""

    session_id: str
    anfragen: list[AnfrageSummary]
    active_thread_id: Optional[str] = None


class AnfrageOut(BaseModel):
    thread_id: str
    title: Optional[str] = None
    created_at: str
    last_active_at: str


class RationaleStep(BaseModel):
    label: str
    detail: Optional[str] = None
    source: Optional[dict] = None


class Rationale(BaseModel):
    steps: list[RationaleStep]


class MessageOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    rationale: Optional[Rationale] = None


class InterruptOut(BaseModel):
    proposal: Optional[dict] = None
    options: list[str] = []
    change_notice: Optional[str] = None


class ThreadSnapshotResponse(BaseModel):
    thread_id: str
    session_id: str
    status: StatusValue
    messages: list[MessageOut]
    interrupt: Optional[InterruptOut] = None


class PostMessageRequest(BaseModel):
    session_id: str
    text: str = Field(min_length=1)
    channel: Literal["dm", "status_panel"] = "dm"


class ResumeRequest(BaseModel):
    session_id: str
    decision: str = Field(min_length=1)


class AcceptedResponse(BaseModel):
    accepted: bool = True
