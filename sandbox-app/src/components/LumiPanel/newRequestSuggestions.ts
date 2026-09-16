/**
 * Allgemeine Einstiegsvorschläge beim Öffnen einer NEUEN, noch leeren
 * Anfrage im Panel - unabhängig vom Screen. Anderer Mechanismus als die
 * bildschirmspezifischen Vorschläge in api/suggestion_policy.py (dort:
 * Verweildauer auf einem der vier Sandbox-Screens, vier Einträge, siehe
 * Bericht an die Nutzerin - die beiden Mechanismen nicht vermischen).
 *
 * `displayed` (angezeigte Zeile) 1:1 aus dem Design übernommen (ConfirmationCard,
 * node 219:4794, type=options) statt neu erfunden - deckt sich mit Lumis
 * Willkommensnachricht im Chat und den ersten Onboarding-Schritten.
 *
 * `submitted` (abgeschickter Text) weicht seit Schritt 6 für den
 * Knowledge-Hub-Eintrag bewusst vom angezeigten Text ab (bei den anderen
 * beiden ist es weiterhin derselbe Text, kein Sonderfall dafür nötig): "Knowledge-Hub
 * durchsuchen" ist als AUFTRAG formuliert, enthält aber kein Suchthema -
 * info_agent_node (graph.py) hätte darauf ohne Thema zwingend leer gesucht.
 * Der abgeschickte Text ist deshalb bewusst vage gehalten (klingt, als hätte
 * die Person ihn selbst getippt), damit die neue deterministische
 * Themen-Erkennung dort korrekt die Rückfrage auslöst, statt eine leere
 * Suche zu erzwingen - siehe _has_recognizable_search_topic()/
 * NO_SEARCH_TOPIC_RESPONSE in graph.py für die andere Hälfte des Fixes.
 */
export type NewRequestSuggestion = {
  displayed: string
  submitted: string
}

export const NEW_REQUEST_SUGGESTIONS: NewRequestSuggestion[] = [
  { displayed: 'VPN-Zugang einrichten', submitted: 'VPN-Zugang einrichten' },
  {
    displayed: 'Kennenlern-Termin in den Kalender eintragen',
    submitted: 'Kennenlern-Termin in den Kalender eintragen',
  },
  {
    displayed: 'Knowledge-Hub durchsuchen',
    submitted: 'Ich würde gern im Knowledge-Hub etwas nachschlagen.',
  },
]
