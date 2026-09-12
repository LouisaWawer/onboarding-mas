"""
Graph-Level-Test für context_recheck_node (G13, "geänderter Kontext"-Fall,
siehe agent/graph.py). Reiner Python-Test mit direktem graph.invoke()/
graph.update_state()-Zugriff (wie test_graph.py) - NICHT über die HTTP-API
(test_api_manual.py), weil dort keine Stelle existiert, die sandbox_state
von außen verändern kann. sandbox_state wird ausschließlich durch
AVAILABLE_TOOLS-Aufrufe innerhalb von execute_action_node verändert (siehe
tools.py) - kein Endpoint nimmt einen Sandbox-Zustand vom Client entgegen.

graph.update_state() ist LangGraphs eigene, öffentliche API für genau
diesen Zweck: einen Checkpoint zwischen zwei Schritten von außen zu
verändern. Kein Test-Hook in graph.py, kein erfundener Umweg.

WICHTIG, WAS DIESER TEST BEWEIST UND WAS NICHT (siehe Bericht an die
Nutzerin - ohne diesen Hinweis liest jemand den grünen Test später als
Beleg für das Falsche):

  BEWEIST: context_recheck_node erkennt eine Sandbox-Änderung korrekt und
  routet zum bestehenden updated_query_node (zweiter Interrupt mit
  change_notice, "trotzdem bestätigen"/"abbrechen"), WENN eine Änderung
  zwischen der ersten Bestätigung und der Ausführung eintrifft.

  BEWEIST NICHT, dass im laufenden Studienbetrieb tatsächlich etwas
  sandbox_state während eines wartenden interrupt() ändern kann. Das ist
  beim aktuellen, streng sequenziellen Ausführungsmodell (ein Thread läuft
  synchron bis zum nächsten interrupt(), nichts läuft "nebenher", andere
  Threads haben isolierten sandbox_state) strukturell ausgeschlossen - es
  gibt aktuell keinen Kanal zwischen der Sandbox-UI und
  state["sandbox_state"] (siehe Setup_Dokumentation.md). update_state()
  hier simuliert, was ein KÜNFTIGER Sync-Kanal liefern würde - der Test
  belegt die Korrektheit von context_recheck_node, nicht die Erreichbarkeit
  dieses Pfads durch echte Nutzeraktionen in der Studie.

Ausführen: python test_context_recheck.py
"""

import uuid

from agent.graph import build_graph
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command


