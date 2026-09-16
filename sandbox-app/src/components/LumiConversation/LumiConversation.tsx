import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { PaperPlaneRight, Smiley } from '@phosphor-icons/react'
import ConfirmationCard from '../ConfirmationCard/ConfirmationCard'
import LumiMessageIcons from '../LumiMessageIcons/LumiMessageIcons'
import MessageBox from '../MessageBox/MessageBox'
import OptionsCard from '../OptionsCard/OptionsCard'
import RationaleBlock from '../RationaleBlock/RationaleBlock'
import SparkleIndicator from '../SparkleIndicator/SparkleIndicator'
import { useAgentState } from '../../state/AgentState'
import { formatDateDivider } from '../../utils/formatTime'
import './LumiConversation.css'

/**
 * Die Lumi-Konversation (Verlauf + Composer) - herausgelöst aus Chat.tsx
 * (siehe Bericht an die Nutzerin, Schritt 5): EINE Komponente, ZWEI
 * Einbettungsorte (Chat.tsx Agent-Zweig, LumiPanel) - "zwei Ansichten auf
 * dieselben Daten, kein zweiter State". Liest state/AgentState.tsx direkt,
 * keine Props nötig - beide Einbettungsorte sehen dadurch IMMER denselben
 * Stand (Nachrichten, Bestätigungskarte, Busy-Zustand), ohne
 * Synchronisierungscode zwischen ihnen.
 *
 * Der umgebende Container (Chat.tsx: .chat__content, LumiPanel: die
 * Panel-Box) muss display:flex/flex-direction:column liefern - diese
 * Komponente selbst rendert ein Fragment, keinen eigenen Rahmen.
 */
