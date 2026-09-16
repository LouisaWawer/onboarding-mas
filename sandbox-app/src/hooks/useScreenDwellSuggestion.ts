import { useEffect, useRef } from 'react'
import { useAgentState } from '../state/AgentState'
import { useNavigation } from '../state/Navigation'

const DWELL_MS = 9000
const DWELL_SCREENS = ['intranet', 'hub', 'tickets', 'calendar'] as const
type DwellScreen = (typeof DWELL_SCREENS)[number]

function isDwellScreen(screen: string): screen is DwellScreen {
  return (DWELL_SCREENS as readonly string[]).includes(screen)
}

/**
 * Verweildauer-Timer für proaktive Screenwechsel-Vorschläge (Guideline 21,
 * siehe Bericht an die Nutzerin, Schritt 6) - EIN zentraler Hook, in
 * App.tsx eingehängt, statt in jedem der vier Screens einzeln dupliziert.
 * Timer sitzt bewusst im FRONTEND (siehe suggestion_policy.py/
 * Setup_Dokumentation.md Abschnitt 7): POST /session/{id}/screen bedeutet
 * "hier wurde lange genug verweilt", nicht "jemand ist hier". 'chat' startet
 * nie einen eigenen Timer (isDwellScreen) - dort gibt es keinen Vorschlag.
 *
 * Aufräumen beim Verlassen EINES der vier Dwell-Screens macht ZWEI Dinge:
 * - clearTimeout(), falls er noch nicht gefeuert hat (Person war zu kurz da)
 * - markSessionSeen() - verwirft einen ggf. gerade angezeigten Vorschlag
 *   (siehe Bericht an die Nutzerin: "Ich sehe du bist im Kalender" stimmt
 *   nicht mehr, wenn die Person längst woanders ist - Guideline 3, ein
 *   Hinweis vergeht mit seinem Anlass) - AUSSER das Ziel ist der Chat
 *   (Bugfix nach dem ersten Testlauf, siehe Bericht an die Nutzerin): der
 *   Chat ist kein "anderer Screen" im Sinne der Regel, sondern der Ort, an
 *   dem der Vorschlag aufgegriffen wird - wer ihn sieht und in den Chat
 *   wechselt, will ihn vermutlich gerade annehmen, ihn genau dabei
 *   wegzunehmen wäre falsch. Verlässt die Person DANACH auch den Chat
 *   wieder (zu einem dritten Screen), OHNE den Vorschlag angeklickt/
 *   geschlossen zu haben, gilt die normale Regel wieder ganz normal - der
 *   Chat selbst ist jetzt Teil des Aufräum-Zyklus (siehe Ternary unten:
 *   `timer` bleibt undefined für 'chat', ein Cleanup wird aber trotzdem
 *   registriert).
 *
 * ZWEITE Ausnahme (siehe Bericht an die Nutzerin, nach dem Randfall
 * Kalender -> Chat -> zurück zu Kalender): auch verwerfen überspringen,
 * wenn das ZIEL genau der Screen ist, auf den sich die aktuell angezeigte
 * Karte bezieht (displayedSuggestionRef.current?.screen === Ziel) -
 * unabhängig davon, ob der Weg dahin über den Chat lief. Begründung: der
 * Anlass ist dort nicht vergangen, sondern wieder da - die Person kommt
 * womöglich genau deshalb zurück, weil sie den Vorschlag aufgreifen will.
 * Gilt allgemein (nicht nur nach einem Chat-Umweg), z.B. auch bei einem
 * direkten Kalender -> Tickets -> Kalender ohne Chat dazwischen - dort
 * wurde die Karte aber beim ersten Verlassen (Kalender -> Tickets) bereits
 * regulär verworfen, die Ausnahme greift dann folgerichtig nicht mehr
 * (displayedSuggestion ist zu diesem Zeitpunkt schon null).
 *
 * activeScreenRef (statt activeScreen direkt im Cleanup zu lesen): eine
 * Cleanup-Funktion schließt über die Werte VOM MOMENT DER EFFEKT-ERSTELLUNG,
 * bräuchte man also den VORHERIGEN Screen. Hier wird aber das ZIEL
 * gebraucht (wohin wird gerade gewechselt) - der Ref wird bei JEDEM Render
 * synchron aktualisiert, ist beim Cleanup-Lauf (der nach dem Render mit dem
 * NEUEN activeScreen passiert) also bereits der neue Wert.
 *
 * Das "einmal pro Screen pro Session" (suggested_screens-Tabelle,
 * store.py) ist von alldem strukturell unabhängig (eigene Tabelle, von
 * set_pending_suggestion() nie berührt, siehe dort) - wird durch das
 * Verwerfen NICHT ausgehebelt.
 */
export function useScreenDwellSuggestion(): void {
  const { activeScreen } = useNavigation()
  const { reportScreenDwell, markSessionSeen, displayedSuggestion } = useAgentState()
  // Aktuelle Funktionsreferenzen/-werte für den Timeout-Callback/Cleanup
  // unten, ohne sie in die Dependency-Liste des Effekts aufnehmen zu
  // müssen - sonst würde jede Neuerzeugung von reportScreenDwell/
  // markSessionSeen (z.B. wenn sessionId erst nach dem Bootstrap verfügbar
  // wird) ODER jede Änderung von displayedSuggestion den laufenden Timer
  // verwerfen und neu starten.
  const reportRef = useRef(reportScreenDwell)
  const seenRef = useRef(markSessionSeen)
  const activeScreenRef = useRef(activeScreen)
  const displayedSuggestionRef = useRef(displayedSuggestion)
  reportRef.current = reportScreenDwell
  seenRef.current = markSessionSeen
  activeScreenRef.current = activeScreen
  displayedSuggestionRef.current = displayedSuggestion

  useEffect(() => {
    const timer = isDwellScreen(activeScreen)
      ? setTimeout(() => {
          reportRef.current(activeScreen).catch((err) => console.error('[dwell] reportScreenDwell fehlgeschlagen', err))
        }, DWELL_MS)
      : undefined

    return () => {
      if (timer) clearTimeout(timer)
      const destination = activeScreenRef.current
      if (destination === 'chat') return
      if (displayedSuggestionRef.current?.screen === destination) return
      seenRef.current().catch((err) => console.error('[dwell] markSessionSeen fehlgeschlagen', err))
    }
  }, [activeScreen])
}
