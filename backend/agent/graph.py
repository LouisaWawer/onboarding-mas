"""
Graph-Struktur, Version 2: Supervisor + Prüfer um den bestehenden
Infrastructure-Pfad herum (bewusst NICHT alle vier Tool-Agenten gleichzeitig -
siehe Architektur-Gespräch: erst den Kreislauf an einem Beispiel validieren).

Ablauf:
  supervisor --[ok]--> infrastructure_agent --> pruefer
                                                    |
                          [beanstandung, correction_count <= MAX] -> zurück zu supervisor
                          [beanstandung, correction_count > MAX]  -> escalate
                          [freigabe] -> context_check
                                            |
                          [unverändert] -> human_review -> execute_action
                          [geändert]    -> updated_query -> execute_action | END
"""

from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from anthropic import Anthropic
from dotenv import load_dotenv
import os

load_dotenv()  # liest backend/.env ein - ohne diesen Aufruf bleibt
                # ANTHROPIC_API_KEY trotz korrekt gefüllter .env-Datei leer

from .state import OnboardingState
from .tools import AVAILABLE_TOOLS
from .colleague_data import find_colleague_for_topic
from .prompts_config import build_system_prompt, ESCALATION_PROMPT
from .logging_store import log_interaction

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MAX_CORRECTION_ATTEMPTS = 2

# Bewusst schlanke, leicht erweiter-/kürzbare Liste - Guidelines sind noch
# nicht final. Nicht sinnvoll prüfbare Punkte fliegen raus statt erzwungen
# zu werden (siehe Architektur-Gespräch, Punkt 3).
GENERIC_PHRASES = ["aus verschiedenen gründen", "wie du sicher weißt", "generell gilt"]


# ---------------------------------------------------------------------------
# Supervisor: wiederverwendeter Knoten für Ersteingang UND Korrekturschleife
# ---------------------------------------------------------------------------

def supervisor_node(state: OnboardingState) -> OnboardingState:
    check_target = state.get("check_target", "initial_request")

    if check_target == "correction":
        state["correction_count"] = state.get("correction_count", 0) + 1
        log_interaction(
            category="correction_loop",
            node="supervisor",
            session_id=state["session_id"],
            task=state.get("current_task"),
            channel=state["channel"],
            attempt=state["correction_count"],
        )
        if state["correction_count"] > MAX_CORRECTION_ATTEMPTS:
            state["active_agent"] = "escalate"
            return state
        # Zurück zur Korrektur: bleibt "aktiv", da (noch) keine Rückfrage an
        # die Nutzer:in nötig ist (Architektur-Gespräch, Punkt 4)
        state["dot_status"] = "active"
        state["active_agent"] = "infrastructure_agent"
        return state

    # Ersteingang: Klassifikation statt hart kodiertem Wert. Bewusst ein
    # SEPARATER, kleiner API-Call mit sehr niedrigem max_tokens - nicht der
    # eigentliche Antwort-Call, nur eine Ein-Wort-Einordnung.
    state["dot_status"] = "active"

    classification_prompt = (
        "Ordne die letzte Nutzer-Nachricht GENAU EINEM Bereich zu: "
        "'infrastructure' (VPN, Zugänge, Hardware, Software) oder "
        "'other' (alles andere, auch wenn unklar). "
        "Antworte NUR mit einem dieser zwei Wörter, sonst nichts."
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10,
        system=classification_prompt,
        messages=state["messages"],
    )
    routing = response.content[0].text.strip().lower()

    # Fallback-Logik: Bei allem, was nicht eindeutig "infrastructure" ist,
    # wird eskaliert statt geraten (ADR-004-Prinzip: im Zweifel nicht
    # improvisieren). Sobald scheduling_agent/info_agent existieren, hier
    # die ROUTING_MAP entsprechend erweitern.
    ROUTING_MAP = {
        "infrastructure": "infrastructure_agent",
    }
    state["active_agent"] = ROUTING_MAP.get(routing, "escalate")

    log_interaction(
        category="routing",
        node="supervisor",
        session_id=state["session_id"],
        channel=state["channel"],
        classification=routing,
        routed_to=state["active_agent"],
    )
    return state


def route_from_supervisor(state: OnboardingState) -> str:
    return state["active_agent"]


# ---------------------------------------------------------------------------
# Infrastructure-Agent (vormals it_agent)
# ---------------------------------------------------------------------------

