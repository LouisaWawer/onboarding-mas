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
# Tool-Schemas für STRUKTURIERTE Ausgaben (Anthropic Tool Use) - zu
# unterscheiden von AVAILABLE_TOOLS in tools.py, die echte Sandbox-Aktionen
# sind. Diese hier zwingen das Modell zu einem festen Antwortformat, statt
# Text zu parsen (ersetzt die frühere json.loads()-Lösung).
# ---------------------------------------------------------------------------

DECOMPOSE_TOOL = {
    "name": "decompose_request",
    "description": (
        "Zerlegt die Nutzer-Nachricht in einen oder mehrere Teilschritte, "
        "jeweils GENAU EINER Kategorie zugeordnet."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subtasks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "subtask": {
                            "type": "string",
                            "description": "Kurze Beschreibung des Teilschritts, 3-8 Wörter",
                        },
                        "category": {
                            "type": "string",
                            "enum": ["infrastructure", "info", "other"],
                            "description": (
                                "'infrastructure' = VPN/Zugänge/Hardware/Software, "
                                "'info' = allgemeine organisatorische Fragen (Urlaub, "
                                "Richtlinien, Onboarding-Themen), "
                                "'other' = alles andere, auch wenn unklar"
                            ),
                        },
                    },
                    "required": ["subtask", "category"],
                },
            }
        },
        "required": ["subtasks"],
    },
}

PROPOSE_TICKET_TOOL = {
    "name": "propose_ticket",
    "description": "Entscheidet, ob für die aktuelle Anfrage ein IT-Ticket vorgeschlagen werden soll.",
    "input_schema": {
        "type": "object",
        "properties": {
            "needed": {
                "type": "boolean",
                "description": "Ob überhaupt ein Ticket für diese Anfrage nötig ist",
            },
            "subject": {"type": "string", "description": "Kurzer Betreff für das Ticket"},
            "reason": {
                "type": "string",
                "description": "Kurze, der Nutzer:in gezeigte Begründung, warum das Ticket nötig ist",
            },
            "is_critical": {
                "type": "boolean",
                "description": "Ob dies eine kritische/sicherheitsrelevante Aktion ist (steuert L2/G3)",
            },
        },
        "required": ["needed"],
    },
}


def _extract_tool_input(response, tool_name: str) -> dict:
    """Holt den Tool-Use-Block aus einer erzwungenen Tool-Choice-Antwort.
    Bei tool_choice={'type':'tool', 'name': ...} enthält die Antwort GARANTIERT
    genau diesen Block - kein Text-Parsing, kein json.loads() nötig."""
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    raise ValueError(f"Kein Tool-Use-Block für '{tool_name}' in der Antwort gefunden")


def _messages_ending_with_user(messages: list, fallback_instruction: str) -> list:
    """Stellt sicher, dass eine Nachrichtenliste mit einer User-Nachricht endet -
    Anthropic-API-Anforderung ('conversation must end with a user message').

    Wird gebraucht, sobald mehrere Agenten NACHEINANDER auf denselben
    state["messages"]-Verlauf zugreifen (Mehrfach-Teilschritt-Zerlegung):
    Der zweite Sub-Agent würde sonst eine Konversation vorfinden, die mit
    der Antwort des ERSTEN Sub-Agenten (role="assistant") endet. Gibt eine
    NEUE Liste zurück, verändert die übergebene Liste nicht."""
    if messages and messages[-1]["role"] == "assistant":
        return messages + [{"role": "user", "content": fallback_instruction}]
    return messages


# ---------------------------------------------------------------------------
# Supervisor: wiederverwendeter Knoten für Ersteingang UND Korrekturschleife
# ---------------------------------------------------------------------------

import json


