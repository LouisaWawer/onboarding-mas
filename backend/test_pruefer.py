"""
Testet die Prüfer-Regeln isoliert, ohne API-Calls - schnell, kostenlos,
deterministisch. Läuft VOR dem großen End-to-End-Test sinnvoll, um die
reine Logik (nicht das LLM-Verhalten) abzusichern.

Ausführen: python test_pruefer.py
"""

from agent.graph import pruefer_node


def test_flags_confidence_on_critical():
    state = {
        "messages": [{"role": "assistant", "content": "Ich bin mir zu 80% sicher, dass das klappt."}],
        "pending_action": {"is_critical": True},
        "session_id": "test", "channel": "dm", "current_task": "vpn_zugang",
    }
    result = pruefer_node(state)
    assert result["pruefer_verdict"] == "beanstandung", "sollte L2-Verstoß erkennen"
    print("OK: Konfidenzwert bei kritischer Aussage wird erkannt")


def test_flags_generic_phrase():
    state = {
        "messages": [{"role": "assistant", "content": "Das mache ich aus verschiedenen Gründen so."}],
        "pending_action": {"is_critical": False},
        "session_id": "test", "channel": "dm", "current_task": "vpn_zugang",
    }
    result = pruefer_node(state)
    assert result["pruefer_verdict"] == "beanstandung", "sollte L3-Floskel erkennen"
    print("OK: generische Floskel wird erkannt")


def test_passes_clean_response():
    state = {
        "messages": [{"role": "assistant", "content": "Ich richte den VPN-Zugang jetzt für dich ein."}],
        "pending_action": {"is_critical": True},
        "session_id": "test", "channel": "dm", "current_task": "vpn_zugang",
    }
    result = pruefer_node(state)
    assert result["pruefer_verdict"] == "freigabe", "saubere Antwort sollte durchgehen"
    print("OK: unauffällige Antwort wird freigegeben")


if __name__ == "__main__":
    test_flags_confidence_on_critical()
    test_flags_generic_phrase()
    test_passes_clean_response()
    print("\nAlle Prüfer-Tests bestanden.")
