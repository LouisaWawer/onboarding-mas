import { useEffect, useState } from 'react'
import { ArrowSquareIn, ChatTeardropText, Minus, PaperPlaneRight } from '@phosphor-icons/react'
import LumiAvatar from '../LumiAvatar/LumiAvatar'
import LumiConversation from '../LumiConversation/LumiConversation'
import { NEW_REQUEST_SUGGESTIONS } from './newRequestSuggestions'
import { useAgentState } from '../../state/AgentState'
import { useNavigation } from '../../state/Navigation'
import './LumiPanel.css'

type LumiPanelProps = {
  onClose: () => void
}

/**
 * Das schwebende Panel (Figma: LumiChat_Floating, node 194:2892) - zeigt
 * DIESELBE aktive Anfrage wie der Chat-Screen. Zwei Zustände, Property
 * "state" im Design: "newRequest" (die aktive Anfrage hat noch KEINE
 * Nachrichten) und "existingRequest" (hat welche) - siehe Bericht an die
 * Nutzerin für die volle Design-Beschreibung.
 *
 * Anfragen-Dropdown bewusst ohne Funktion (Backlog) - die Pille zeigt nur
 * den im Design vorgegebenen FESTEN Zustandstext ("Neue Anfrage"/
 * "Kürzlich gestellte Anfrage"), NICHT den Anfrage-Titel.
 *
 * Design-Fund (siehe Bericht an die Nutzerin, Schritt 5): die "conf=true"-
 * Zustände von LumiChat_Floating sind eine Instanz der ConfirmationCard-
 * Variante "type=options" (node 219:4794) - zu unterscheiden von den
 * newRequest-Einstiegsvorschlägen (NEW_REQUEST_SUGGESTIONS, eigener
 * Mechanismus) UND von der normalen Bestätigungskarte (type=confirmation).
 * Seit Schritt 6 EINE ihrer beiden Verwendungen gebaut (proaktiver
 * Screenwechsel-Vorschlag, über OptionsCard.tsx/LumiConversation.tsx - die
 * Karte selbst sitzt dort im Nachrichtenverlauf, nicht hier im Panel-
 * Rahmen). Die zweite Verwendung (Teilschritt-Auswahl) bleibt Backlog.
 *
 * displayedSuggestion (siehe AgentState.tsx - NICHT pendingSuggestion, das
 * speist nur den peripheren Punkt) ist SESSION-, nicht Anfrage-gebunden -
 * kann also auch dann anstehen, wenn die aktive Anfrage selbst noch leer
 * ist. Deshalb unten `hasMessages || displayedSuggestion` statt nur
 * `hasMessages`: sonst wäre die Karte unsichtbar, solange die aktive
 * Anfrage zufällig gerade leer ist (LumiConversation zeigt bei leerem
 * Verlauf einfach nur SparkleIndicator+Karte+Composer, kein Sonderfall
 * nötig).
 */