def _route_for_category(category: str) -> str:
    """Zentrale Zuordnung Kategorie -> Graph-Knoten. Hier erweitern, sobald
    scheduling_agent existiert."""
    ROUTING_MAP = {
        "infrastructure": "infrastructure_agent",
        "info": "info_agent",
    }
    return ROUTING_MAP.get(category, "escalate")


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
        # Zurück zur Korrektur DESSELBEN Teilschritts - nicht hart kodiert,
        # sondern der Agent, der für die aktuelle subtask-Kategorie zuständig ist
        current = state["subtasks"][state["subtask_index"]]
        state["dot_status"] = "active"
        state["active_agent"] = _route_for_category(current["category"])
        return state

    if check_target == "next_subtask":
        state["correction_count"] = 0  # pro Teilschritt zurücksetzen
        state["subtask_index"] += 1
        if state["subtask_index"] >= len(state["subtasks"]):
            state["active_agent"] = "__end__"
            state["dot_status"] = "idle"
            return state
        current = state["subtasks"][state["subtask_index"]]
        state["current_task"] = current["subtask"]
        state["dot_status"] = "active"
        state["active_agent"] = _route_for_category(current["category"])
        return state

    # Ersteingang: Nachricht in einen oder mehrere Teilschritte zerlegen.
    # Tool Use mit erzwungenem tool_choice statt freiem Text + json.loads() -
    # garantiert gültige Struktur, kein Parsing-Fehler möglich.
    state["dot_status"] = "active"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=state["messages"],
        tools=[DECOMPOSE_TOOL],
        tool_choice={"type": "tool", "name": "decompose_request"},
    )
    result = _extract_tool_input(response, "decompose_request")
    subtasks = result["subtasks"]

    state["subtasks"] = subtasks
    state["subtask_index"] = 0
    state["current_task"] = subtasks[0]["subtask"]
    state["active_agent"] = _route_for_category(subtasks[0]["category"])

    log_interaction(
        category="decomposition",
        node="supervisor",
        session_id=state["session_id"],
        channel=state["channel"],
        subtask_count=len(subtasks),
        subtasks=subtasks,
    )
    return state


def route_from_supervisor(state: OnboardingState) -> str:
    return state["active_agent"]


# ---------------------------------------------------------------------------
# Infrastructure-Agent (vormals it_agent)
# ---------------------------------------------------------------------------

def infrastructure_agent_node(state: OnboardingState) -> OnboardingState:
    system_prompt = build_system_prompt(state["transparency_level"])

    # Fokus-Anweisung: die Nutzer-Nachricht kann mehrere Anliegen enthalten,
    # dieser Knoten soll sich NUR um den aktuellen Teilschritt kümmern, nicht
    # die ganze Original-Nachricht erneut aufrollen.
    system_prompt += (
        f"\n\nWICHTIG: Kümmere dich in dieser Antwort AUSSCHLIESSLICH um "
        f"folgenden Teilschritt: \"{state['current_task']}\". Falls die "
        f"ursprüngliche Nachricht weitere Anliegen enthält, werden diese "
        f"separat behandelt - gehe NICHT darauf ein, auch nicht kurz erwähnend."
    )

    if state.get("pruefer_issues"):
        system_prompt += (
            "\n\nDeine letzte Antwort wurde beanstandet: "
            + "; ".join(state["pruefer_issues"])
            + ". Bitte korrigiere das in deiner nächsten Antwort."
        )

    # --- TEMPORÄRER TEST-HOOK: erzwingt beim ERSTEN Versuch eine Floskel,
    # um die Korrekturschleife gezielt auszulösen. Nach dem Test wieder
    # entfernen (siehe Architektur-Gespräch, Punkt 1 - Korrekturschleife
    # testen). ---
    if state.get("correction_count", 0) == 0:
        system_prompt += (
            "\n\nTESTMODUS: Baue in diese eine Antwort irgendwo den Satz "
            "'Das mache ich aus verschiedenen Gründen so.' ein."
        )
    # --- ENDE TEST-HOOK ---

    # 1. Antwort-Entwurf generieren. Nachrichtenliste absichern (siehe
    # _messages_ending_with_user) - bei einem zweiten/weiteren Teilschritt
    # ODER einem zweiten Korrekturversuch endet state["messages"] sonst mit
    # einer Assistant-Nachricht, was die API ablehnt.
    call_messages = _messages_ending_with_user(
        state["messages"],
        f"Bitte kümmere dich jetzt um diesen Teilschritt: {state['current_task']}",
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=system_prompt,
        messages=call_messages,
    )
    # WICHTIG: NICHT direkt an state["messages"] anhängen - erst nach
    # Prüfer-Freigabe (siehe pruefer_node). So bleiben abgelehnte Entwürfe
    # aus der Korrekturschleife unsichtbar für die Nutzer:in (wie geplant:
    # "Korrektur läuft nur intern"), UND es entstehen nie zwei
    # Assistant-Nachrichten hintereinander in der gespeicherten Historie.
    state["draft_response"] = response.content[0].text

    # 2. Strukturierte Aktions-Extraktion per Tool Use - basiert auf dem
    # ENTWURF (noch nicht bestätigt), nicht auf state["messages"]. Eigene,
    # rein lokale Nachrichtenliste - landet nirgends in der gespeicherten
    # Historie.
    extraction_messages = call_messages + [
        {"role": "assistant", "content": state["draft_response"]},
        {"role": "user", "content": "Bewerte anhand des bisherigen Gesprächs: ist ein Ticket nötig?"},
    ]
    extraction_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=(
            "Entscheide anhand der Konversation, ob ein IT-Ticket für die "
            "aktuelle Anfrage vorgeschlagen werden soll."
        ),
        messages=extraction_messages,
        tools=[PROPOSE_TICKET_TOOL],
        tool_choice={"type": "tool", "name": "propose_ticket"},
    )
    action_data = _extract_tool_input(extraction_response, "propose_ticket")

    if action_data.get("needed"):
        state["pending_action"] = {
            "tool": "create_ticket",
            "args": {"department": "IT", "subject": action_data.get("subject", "IT-Anliegen")},
            "reason": action_data.get("reason", ""),
            "department": "IT",
            "is_critical": action_data.get("is_critical", True),
        }
    else:
        state["pending_action"] = None

    return state


