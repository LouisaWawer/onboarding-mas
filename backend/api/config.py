"""
Environment-Konfiguration für die API-Schicht. Zentral hier statt verteilt
über die Module, damit auf einen Blick klar ist, welche Env-Vars es gibt.

WICHTIG: load_dotenv() wird bereits in agent/graph.py aufgerufen (siehe
dortigen Kommentar) - server.py importiert graph.py vor diesem Modul,
daher ist .env hier bereits eingelesen. Trotzdem KEIN Secret hier fest
verdrahten.
"""

import os
import secrets
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Zugangscode fürs Anlegen einer Session (POST /session) - schützt den
# Anthropic-Key vor Fremdnutzung, siehe Auftrag Punkt 1. Bewusst OHNE
# Default: ist die Variable nicht gesetzt, schlägt JEDE Session-Anlage fehl
# (fail closed), statt versehentlich offen zu sein.
STUDY_ACCESS_CODE = os.getenv("STUDY_ACCESS_CODE", "")

# LangGraph-Checkpoints (eine Zeile pro Graph-Schritt/Thread) - eigene Datei,
# getrennt von den Session-/Anfragen-Metadaten (siehe store.py), damit
# LangGraphs eigene Tabellenverwaltung (SqliteSaver.setup()) nicht mit
# unseren eigenen Tabellen im selben File kollidieren kann.
CHECKPOINTS_DB_PATH = os.getenv(
    "CHECKPOINTS_DB_PATH", str(BACKEND_DIR / "checkpoints.sqlite")
)

# Sessions/Anfragen/Rationale-Spiegel (siehe store.py).
APP_DB_PATH = os.getenv("APP_DB_PATH", str(BACKEND_DIR / "app_meta.sqlite"))

# Nutzerstudie testet EINE Variante, keinen 3x3-Vergleich (siehe
# Setup_Dokumentation.md Abschnitt 7) - daher fixe Default-Werte statt
# einer Wahlmöglichkeit pro Request. Über Env-Var änderbar, falls die
# konkrete Konfiguration noch nicht feststeht.
DEFAULT_TRANSPARENCY_LEVEL = os.getenv("DEFAULT_TRANSPARENCY_LEVEL", "medium")
DEFAULT_CONTROL_LEVEL = os.getenv("DEFAULT_CONTROL_LEVEL", "high")

# Gebauter Vite-Output von sandbox-app, siehe Auftrag Punkt 9.
SANDBOX_DIST_DIR = Path(
    os.getenv("SANDBOX_DIST_DIR", str(BACKEND_DIR.parent / "sandbox-app" / "dist"))
)


def access_code_is_valid(code: str) -> bool:
    """Konstante Laufzeit-Vergleich (secrets.compare_digest) - kein
    Passwort-Hashing nötig (siehe Auftrag: "mehr soll es nicht sein"),
    aber ein simpler '==' wäre unnötig anfällig für Timing-Angriffe."""
    if not STUDY_ACCESS_CODE:
        return False
    return secrets.compare_digest(code, STUDY_ACCESS_CODE)