export default function LumiPanel({ onClose }: LumiPanelProps) {
  const { activeThreadId, anfragen, createAnfrage, sendMessage, displayedSuggestion, acknowledgeSuggestion } =
    useAgentState()
  const { navigateTo } = useNavigation()
  const [emptyDraft, setEmptyDraft] = useState('')

  const activeAnfrage = activeThreadId ? anfragen[activeThreadId] : undefined
  const hasMessages = (activeAnfrage?.messages.length ?? 0) > 0
  const showConversation = hasMessages || Boolean(displayedSuggestion)

  // "Beim Öffnen des Panels" (siehe Bericht an die Nutzerin, Schritt 6) -
  // NUR der Backend-Aufruf (Statuspunkt hört auf zu signalisieren), KEIN
  // lokales Löschen von pendingSuggestion (siehe acknowledgeSuggestion-
  // Docstring, AgentState.tsx) - sonst wäre die Karte schon weg, bevor sie
  // überhaupt sichtbar wird. LumiPanel mountet nur, wenn panelOpen true ist
  // (siehe StatusDot.tsx), ein leeres Deps-Array feuert also genau einmal
  // pro tatsächlichem Öffnen.
  useEffect(() => {
    acknowledgeSuggestion().catch((err) => console.error('[lumi-panel] acknowledgeSuggestion fehlgeschlagen', err))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleNewAnfrage() {
    try {
      await createAnfrage()
    } catch (err) {
      console.error('[lumi-panel] createAnfrage fehlgeschlagen', err)
    }
  }

  function handleExpandToChat() {
    navigateTo('chat')
    onClose()
  }

  // Klickverhalten (siehe Bericht an die Nutzerin): direkt senden, wie
  // beim bestehenden Screenwechsel-Vorschlag - kein Zwischenschritt über
  // das Eingabefeld. Bewusst OHNE suggestionScreen-Parameter: das ist ein
  // eigener Mechanismus (siehe newRequestSuggestions.ts), keine Variante
  // des Screen-Vorschlags, soll also auch nicht als "suggestion_accepted"
  // mit einer Screen-ID geloggt werden.
  async function handleSend(text: string) {
    const trimmed = text.trim()
    if (!trimmed) return
    try {
      await sendMessage(trimmed)
    } catch (err) {
      console.error('[lumi-panel] Nachricht senden fehlgeschlagen', err)
    }
  }

  return (
    <div className="lumi-panel">
      <div className="lumi-panel__topbar">
        {/* Kein Avatar in der Topbar im newRequest-Zustand (siehe Design) -
            der große Avatar unten in der Fläche übernimmt das dort. */}
        {hasMessages && <LumiAvatar size={32} />}
        <span className="lumi-panel__title">
          {/* existingRequest: echter Anfrage-Titel statt der festen
              Pillen-Beschriftung (siehe Bericht an die Nutzerin) - die
              Pille ist im Design ein noch unfunktionales Dropdown zur
              Anfragen-Auswahl, ihr fester Text ("Kürzlich gestellte
              Anfrage") ist dessen Beschriftung, nicht der Titel DIESER
              Anfrage. Fällt auf denselben Text zurück, falls (noch) kein
              Titel gesetzt ist (siehe make_title()/set_title_if_empty()
              backend-seitig - erst nach der ersten Nutzernachricht
              vorhanden). newRequest bleibt unverändert bei "Neue Anfrage" -
              dort gibt es strukturell noch keinen Titel. */}
          {hasMessages ? activeAnfrage?.title ?? 'Kürzlich gestellte Anfrage' : 'Neue Anfrage'}
        </span>
        <div className="lumi-panel__icons">
          <button type="button" className="lumi-panel__icon" title="Neue Anfrage" onClick={handleNewAnfrage}>
            <ChatTeardropText size={20} />
          </button>
          <button type="button" className="lumi-panel__icon" title="Im Chat öffnen" onClick={handleExpandToChat}>
            <ArrowSquareIn size={20} />
          </button>
          <button type="button" className="lumi-panel__icon" title="Minimieren" onClick={onClose}>
            <Minus size={20} />
          </button>
        </div>
      </div>

      {showConversation ? (
        <LumiConversation />
      ) : (
        <div className="lumi-panel__empty">
          <LumiAvatar size={64} variant="large" />
          <h2 className="lumi-panel__empty-headline">Wie kann ich dir helfen?</h2>
          <ul className="lumi-panel__suggestions">
            {NEW_REQUEST_SUGGESTIONS.map((suggestion) => (
              <li key={suggestion.displayed}>
                <button
                  type="button"
                  className="lumi-panel__suggestion"
                  onClick={() => handleSend(suggestion.submitted)}
                >
                  {suggestion.displayed}
                </button>
              </li>
            ))}
          </ul>

          {/* Eigenes, schlankes Composer-Feld NUR für diesen Zustand - das
              Design zeigt hier (anders als LumiConversation) keinen
              Emoji-Button, nur Eingabe + Senden. */}
          <div className="lumi-panel__empty-composer">
            <textarea
              placeholder="Nachricht an Lumi..."
              value={emptyDraft}
              rows={1}
              onChange={(e) => setEmptyDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend(emptyDraft)
                  setEmptyDraft('')
                }
              }}
            />
            <button
              type="button"
              className="lumi-panel__empty-send"
              title="Senden"
              onClick={() => {
                handleSend(emptyDraft)
                setEmptyDraft('')
              }}
            >
              <PaperPlaneRight size={20} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