# ---------------------------------------------------------------------------
# Info-Agent: allgemeine organisatorische Fragen, nutzt search_documents
# ---------------------------------------------------------------------------

def info_agent_node(state: OnboardingState) -> OnboardingState:
    query = state["current_task"]
    results = AVAILABLE_TOOLS["search_documents"](state["sandbox_state"], query)

    system_prompt = build_system_prompt(state["transparency_level"])
    system_prompt += (
        f"\n\nWICHTIG: Kümmere dich in dieser Antwort AUSSCHLIESSLICH um "
        f"folgenden Teilschritt: \"{state['current_task']}\". Falls die "
        f"ursprüngliche Nachricht weitere Anliegen enthält, werden diese "
        f"separat behandelt - gehe NICHT darauf ein, auch nicht kurz erwähnend."
    )

    if results:
        docs_context = "\n".join(
            f"- {r['title']}: {r.get('summary', '')}" for r in results
        )
        system_prompt += (
            f"\n\nGefundene relevante Inhalte aus Knowledge Hub/Intranet:\n"
            f"{docs_context}\nNutze diese als Grundlage für deine Antwort, "
            f"erfinde keine Details, die dort nicht stehen. Nenne am Ende "
            f"deiner Antwort explizit, aus welchem Dokument/Artikel die "
            f"Information stammt (Titel nennen, z.B. \"(Quelle: [Titel])\"), "
            f"damit die Nutzer:in die Angabe selbst nachlesen kann."
        )
    else:
        system_prompt += (
            "\n\nEs wurden keine passenden Dokumente gefunden. Erkläre das "
            "ehrlich, statt zu improvisieren."
        )

    if state.get("pruefer_issues"):
        system_prompt += (
            "\n\nDeine letzte Antwort wurde beanstandet: "
            + "; ".join(state["pruefer_issues"])
            + ". Bitte korrigiere das in deiner nächsten Antwort."
        )

    call_messages = _messages_ending_with_user(
        state["messages"],
        f"Bitte kümmere dich jetzt um diesen Teilschritt: {state['current_task']}",
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=system_prompt,
        messages=call_messages,
    )
    # NICHT direkt an state["messages"] anhängen - erst nach Prüfer-Freigabe
    # (siehe pruefer_node und infrastructure_agent_node, gleiches Prinzip).
    state["draft_response"] = response.content[0].text

    # info_agent schlägt i.d.R. keine Tool-Aktion vor - reine
    # Informationsantwort, kein Bestätigungsschritt nötig.
    state["pending_action"] = None
    return state


