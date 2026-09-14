"""
Gemeinsame Wort-Normalisierung/-Vergleich für die keyword-basierten
Zuordnungen im Prototyp (Wissensdatenbank-/Intranet-Suche in
knowledge_data.py, Kolleg:innen-Zuordnung in colleague_data.py) - siehe
Bericht an die Nutzerin: zwei unabhängige Kopien derselben Technik wären
genau die Drift-Falle, die in diesem Projekt schon mehrfach zugeschlagen
hat. EINE Quelle, beide Aufrufer importieren - verbessert sich die
Normalisierung hier, ziehen beide Stellen automatisch mit.

Reine Textverarbeitung, kein Sandbox-Tool - deshalb nicht in tools.py.
"""

import re

# Deutsche Flexion (Zugang/Zugänge/Zugängen) unterscheidet sich oft NUR im
# Umlaut - ein reiner Wortgrenzen-/Präfixvergleich ohne Normalisierung
# würde "Zugängen" nie gegen "Zugang" treffen, weil ä und a verschiedene
# Zeichen sind, selbst nach .lower(). Ursprünglich bei find_colleague_for_
# topic gefunden (siehe Bericht an die Nutzerin), betraf aber latent auch
# die Wissensdatenbank-Suche - eine Frage mit "Zugänge" hätte den
# VPN-Artikel vorher ebenfalls nicht gefunden, nur ist das noch niemandem
# aufgefallen.
_UMLAUT_MAP = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})

# Ab wie vielen gemeinsamen Zeichen ein Präfix-Treffer zählt (siehe
# word_matches) - lang genug, um "urlaub" als Anfang von
# "urlaubsregelung" zu erkennen, zu kurz für "regel" als Anfang von
# "regelung" (5 < 6) - das war der ursprüngliche Bug in der Suche.
MIN_PREFIX_LENGTH = 6

# Kurze, nicht vollständige Stoppwortliste (Artikel/Präpositionen/häufige
# Pronomen/Hilfsverben) - deckt ab, was in natürlichsprachlichen
# Formulierungen als Füllwort auftaucht und sonst in praktisch jedem
# Text mitträfe.
STOPWORDS = {
    "der", "die", "das", "den", "dem", "des",
    "ein", "eine", "einen", "einem", "einer", "eines",
    "für", "in", "im", "zu", "zur", "zum",
    "und", "oder", "mit", "von", "vom", "auf", "an", "am",
    "bei", "beim", "nach", "über", "unter", "vor", "durch", "um",
    "ist", "sind", "war", "wird", "werden", "wurde", "hat", "haben",
    "ich", "du", "er", "sie", "es", "wir", "ihr",
    "mein", "meine", "dein", "deine", "sein", "seine", "ihre",
    "nicht", "kein", "keine", "auch", "noch", "nur", "schon",
    "wie", "was", "wer", "wo", "wann", "warum", "dass", "ob",
    "als", "wenn", "aber", "doch", "so", "kann", "kannst",
    "mir", "dir", "ihm", "ihnen", "uns", "euch",
}


def normalize_word(word: str) -> str:
    """Kleinschreibung + Umlaut-Normalisierung. Erwartet bereits ein
    einzelnes Wort (kein Satz) - für Sätze siehe tokenize()."""
    return word.lower().translate(_UMLAUT_MAP)


def tokenize(text: str, *, filter_stopwords: bool = True) -> set[str]:
    """Wortgrenzen statt Teilstring: exakte Wörter, Bindestriche trennen
    ("VPN-Zugang" -> "vpn"/"zugang", sonst träfe ein Suchwort wie "VPN"
    allein nie), Umlaute normalisiert. Stoppwörter werden VOR der
    Normalisierung geprüft (die Liste selbst ist normal geschrieben, z.B.
    "für" mit Umlaut - würde sonst nicht mehr matchen)."""
    words = re.findall(r"[a-zäöüß]+", text.lower())
    if filter_stopwords:
        words = [w for w in words if w not in STOPWORDS]
    return {normalize_word(w) for w in words}


def word_matches(a: str, b: str) -> bool:
    """a/b müssen bereits normalisiert sein (siehe normalize_word/
    tokenize). Exakte Gleichheit ODER ein gemeinsames Präfix ab
    MIN_PREFIX_LENGTH Zeichen - siehe dortigen Kommentar."""
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) < MIN_PREFIX_LENGTH:
        return False
    return longer.startswith(shorter)


def any_word_matches(words_a: set[str], words_b: set[str]) -> bool:
    return any(word_matches(a, b) for a in words_a for b in words_b)