def test_context_recheck_erkennt_aenderung_und_routet_zu_updated_query() -> None:
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    initial_state = {
        "messages": [{"role": "user", "content": "Ich brauche VPN-Zugang, kannst du das einrichten?"}],
        "session_id": session_id,
        "current_task": None,
        "active_agent": "",
        "transparency_level": "medium",
        "control_level": "medium",
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

    with SqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
        graph = build_graph(checkpointer)

        # --- 1. Erster Interrupt (human_review), create_ticket ist bei
        # control_level="medium" kritisch (is_critical=True) und wartet. ---
        result = graph.invoke(initial_state, config)
        assert "__interrupt__" in result, f"erwartet ersten Interrupt (human_review), bekam: {result}"
        interrupt_data = result["__interrupt__"][0].value
        proposal = interrupt_data.get("proposal") or {}
        assert proposal.get("tool") == "create_ticket", f"erwartet create_ticket-Vorschlag, bekam: {proposal}"
        print(f"[ok] erster Interrupt (human_review): {proposal}")

        # --- 2. Sandbox-Änderung injizieren, WÄHREND der erste Interrupt
        # wartet - simuliert, was ein künftiger Sync-Kanal liefern würde
        # (siehe Moduldocstring: Grenze dessen, was dieser Test beweist). ---
        live_sandbox_state = dict(graph.get_state(config).values["sandbox_state"])
        live_sandbox_state["tickets"] = list(live_sandbox_state.get("tickets", [])) + [
            {
                "id": "N9999",
                "date": "01.01.",
                "subject": "Fremdes Ticket (von außen injiziert)",
                "department": "IT",
                "status": "offen",
                "is_new": True,
            }
        ]
        graph.update_state(config, {"sandbox_state": live_sandbox_state})
        print(f"[ok] sandbox_state extern verändert, tickets_count jetzt: {len(live_sandbox_state['tickets'])}")

        # --- 3. Ersten Interrupt bestätigen -> darf NICHT direkt ausführen,
        # context_recheck_node muss die Änderung erkennen und zu
        # updated_query_node routen (zweiter Interrupt). ---
        result = graph.invoke(Command(resume="bestätigen"), config)
        assert "__interrupt__" in result, (
            f"erwartet zweiten Interrupt (updated_query) nach erkannter Änderung, bekam: {result}"
        )
        interrupt_data = result["__interrupt__"][0].value
        assert interrupt_data.get("change_notice"), f"zweiter Interrupt hat keinen change_notice: {interrupt_data}"
        assert "trotzdem bestätigen" in interrupt_data.get("options", []), (
            f"erwartet 'trotzdem bestätigen' als Option: {interrupt_data}"
        )
        print(f"[ok] zweiter Interrupt (updated_query) mit change_notice: {interrupt_data['change_notice']}")

        # --- 4. Zweiten Interrupt bestätigen -> jetzt läuft execute_action,
        # Graph endet (kein weiterer Interrupt). ---
        result = graph.invoke(Command(resume="trotzdem bestätigen"), config)
        assert "__interrupt__" not in result, f"erwartet Graph-Ende, aber noch ein Interrupt: {result}"
        assert result.get("pending_action") is None
        tickets = result["sandbox_state"].get("tickets", [])
        assert len(tickets) >= 2, f"erwartet mind. 2 Tickets (injiziertes + neu erstelltes), bekam: {tickets}"
        print(f"[ok] nach zweiter Bestätigung: pending_action=None, {len(tickets)} Tickets in sandbox_state")

    print("\n=== context_recheck_node erkennt Änderung und routet korrekt: GRÜN ===")


def test_context_recheck_ohne_aenderung_fuehrt_direkt_aus() -> None:
    """Gegenprobe: OHNE injizierte Änderung darf context_recheck_node NICHT
    zu updated_query routen - direkte Ausführung nach der ersten
    Bestätigung, wie vor dieser Änderung."""
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    initial_state = {
        "messages": [{"role": "user", "content": "Ich brauche VPN-Zugang, kannst du das einrichten?"}],
        "session_id": session_id,
        "current_task": None,
        "active_agent": "",
        "transparency_level": "medium",
        "control_level": "medium",
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

    with SqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
        graph = build_graph(checkpointer)

        result = graph.invoke(initial_state, config)
        assert "__interrupt__" in result, f"erwartet ersten Interrupt (human_review), bekam: {result}"
        print("[ok] erster Interrupt (human_review), keine Änderung injiziert")

        result = graph.invoke(Command(resume="bestätigen"), config)
        assert "__interrupt__" not in result, (
            f"erwartet Graph-Ende ohne zweiten Interrupt (keine Änderung), bekam: {result}"
        )
        assert result.get("pending_action") is None
        tickets = result["sandbox_state"].get("tickets", [])
        assert len(tickets) == 1, f"erwartet genau 1 Ticket, bekam: {tickets}"
        print(f"[ok] ohne Änderung: direkt ausgeführt, {len(tickets)} Ticket, kein zweiter Interrupt")

    print("\n=== context_recheck_node ohne Änderung führt direkt aus: GRÜN ===")


if __name__ == "__main__":
    test_context_recheck_erkennt_aenderung_und_routet_zu_updated_query()
    test_context_recheck_ohne_aenderung_fuehrt_direkt_aus()
    print("\n2/2 Schritte grün.")