export default function LumiConversation() {
  const {
    anfragen,
    activeThreadId,
    sendMessage,
    resume,
    markThreadSeen,
    displayedSuggestion,
    acceptSuggestion,
    markSessionSeen,
  } = useAgentState()
  const [draft, setDraft] = useState('')
  const [smileyFilled, setSmileyFilled] = useState(false)
  const [sendFilled, setSendFilled] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const messagesRef = useRef<HTMLDivElement>(null)
  // Ob die Person zuletzt am unteren Rand war - kein State (löst keinen
  // Re-Render aus, wird nur in den Scroll-Effekten unten gelesen/
  // geschrieben), siehe handleMessagesScroll.
  const isNearBottomRef = useRef(true)

  const activeAnfrage = activeThreadId ? anfragen[activeThreadId] : undefined
  const isAgentBusy = activeAnfrage?.status === 'working' || activeAnfrage?.status === 'waiting'
  const firstMessageTime = activeAnfrage?.messages[0]?.receivedAt
  const messageCount = activeAnfrage?.messages.length ?? 0

  function handleMessagesScroll() {
    const el = messagesRef.current
    if (!el) return
    // 80px Toleranz statt exakt 0 - beim Nachverfolgen einer live
    // eintreffenden Antwort ist der Rand nie pixelgenau erreicht.
    isNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  // Öffnen/Anfragewechsel: SOFORT ans Ende, ohne sichtbaren Sprung -
  // useLayoutEffect statt useEffect, damit das vor dem ersten Paint passiert
  // (siehe Bericht an die Nutzerin, Schritt 5, Punkt 3 - "steht bereits am
  // Ende", kein Scroll-Erlebnis beim Öffnen).
  useLayoutEffect(() => {
    const el = messagesRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    isNearBottomRef.current = true
  }, [activeThreadId])

  // Neue Nachricht ODER neu erscheinende Bestätigungskarte: nur
  // mitscrollen, wenn die Person ohnehin gerade am unteren Rand war -
  // sonst würde ein bewusstes Hochscrollen (etwas Älteres lesen) durch das
  // Eintreffen der Antwort weggerissen (siehe Bericht an die Nutzerin,
  // ausdrücklich genannter Sonderfall). Gilt für BEIDE Einbettungsorte
  // (Chat-Screen, Panel) automatisch, da dieselbe Komponente/derselbe
  // Ref in beiden Kontexten sitzt.
  useEffect(() => {
    const el = messagesRef.current
    if (!el) return
    if (!isNearBottomRef.current) return
    el.scrollTop = el.scrollHeight
  }, [messageCount, activeAnfrage?.interrupt, displayedSuggestion])

  // Wer die Konversation gerade offen hat (Chat-Screen ODER Panel - diese
  // Komponente sitzt in beiden, siehe Moduldocstring), hat "result"/"error"
  // bereits gesehen - Override zurücksetzen, statt auf einen separaten
  // Statuspunkt-Klick zu warten. Ursprünglich in Chat.tsx, hierher gezogen,
  // damit das Panel dasselbe Verhalten automatisch mitbekommt.
  useEffect(() => {
    if (!activeThreadId) return
    if (activeAnfrage?.status !== 'result' && activeAnfrage?.status !== 'error') return
    markThreadSeen(activeThreadId).catch((err) => console.error('[lumi-conversation] markThreadSeen fehlgeschlagen', err))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeThreadId, activeAnfrage?.status])

  // Textarea wächst mit dem Inhalt (siehe ursprünglich Chat.tsx).
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [draft])

  async function handleSend() {
    const text = draft.trim()
    if (!text) return
    setDraft('')
    try {
      await sendMessage(text)
    } catch (err) {
      console.error('[lumi-conversation] sendMessage fehlgeschlagen', err)
    }
  }

  return (
    <>
      <div className="lumi-conversation__messages" ref={messagesRef} onScroll={handleMessagesScroll}>
        {firstMessageTime && (
          <div className="lumi-conversation__date-divider">{formatDateDivider(firstMessageTime)}</div>
        )}
        {(activeAnfrage?.messages ?? []).map((m, i) => (
          <div className="lumi-conversation__message-group" key={i}>
            {/* Block ERKLÄRT die folgende Nachricht, gehört laut Figma
                deshalb davor, nicht danach. */}
            <RationaleBlock rationale={m.rationale} />
            <MessageBox
              from={m.role === 'user' ? 'out' : 'in'}
              message={m.content}
              showSender={false}
              plain={m.role === 'assistant'}
            />
            {m.role === 'assistant' && <LumiMessageIcons message={m.content} receivedAt={m.receivedAt} />}
          </div>
        ))}

        {/* Dauerhaft sichtbar, solange die Lumi-Konversation offen ist -
            Lumis Präsenz im Verlauf, kein reiner Ladezustand. */}
        <SparkleIndicator status={activeAnfrage?.status === 'working' ? 'working' : 'idle'} />

        {activeAnfrage?.interrupt && <ConfirmationCard interrupt={activeAnfrage.interrupt} onResume={resume} />}

        {/* Proaktiver Screenwechsel-Vorschlag (siehe Bericht an die
            Nutzerin, Schritt 6) - SESSION-, nicht Anfrage-gebunden (siehe
            AgentState.tsx: displayedSuggestion), erscheint deshalb
            unabhängig davon, welche Anfrage gerade offen ist, hier aber im
            selben Verlaufs-Slot wie ConfirmationCard (Figma: dieselbe
            Karten-Komponente, node 219:4794, type=options statt type=
            confirmation). Klick auf eine Option erzeugt IMMER eine NEUE
            Anfrage (siehe acceptSuggestion, AgentState.tsx) - nie in die
            hier sichtbare, ggf. beschäftigte Anfrage hinein.

            BEWUSST displayedSuggestion, NICHT pendingSuggestion (Bugfix,
            siehe Bericht an die Nutzerin): pendingSuggestion folgt dem
            Backend 1:1 und wird auch durch das status_changed-idle
            genullt, das POST /session/{id}/seen als Nebenwirkung auslöst
            (siehe acknowledgeSuggestion, LumiPanel.tsx) - mit
            pendingSuggestion hier wäre die Karte im selben Moment
            verschwunden, in dem das Panel sie zeigen sollte.
            displayedSuggestion wird NUR durch eine Handlung der Person
            gelöscht (Klick, X, Screenwechsel), nicht durch dieses
            Folge-Event. */}
        {displayedSuggestion && (
          <OptionsCard
            title={displayedSuggestion.title}
            options={displayedSuggestion.options.map((option) => ({
              label: option.displayed,
              onClick: () => acceptSuggestion(option).catch((err) => console.error('[lumi-conversation] acceptSuggestion fehlgeschlagen', err)),
            }))}
            onClose={() => markSessionSeen().catch((err) => console.error('[lumi-conversation] markSessionSeen fehlgeschlagen', err))}
          />
        )}
      </div>

      <div className="lumi-conversation__composer">
        <textarea
          ref={textareaRef}
          // "Nachricht an Lumi..." vereinheitlicht (siehe Bericht an die
          // Nutzerin, Schritt 5) - steht so im Design (LumiChat_Floating,
          // beide Zustände) und gilt jetzt für Chat UND Panel gleichermaßen.
          placeholder={isAgentBusy ? 'Lumi ist noch mit der letzten Anfrage beschäftigt…' : 'Nachricht an Lumi...'}
          value={draft}
          disabled={isAgentBusy}
          rows={1}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
        />
        <div className="lumi-conversation__composer-icons">
          <button
            type="button"
            className="lumi-conversation__composer-icon"
            title="Emoji"
            onMouseEnter={() => setSmileyFilled(true)}
            onMouseLeave={() => setSmileyFilled(false)}
          >
            <Smiley size={20} weight={smileyFilled ? 'fill' : 'regular'} />
          </button>
          <span className="lumi-conversation__composer-divider" aria-hidden="true" />
          <button
            type="button"
            className="lumi-conversation__composer-icon"
            title="Senden"
            onClick={handleSend}
            disabled={isAgentBusy}
            onMouseEnter={() => setSendFilled(true)}
            onMouseLeave={() => setSendFilled(false)}
          >
            <PaperPlaneRight size={20} weight={sendFilled ? 'fill' : 'regular'} />
          </button>
        </div>
      </div>
    </>
  )
}
