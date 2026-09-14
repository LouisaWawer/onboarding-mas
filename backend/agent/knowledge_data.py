"""
Strukturierte Inhalte aus Knowledge_Hub_Inhalte.md und Intranet_Inhalte.md.

Diese Datei hält die Artikel/Beiträge als durchsuchbare Datenstruktur bereit,
damit der Agent echte Inhalte findet statt sie zu erfinden. Bei neuen
Artikeln: hier ergänzen (Inhalt bleibt mit den .md-Dateien synchron halten).
"""

KNOWLEDGE_ARTICLES = [
    {
        "id": "urlaub-beantragen",
        "title": "Urlaub beantragen",
        "path": "HR / Abwesenheit / Urlaub",
        "category": "HR",
        # summary bleibt die kurze Zeile für die Keyword-Suche (siehe
        # search_knowledge_and_intranet unten) - body ist NEU: der volle
        # Artikeltext aus Knowledge_Hub_Inhalte.md (der maßgeblichen
        # Quelle, siehe Bericht an die Nutzerin), den info_agent_node
        # tatsächlich in den Prompt-Kontext gibt. Vorher gab es nur die
        # eine Zeile - Fragen wie "wie lange kann ich Resturlaub nehmen"
        # liefen strukturell ins Leere, nicht weil die Suche versagte,
        # sondern weil die Information nirgends in der Datenbasis stand.
        "summary": "Für einen Urlaubsantrag wird ein Ticket an HR angelegt (Zeitraum, Genehmigung durch die Teamleitung, Fristen, Resturlaub).",
        "body": (
            "Hier erfährst du, wie ein Urlaubsantrag abläuft.\n\n"
            "So läuft das ab:\n"
            "1. Für einen Urlaubsantrag wird ein Ticket an HR angelegt, mit "
            "dem gewünschten Zeitraum (Start- und Enddatum).\n"
            "2. Deine Teamleitung erhält automatisch eine Benachrichtigung "
            "und muss den Antrag genehmigen.\n"
            "3. Nach der Genehmigung wird der Urlaub automatisch in den "
            "Kalender eingetragen.\n\n"
            "Fristen:\n"
            "- Bis zu 5 Tagen Urlaub: möglichst 1 Woche im Voraus "
            "beantragen\n"
            "- Längere Urlaube (mehr als 5 Tage): mindestens 4 Wochen im "
            "Voraus, besonders in der Ferienzeit\n\n"
            "Genehmigung:\n"
            "Ein Antrag wird von der direkten Teamleitung geprüft. Bei "
            "Rückfragen (z.B. bei Terminüberschneidungen im Team) meldet "
            "sie sich direkt im Chat. Die Bearbeitung dauert in der Regel "
            "1-2 Werktage.\n\n"
            "Resturlaub:\n"
            "Nicht genommener Urlaub kann bis zum 31. März des "
            "Folgejahres übertragen werden. Danach verfällt er "
            "automatisch.\n\n"
            "Sonderfälle:\n"
            "Für Urlaub aus besonderem Anlass (z.B. Hochzeit, Umzug) gilt "
            "eine eigene Regelung."
        ),
    },
    {
        "id": "vpn-zugang",
        # Titel bewusst "VPN-Zugang" (nicht "VPN-Zugang einrichten" wie im
        # alten Platzhalter-Kommentar) - deckungsgleich mit der Überschrift
        # in Knowledge_Hub_Inhalte.md.
        "title": "VPN-Zugang",
        "path": "IT / Zugänge / VPN",
        "category": "IT",
        "summary": "Für den VPN-Zugang wird ein Ticket bei der IT angelegt (Kategorie IT-Zugänge), das in der Regel noch am selben Tag bearbeitet wird.",
        "body": (
            "Hier erfährst du, wie der VPN-Zugang für neue "
            "Mitarbeiter:innen eingerichtet wird.\n\n"
            "So läuft das ab:\n"
            "1. Für den VPN-Zugang wird ein Ticket bei der IT angelegt "
            "(Kategorie: IT-Zugänge).\n"
            "2. Die IT bearbeitet eingehende Zugangs-Tickets in der Regel "
            "zeitnah am selben Tag.\n"
            "3. Sobald der Zugang eingerichtet ist, gibt es dazu eine "
            "Rückmeldung im Ticket.\n\n"
            "Wichtig:\n"
            "- Ohne VPN-Zugang sind bestimmte interne Tools eingeschränkt "
            "erreichbar - etwa während geplanter Wartungsfenster.\n"
            "- Bei Rückfragen zu einem laufenden Ticket meldet sich die "
            "IT direkt im Chat."
        ),
    },
]

INTRANET_POSTS = [
    {
        "title": "Save the Date: Sommerfest am 15. September",
        "author": "Anna Schmidt",
        "category": "Ankündigung",
        "summary": "Firmenfest mit Live-Musik und Grill auf der Dachterrasse.",
    },
    {
        "title": "IT-Wartungsfenster am kommenden Wochenende",
        "author": "Max Vogel",
        "category": "Ankündigung",
        "summary": "Geplante Wartung, VPN/Tools ggf. eingeschränkt erreichbar.",
    },
    {
        "title": "Neue Kaffeemaschine im 3. Stock",
        "author": "Tom Bauer",
        "category": "Ankündigung",
        "summary": "Neue Maschine inkl. Hafermilch-Option verfügbar.",
    },
]


# Wort-Normalisierung/-Vergleich (Wortgrenzen, Stoppwörter, Umlaut- und
# Präfixvergleich) liegt gemeinsam mit colleague_data.py in text_matching.py
# (siehe Bericht an die Nutzerin: eine Quelle statt zwei Kopien derselben
# Technik).
from .text_matching import tokenize, word_matches


def search_knowledge_and_intranet(query: str, top_k: int = 3) -> list[dict]:
    """Einfache Keyword-Suche über Titel + Zusammenfassung - bewusst NICHT
    über body (siehe Bericht an die Nutzerin): body ist unkuratierter
    Volltext, würde bei mehr Wörtern automatisch mehr zufällige Treffer
    anhäufen als die dichte, extra für die Suche geschriebene summary -
    body ist Kontext NACH der Auswahl, kein Kriterium FÜR sie. Titel-Treffer
    zählen doppelt (eindeutigstes Relevanzsignal), Summary-Treffer einfach.
    Score > 0 ist nach Wortgrenzen+Stoppwörtern bereits ein echter
    Mindest-Score - anders als vorher trägt kein Füllwort mehr bei, jeder
    verbleibende Treffer ist ein tatsächliches Inhaltswort.

    Bewusst simpel (keine Embeddings/Vektorsuche) - für die überschaubare
    Anzahl Artikel im Prototyp ausreichend. Bei Bedarf später durch
    semantische Suche ersetzbar, ohne die Tool-Schnittstelle zu ändern.
    """
    query_words = tokenize(query)
    if not query_words:
        return []

    all_content = [{**a, "source": "knowledge_hub"} for a in KNOWLEDGE_ARTICLES] + [
        {**p, "source": "intranet"} for p in INTRANET_POSTS
    ]

    scored = []
    for item in all_content:
        title_words = tokenize(item["title"])
        summary_words = tokenize(item.get("summary", ""))
        score = 0
        for qw in query_words:
            if any(word_matches(qw, tw) for tw in title_words):
                score += 2
            elif any(word_matches(qw, tw) for tw in summary_words):
                score += 1
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]
