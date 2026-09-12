"""
Logging-Infrastruktur für Interaktionsdaten (siehe Setup_Dokumentation.md, Abschnitt 8).

Kategorien werden STRUKTURELL aus dem Graphen abgeleitet, nicht nachträglich
aus dem generierten Text geraten:
  - "confirm"     -> Knoten mit interrupt()-Aufruf
  - "autonomous"  -> Aktion ohne vorherigen interrupt() im Pfad
  - "explain"     -> direkt aus transparency_level ableitbar

WICHTIG zu session_id vs. api_session_id (siehe Setup_Dokumentation.md,
Abschnitt 7): `session_id` trägt bei JEDER Kategorie außer
"suggestion_shown"/"suggestion_accepted" die LangGraph-`thread_id` (=
eine Anfrage) - das ist die durchgängige Bedeutung dieses Felds im
gesamten Log. Für "suggestion_shown"/"suggestion_accepted" gibt es KEINE
thread_id (der Vorschlag entsteht vor jeder Anfrage) - dort ist
`session_id` bewusst None, und die tatsächliche API-Session-ID steht
stattdessen im SEPARATEN Feld `api_session_id`. Bewusst KEIN
Wiederverwenden/Umwidmen von `session_id` für diese zwei Kategorien -
ein Feld, das je nach `category` etwas anderes bedeutet, ist genau die
Art Mehrdeutigkeit, die bei einer späteren Auswertung (z.B. ein
naives `groupby(session_id)`) zwei unterschiedliche ID-Räume
unbemerkt vermischen würde.
"""

import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "interaction_log.jsonl"


def log_interaction(
    category,
    node: str | None,
    session_id: str | None,
    task: str | None = None,
    channel: str | None = None,
    **extra,
) -> None:
    """Schreibt einen strukturierten Log-Eintrag als JSON-Zeile.

    node/session_id sind bewusst Optional (statt str): "suggestion_shown"/
    "suggestion_accepted" haben keinen Knoten und keine thread_id (siehe
    Moduldocstring) - eine feste str-Vorgabe hätte diese beiden Kategorien
    gezwungen, etwas Falsches einzutragen, statt ehrlich None zu sein."""
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
