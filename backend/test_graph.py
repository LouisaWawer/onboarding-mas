"""
End-to-End-Test des Graphen (Supervisor -> Infrastructure-Agent -> Prüfer ->
Kontext-Check -> human_review/updated_query -> execute_action).

Ausführen: python test_graph.py
Bei einem interrupt() wirst du im Terminal nach deiner Entscheidung gefragt.
"""

import uuid
from agent.graph import build_graph
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command


def run_test():
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    initial_state = {
        "messages": [{"role": "user", "content": "Ich brauche VPN-Zugang, kannst du das einrichten?"}],
        "session_id": session_id,
        "current_task": None,
        "active_agent": "",
        "transparency_level": "medium",
        "control_level": "high",
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

    # WICHTIG: from_conn_string ist in aktuellen langgraph-Versionen ein
    # Context-Manager - die Verbindung muss über die GESAMTE Testlauf-Dauer
    # offen bleiben (mehrere invoke()-Aufrufe bei Interrupt/Resume), deshalb
    # liegt der komplette Testlauf innerhalb dieses with-Blocks.
    with SqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
        graph = build_graph(checkpointer)

        print("=== Starte Graph ===")
        result = graph.invoke(initial_state, config)
        _print_state(result)

        while "__interrupt__" in result:
            interrupt_data = result["__interrupt__"][0].value
            print("\n--- INTERRUPT: der Graph wartet auf dich ---")
            print("Vorschlag:", interrupt_data.get("proposal"))
            if interrupt_data.get("change_notice"):
                print("Hinweis auf Änderung:", interrupt_data["change_notice"])
            print("Optionen:", interrupt_data.get("options"))

            decision = input("Deine Entscheidung (genauen Options-Text eingeben): ")
            result = graph.invoke(Command(resume=decision), config)
            _print_state(result)

        print("\n=== Graph beendet ===")
        print("Finaler Sandbox-Zustand:", result.get("sandbox_state"))


def _print_state(result):
    print(f"\n[Status] aktiver Agent: {result.get('active_agent')} | Statuspunkt: {result.get('dot_status')}")
    if result.get("messages"):
        last = result["messages"][-1]
        print(f"[Letzte Nachricht - {last['role']}]: {last['content'][:200]}")
    if result.get("pruefer_verdict"):
        print(f"[Prüfer]: {result['pruefer_verdict']} {result.get('pruefer_issues')}")


if __name__ == "__main__":
    run_test()