def pruefer_node(state: OnboardingState) -> OnboardingState:
    last_response = state.get("draft_response", "")
    issues = []

    is_critical = (state.get("pending_action") or {}).get("is_critical", False)
    if is_critical and "%" in last_response:
        issues.append("Konfidenzwert bei kritischer Aussage verwendet (L2 verletzt)")

    lowered = last_response.lower()
    if any(phrase in lowered for phrase in GENERIC_PHRASES):
        issues.append("generische Floskel statt konkreter Begründung (L3 verletzt)")

    state["pruefer_issues"] = issues
    state["pruefer_verdict"] = "beanstandung" if issues else "freigabe"

    if state["pruefer_verdict"] == "freigabe":
        # Erst JETZT wird der Entwurf Teil der sichtbaren, permanenten
        # Historie - abgelehnte Entwürfe (Korrekturschleife) haben es nie
        # bis hierher geschafft und bleiben unsichtbar für die Nutzer:in.
        state["messages"].append({"role": "assistant", "content": state["draft_response"]})

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
    colleague = find_colleague_for_topic(state.get("current_task", ""))

    if state.get("correction_count", 0) > MAX_CORRECTION_ATTEMPTS:
        reason = "; ".join(state.get("pruefer_issues", [])) or "wiederholte Qualitätsprobleme"
        if colleague:
            instruction = (
                f"Erkläre freundlich, dass die Anfrage nach mehreren Versuchen nicht "
                f"zuverlässig bearbeitet werden konnte (Grund: {reason}), und verweise "
                f"konkret auf {colleague['name']} ({colleague['department']}) als "
                f"Ansprechperson."
            )
        else:
            instruction = (
                f"Erkläre freundlich, dass die Anfrage nach mehreren Versuchen nicht "
                f"zuverlässig bearbeitet werden konnte (Grund: {reason}), und bitte darum, "
                f"stattdessen ein Ticket für menschliche Unterstützung zu erstellen."
            )
    else:
        colleague_hint = (
            f"Verweise konkret auf {colleague['name']} ({colleague['department']}) als "
            f"zuständige Person für dieses Thema."
            if colleague
            else "Erkläre, dass dafür aktuell kein spezifischer Kontakt bekannt ist."
        )
        instruction = ESCALATION_PROMPT + "\n\n" + colleague_hint

    # Fokus-Anweisung, wie beim Infrastructure-Agenten: nur den aktuellen
    # Teilschritt ansprechen, bereits behandelte Themen nicht wiederholen.
    instruction += (
        f"\n\nWICHTIG: Es geht in dieser Antwort AUSSCHLIESSLICH um folgenden "
        f"Teilschritt: \"{state.get('current_task', '')}\". Andere Anliegen aus "
        f"der ursprünglichen Nachricht wurden bereits separat behandelt oder "
        f"werden noch behandelt - erwähne sie NICHT erneut, auch nicht kurz."
    )

    # Echter LLM-Aufruf statt wörtlicher Ausgabe der Anweisung. Eigene
    # Nachrichtenliste mit User-Abschluss (siehe infrastructure_agent_node -
    # dieselbe API-Anforderung: Konversation muss mit "user" enden).
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=instruction,
        messages=state["messages"] + [
            {"role": "user", "content": "Bitte formuliere jetzt die Antwort an die Nutzer:in."}
        ],
    )
    state["messages"].append({"role": "assistant", "content": response.content[0].text})

    log_interaction(
        category="escalate", node="escalate",
        session_id=state["session_id"], channel=state["channel"],
        correction_exhausted=state.get("correction_count", 0) > MAX_CORRECTION_ATTEMPTS,
    )
    state["dot_status"] = "idle"
    state["check_target"] = "next_subtask"
    return state


def execute_action_node(state: OnboardingState) -> OnboardingState:
    action = state["pending_action"]
    if action:
        tool_fn = AVAILABLE_TOOLS[action["tool"]]
        tool_fn(state["sandbox_state"], **action["args"])
    state["pending_action"] = None
    state["dot_status"] = "idle"
    # Zurück zum Supervisor statt direkt zu enden - prüft dort, ob es
    # weitere Teilschritte aus der Zerlegung gibt (mehrere Anliegen in
    # einer Nachricht).
    state["check_target"] = "next_subtask"
    return state


# ---------------------------------------------------------------------------
# Graph zusammensetzen
# ---------------------------------------------------------------------------

def build_graph(checkpointer=None):
    graph = StateGraph(OnboardingState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("infrastructure_agent", infrastructure_agent_node)
    graph.add_node("info_agent", info_agent_node)
    graph.add_node("pruefer", pruefer_node)
    graph.add_node("context_check", context_check_node)
    graph.add_node("updated_query", updated_query_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("execute_action", execute_action_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges("supervisor", route_from_supervisor, {
        "infrastructure_agent": "infrastructure_agent",
        "info_agent": "info_agent",
        "escalate": "escalate",
        "__end__": END,
    })

    graph.add_edge("infrastructure_agent", "pruefer")
    graph.add_edge("info_agent", "pruefer")
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
    # Beide führen zurück zum Supervisor (dort: check_target="next_subtask"),
    # statt die gesamte Kette nach einem einzigen Teilschritt zu beenden.
    graph.add_edge("execute_action", "supervisor")
    graph.add_edge("escalate", "supervisor")

    # Checkpointer wird vom Aufrufer übergeben (siehe test_graph.py) - muss
    # als "with SqliteSaver.from_conn_string(...) as checkpointer:" über die
    # GESAMTE Testlauf-Dauer offen gehalten werden, da from_conn_string in
    # aktuellen langgraph-Versionen ein Context-Manager ist, kein direktes
    # Objekt. build_graph() erzeugt ihn deshalb bewusst NICHT mehr selbst.
    return graph.compile(checkpointer=checkpointer)