def infrastructure_agent_node(state: OnboardingState) -> OnboardingState:
    system_prompt = build_system_prompt(state["transparency_level"])

    if state.get("pruefer_issues"):
        system_prompt += (
            "\n\nDeine letzte Antwort wurde beanstandet: "
            + "; ".join(state["pruefer_issues"])
            + ". Bitte korrigiere das in deiner nächsten Antwort."
        )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=system_prompt,
        messages=state["messages"],
    )
    state["messages"].append({"role": "assistant", "content": response.content[0].text})

    state["pending_action"] = {
        "tool": "create_ticket",
        "args": {"department": "IT", "subject": "VPN-Zugang beantragen"},
        "reason": "Für den Zugriff auf interne Tools brauchst du VPN.",
        "department": "IT",
        "is_critical": True,
    }
    state["current_task"] = "vpn_zugang"
    return state


# ---------------------------------------------------------------------------
# Prüfer: schlank, primär regelbasiert (Punkt 3 aus dem Architektur-Gespräch)
# ---------------------------------------------------------------------------

def pruefer_node(state: OnboardingState) -> OnboardingState:
    last_response = state["messages"][-1]["content"]
    issues = []

    is_critical = (state.get("pending_action") or {}).get("is_critical", False)
    if is_critical and "%" in last_response:
        issues.append("Konfidenzwert bei kritischer Aussage verwendet (L2 verletzt)")

    lowered = last_response.lower()
    if any(phrase in lowered for phrase in GENERIC_PHRASES):
        issues.append("generische Floskel statt konkreter Begründung (L3 verletzt)")

    state["pruefer_issues"] = issues
    state["pruefer_verdict"] = "beanstandung" if issues else "freigabe"

    log_interaction(
        category="pruefer_check",
        node="pruefer",
        session_id=state["session_id"],
        task=state.get("current_task"),
        channel=state["channel"],
        verdict=state["pruefer_verdict"],
        issues=issues,
    )
    return state


def route_from_pruefer(state: OnboardingState) -> str:
    if state["pruefer_verdict"] == "beanstandung":
        state["check_target"] = "correction"
        return "supervisor"
    return "context_check"


# ---------------------------------------------------------------------------
# Kontext-Check (G13): Zustand bei Zustimmung vs. jetzt
# ---------------------------------------------------------------------------

def _snapshot_relevant_state(sandbox_state: dict, pending_action: dict) -> dict:
    """Nimmt nur den für die geplante Aktion relevanten Ausschnitt des
    Sandbox-Zustands auf - nicht den kompletten State (der würde sich
    durch unabhängige Dinge ständig "ändern")."""
    return {
        "tickets_count": len(sandbox_state.get("tickets", [])),
        "department": pending_action.get("department"),
    }


def context_check_node(state: OnboardingState) -> OnboardingState:
    action = state.get("pending_action")
    if action is None:
        state["context_changed"] = False
        return state

    current = _snapshot_relevant_state(state["sandbox_state"], action)
    previous = state.get("pending_action_snapshot")

    if previous is None:
        # Erster Durchlauf: Snapshot zum Zeitpunkt der (gleich folgenden) Zustimmung setzen
        state["pending_action_snapshot"] = current
        state["context_changed"] = False
    elif previous != current:
        state["context_changed"] = True
        state["change_description"] = (
            f"Es gibt inzwischen {current['tickets_count']} statt vorher "
            f"{previous['tickets_count']} offene Tickets."
        )
    else:
        state["context_changed"] = False

    return state


def route_from_context_check(state: OnboardingState) -> str:
    return "updated_query" if state["context_changed"] else "human_review"


# ---------------------------------------------------------------------------
# Aktualisierte Nachfrage bei geändertem Kontext (Punkt 5)
# ---------------------------------------------------------------------------

def updated_query_node(state: OnboardingState) -> OnboardingState:
    state["dot_status"] = "waiting"
    decision = interrupt({
        "proposal": state["pending_action"],
        "change_notice": state.get("change_description"),
        "options": ["trotzdem bestätigen", "abbrechen"],
    })
    log_interaction(
        category="confirm",
        node="updated_query",
        session_id=state["session_id"],
        task=state.get("current_task"),
        channel=state["channel"],
        decision=decision,
        context_changed=True,
    )
    if decision != "trotzdem bestätigen":
        state["pending_action"] = None
    state["dot_status"] = "idle"
    return state


