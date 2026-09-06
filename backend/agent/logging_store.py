"""
Logging-Infrastruktur für Interaktionsdaten (siehe Setup_Dokumentation.md, Abschnitt 8).

Kategorien werden STRUKTURELL aus dem Graphen abgeleitet, nicht nachträglich
aus dem generierten Text geraten:
  - "confirm"     -> Knoten mit interrupt()-Aufruf
  - "autonomous"  -> Aktion ohne vorherigen interrupt() im Pfad
  - "explain"     -> direkt aus transparency_level ableitbar
"""

import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "interaction_log.jsonl"


def log_interaction(
    category,
    node: str,
    session_id: str,
    task: str | None = None,
    channel: str | None = None,
    **extra,
) -> None:
    """Schreibt einen strukturierten Log-Eintrag als JSON-Zeile."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "category": category,  # str oder Liste, z.B. ["explain", "confirm"]
        "node": node,
        "task": task,
        "channel": channel,    # "dm" | "status_panel"
        **extra,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