def route_from_updated_query(state: OnboardingState) -> str:
    return "execute_action" if state["pending_action"] else "__end__"


# ---------------------------------------------------------------------------
# Human Review (unveränderter Kontext)
# ---------------------------------------------------------------------------

def human_review_node(state: OnboardingState) -> OnboardingState:
    if state["control_level"] == "low" or state["pending_action"] is None:
        log_interaction(
            category="autonomous", node="human_review",
            session_id=state["session_id"], task=state.get("current_task"),
            channel=state["channel"],
        )
        return state

    state["dot_status"] = "waiting"
    decision = interrupt({
        "proposal": state["pending_action"],
        "options": ["bestätigen", "anpassen", "ablehnen"],
    })
    log_interaction(
        category="confirm", node="human_review",
        session_id=state["session_id"], task=state.get("current_task"),
        channel=state["channel"], decision=decision,
    )
    if decision != "bestätigen":
        state["pending_action"] = None
    state["dot_status"] = "idle"
    return state


# ---------------------------------------------------------------------------
# Eskalation - mit Abbruchgrund + Alternative/menschlichem Kontakt (Punkt 2)
# ---------------------------------------------------------------------------

def escalate_node(state: OnboardingState) -> OnboardingState:
    if state.get("correction_count", 0) > MAX_CORRECTION_ATTEMPTS:
        colleague = find_colleague_for_topic(state.get("current_task", ""))
        reason = "; ".join(state.get("pruefer_issues", [])) or "wiederholte Qualitätsprobleme"
        if colleague:
            text = (
                f"Ich konnte diese Anfrage nach mehreren Versuchen nicht zuverlässig "
                f"bearbeiten (Grund: {reason}). Am besten wendest du dich direkt an "
                f"{colleague['name']} ({colleague['department']})."
            )
        else:
            text = (
                f"Ich konnte diese Anfrage nach mehreren Versuchen nicht zuverlässig "
                f"bearbeiten (Grund: {reason}). Bitte erstelle ein Ticket für "
                f"menschliche Unterstützung."
            )
    else:
        text = ESCALATION_PROMPT

    state["messages"].append({"role": "assistant", "content": text})
    log_interaction(
        category="escalate", node="escalate",
        session_id=state["session_id"], channel=state["channel"],
        correction_exhausted=state.get("correction_count", 0) > MAX_CORRECTION_ATTEMPTS,
    )
    state["dot_status"] = "idle"
    return state


def execute_action_node(state: OnboardingState) -> OnboardingState:
    action = state["pending_action"]
    if action:
        tool_fn = AVAILABLE_TOOLS[action["tool"]]
        tool_fn(state["sandbox_state"], **action["args"])
    state["pending_action"] = None
    state["dot_status"] = "idle"
    return state


# ---------------------------------------------------------------------------
# Graph zusammensetzen
# ---------------------------------------------------------------------------

def build_graph(checkpointer=None):
    graph = StateGraph(OnboardingState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("infrastructure_agent", infrastructure_agent_node)
    graph.add_node("pruefer", pruefer_node)
    graph.add_node("context_check", context_check_node)
    graph.add_node("updated_query", updated_query_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("execute_action", execute_action_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges("supervisor", route_from_supervisor, {
        "infrastructure_agent": "infrastructure_agent",
        "escalate": "escalate",
    })

    graph.add_edge("infrastructure_agent", "pruefer")
    graph.add_conditional_edges("pruefer", route_from_pruefer, {
        "supervisor": "supervisor",
        "context_check": "context_check",
    })

    graph.add_conditional_edges("context_check", route_from_context_check, {
        "updated_query": "updated_query",
        "human_review": "human_review",
    })

    graph.add_conditional_edges("updated_query", route_from_updated_query, {
        "execute_action": "execute_action",
        "__end__": END,
    })

    graph.add_edge("human_review", "execute_action")
    graph.add_edge("execute_action", END)
    graph.add_edge("escalate", END)

    # Checkpointer wird vom Aufrufer übergeben (siehe test_graph.py) - muss
    # als "with SqliteSaver.from_conn_string(...) as checkpointer:" über die
    # GESAMTE Testlauf-Dauer offen gehalten werden, da from_conn_string in
    # aktuellen langgraph-Versionen ein Context-Manager ist, kein direktes
    # Objekt. build_graph() erzeugt ihn deshalb bewusst NICHT mehr selbst.
    return graph.compile(checkpointer=checkpointer)
