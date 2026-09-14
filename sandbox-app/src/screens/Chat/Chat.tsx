import { useEffect, useRef, useState } from 'react'
import { CaretDown, CaretUp, ChatTeardropText, Sparkle, Smiley, PaperPlaneRight, ChatCircle } from '@phosphor-icons/react'
import ChatListItem from '../../components/ChatListItem/ChatListItem'
import LumiMessageIcons from '../../components/LumiMessageIcons/LumiMessageIcons'
import MessageBox from '../../components/MessageBox/MessageBox'
import RationaleBlock from '../../components/RationaleBlock/RationaleBlock'
import SparkleIndicator from '../../components/SparkleIndicator/SparkleIndicator'
import UserWithStatus from '../../components/UserWithStatus/UserWithStatus'
import { useReportBadge } from '../../state/AppNotifications'
import { useChatState } from '../../state/ChatState'
import { useAgentState } from '../../state/AgentState'
import { formatDateDivider } from '../../utils/formatTime'
import type { Conversation } from './chatData'
import './Chat.css'

type SectionId = 'channels' | 'dms'

// 'assistant' ist keine eigene Sektion mehr über SECTIONS/conversations -
// die Agent-AI-Zeile kommt jetzt direkt aus AgentState (siehe unten), nicht
// mehr aus einem gefilterten Conversation-Eintrag.
const SECTIONS: { id: SectionId; title: string; filter: (c: Conversation) => boolean }[] = [
  { id: 'channels', title: 'Kanäle', filter: (c) => !!c.isChannel },
  { id: 'dms', title: 'Direktnachrichten', filter: (c) => !c.isChannel },
]

type ActiveSelection = { kind: 'agent' } | { kind: 'conversation'; id: string }

/*
 * Phosphor-Icons haben pro weight ("regular"/"fill") komplett eigene
 * SVG-Pfade – der Outline-zu-Fill-Wechsel bei Hover/Active lässt sich
 * also nicht per CSS lösen, sondern braucht den weight-Prop im JSX.
 */
function useIconFill() {
  const [filled, setFilled] = useState(false)
  return [
    filled,
    {
      onMouseEnter: () => setFilled(true),
      onMouseLeave: () => setFilled(false),
      onMouseDown: () => setFilled(true),
      onMouseUp: () => setFilled(true),
    },
  ] as const
}

export default function Chat() {
  const { conversations, setConversations } = useChatState()
  const { anfragen, activeThreadId, sendMessage, markThreadSeen, createAnfrage } = useAgentState()
  const [selection, setSelection] = useState<ActiveSelection>({ kind: 'agent' })
  const [collapsed, setCollapsed] = useState<Record<SectionId | 'assistant', boolean>>({
    assistant: false,
    channels: false,
    dms: false,
  })
  const [draft, setDraft] = useState('')
  const [smileyFilled, smileyHoverProps] = useIconFill()
  const [sendFilled, sendHoverProps] = useIconFill()
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const activeAnfrage = activeThreadId ? anfragen[activeThreadId] : undefined
  const activeConversation =
    selection.kind === 'conversation' ? (conversations.find((c) => c.id === selection.id) ?? conversations[0]) : undefined

  // Sidebar-Badge: bestehende gescriptete Konversationen ODER eine frische,
  // noch nicht gesehene Antwort/Fehlermeldung vom Agenten (siehe Bericht:
  // "result"/"error" sind genau dafür da, siehe Setup_Dokumentation.md §7).
  // Gleiche Einschränkung wie zuvor: aktualisiert sich nur, während Chat.tsx
  // gemountet ist (useReportBadge hat keinen Unmount-Effekt) - bestehende
  // Limitation, nicht neu eingeführt.
  useReportBadge(
    'chat',
    conversations.some((c) => c.unread) || activeAnfrage?.status === 'result' || activeAnfrage?.status === 'error',
  )

  // Wer die Anfrage gerade offen hat, hat "result"/"error" bereits gesehen -
  // Override direkt zurücksetzen, statt auf einen separaten Statuspunkt-Klick
  // zu warten (der kommt erst in Schritt 5/6).
  useEffect(() => {
    if (selection.kind !== 'agent' || !activeThreadId) return
    if (activeAnfrage?.status !== 'result' && activeAnfrage?.status !== 'error') return
    markThreadSeen(activeThreadId).catch((err) => console.error('[chat] markThreadSeen fehlgeschlagen', err))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection.kind, activeThreadId, activeAnfrage?.status])

  // Textarea wächst mit dem Inhalt (bis zu einer Deckelung), statt intern zu
  // scrollen oder die Composer-Box zu sprengen - siehe Bericht an die
  // Nutzerin zur Umstellung von <input> auf <textarea>.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [draft])

  function openConversation(id: string) {
    setSelection({ kind: 'conversation', id })
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, unread: false } : c)))
  }

  async function handleSend() {
    const text = draft.trim()
    if (!text) return
    setDraft('')

    if (selection.kind === 'agent') {
      try {
        await sendMessage(text)
      } catch (err) {
        console.error('[chat] sendMessage fehlgeschlagen', err)
      }
      return
    }

    const targetId = selection.id
    setConversations((prev) =>
      prev.map((c) => (c.id === targetId ? { ...c, messages: [...c.messages, { from: 'out', text }] } : c)),
    )
  }

  async function handleNewAnfrage() {
    try {
      await createAnfrage()
      setSelection({ kind: 'agent' })
    } catch (err) {
      console.error('[chat] createAnfrage fehlgeschlagen', err)
    }
  }

  const isAgentBusy = selection.kind === 'agent' && (activeAnfrage?.status === 'working' || activeAnfrage?.status === 'waiting')
  const firstMessageTime = selection.kind === 'agent' ? activeAnfrage?.messages[0]?.receivedAt : undefined

  return (
    <div className="chat">
      <aside className="chat__overview">
        <h1 className="chat__overview-title">Chat</h1>

        <div className="chat__section">
          <button
            type="button"
            className="chat__section-title"
            onClick={() => setCollapsed((prev) => ({ ...prev, assistant: !prev.assistant }))}
            aria-expanded={!collapsed.assistant}
          >
            {collapsed.assistant ? <CaretDown size={16} /> : <CaretUp size={16} />}
            {/* "Agent AI" ist sichtbarer Text aus dem Design, kein
                Komponentenname - 1:1 übernommen (siehe Bericht an die
                Nutzerin). */}
            <span>Agent AI</span>
          </button>
          {!collapsed.assistant && (
            <div className="chat__section-list">
              <ChatListItem
                name="Lumi"
                preview={activeAnfrage?.messages[activeAnfrage.messages.length - 1]?.content ?? ''}
                isLumi
                unread={activeAnfrage?.status === 'result' || activeAnfrage?.status === 'error'}
                active={selection.kind === 'agent'}
                onClick={() => setSelection({ kind: 'agent' })}
              />
            </div>
          )}
        </div>

        {SECTIONS.map(({ id, title, filter }) => {
          const items = conversations.filter(filter)
          if (items.length === 0) return null
          const isCollapsed = collapsed[id]
          return (
            <div className="chat__section" key={id}>
              <button
                type="button"
                className="chat__section-title"
                onClick={() => setCollapsed((prev) => ({ ...prev, [id]: !prev[id] }))}
                aria-expanded={!isCollapsed}
              >
                {isCollapsed ? <CaretDown size={16} /> : <CaretUp size={16} />}
                <span>{title}</span>
              </button>
              {!isCollapsed && (
                <div className="chat__section-list">
                  {items.map((c) => (
                    <ChatListItem
                      key={c.id}
                      name={c.name}
                      preview={c.messages[c.messages.length - 1]?.text ?? ''}
                      initials={c.initials}
                      avatarColor={c.avatarColor}
                      isLumi={c.isLumi}
                      presence={c.isChannel ? undefined : c.presence}
                      unread={c.unread}
                      active={selection.kind === 'conversation' && c.id === selection.id}
                      onClick={() => openConversation(c.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </aside>

      <section className="chat__content">
        <header className="chat__header">
          <div className="chat__header-identity">
            {selection.kind === 'agent' ? (
              <UserWithStatus avatarSize={32} isLumi />
            ) : activeConversation?.isChannel ? (
              <ChatCircle size={28} color="var(--color-accent)" />
            ) : (
              <UserWithStatus
                avatarSize={32}
                initials={activeConversation?.initials}
                avatarColor={activeConversation?.avatarColor}
                isLumi={activeConversation?.isLumi}
                presence={activeConversation?.presence}
              />
            )}
            <span className="chat__header-name">{selection.kind === 'agent' ? 'Lumi' : activeConversation?.name}</span>
          </div>
          {/* Nur im Lumi-Chat (Figma-Frame "Chat_Lumi") - erzeugt eine neue
              Anfrage und wechselt dorthin. Das Anfragen-Dropdown daneben
              (Figma) wird bewusst nicht gebaut, siehe Bericht an die
              Nutzerin (Stufe 3/Backlog A6). */}
          {selection.kind === 'agent' && (
            <button type="button" className="chat__header-new-anfrage" title="Neue Anfrage" onClick={handleNewAnfrage}>
              <ChatTeardropText size={20} />
            </button>
          )}
        </header>

        <div className="chat__messages">
          {selection.kind === 'agent' ? (
            <>
              {firstMessageTime && <div className="chat__date-divider">{formatDateDivider(firstMessageTime)}</div>}
              {(activeAnfrage?.messages ?? []).map((m, i) => (
                <div className="chat__message-group" key={i}>
                  {/* Block ERKLÄRT die folgende Nachricht, gehört laut Figma
                      deshalb davor, nicht danach. */}
                  <RationaleBlock rationale={m.rationale} />
                  <MessageBox
                    from={m.role === 'user' ? 'out' : 'in'}
                    message={m.content}
                    // Design zeigt keinen Avatar/keinen wiederholten
                    // Sender-Namen neben einzelnen Lumi-Nachrichten (siehe
                    // Bericht an die Nutzerin) - showSender deshalb immer
                    // false im Agenten-Zweig.
                    showSender={false}
                  />
                  {m.role === 'assistant' && <LumiMessageIcons message={m.content} receivedAt={m.receivedAt} />}
                </div>
              ))}
            </>
          ) : (
            (activeConversation?.messages ?? []).map((m, i) => {
              const showSender =
                !activeConversation?.isChannel &&
                m.from === 'in' &&
                (i === 0 || activeConversation!.messages[i - 1].from !== 'in')
              return (
                <MessageBox
                  key={i}
                  from={m.from}
                  message={m.text}
                  senderName={activeConversation?.name}
                  showSender={showSender}
                  initials={activeConversation?.initials}
                  avatarColor={activeConversation?.avatarColor}
                  isLumi={activeConversation?.isLumi}
                  presence={showSender ? activeConversation?.presence : undefined}
                />
              )
            })
          )}

          {/* Dauerhaft sichtbar, solange die Lumi-Konversation offen ist -
              Lumis Präsenz im Verlauf, kein reiner Ladezustand (siehe
              Bericht an die Nutzerin). Wechselt nur zwischen Idle/Working,
              sparkle.riv kennt keine weiteren Zustände. */}
          {selection.kind === 'agent' && (
            <SparkleIndicator status={activeAnfrage?.status === 'working' ? 'working' : 'idle'} />
          )}
          {selection.kind === 'agent' && activeAnfrage?.status === 'waiting' && (
            // Platzhalter bis Schritt 4 (Bestätigungskarte) - kein Nachrichten-
            // Inhalt aus dem Backend an dieser Stelle, nur der interne Status.
            <div className="chat__typing-indicator" aria-live="polite">
              Lumi wartet auf deine Bestätigung (Bestätigungskarte kommt in Schritt 4).
            </div>
          )}
        </div>

        <div className="chat__composer">
          <textarea
            ref={textareaRef}
            placeholder={isAgentBusy ? 'Lumi ist noch mit der letzten Anfrage beschäftigt…' : 'Nachricht eingeben'}
            value={draft}
            disabled={isAgentBusy}
            rows={1}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              // Enter sendet, Shift+Enter fügt einen Zeilenumbruch ein -
              // preventDefault ist nötig, sonst fügt die Textarea VOR dem
              // Senden trotzdem schon einen Umbruch ein.
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
          />
          <div className="chat__composer-icons">
            {selection.kind !== 'agent' && (
              // AskLumi-Funke gehört nur in Kolleg:innen-Composer, nicht in
              // den Lumi-Chat selbst (siehe Bericht) - im Lumi-Chat ergäbe
              // "frag Lumi nach einem Formulierungsvorschlag für Lumi" keinen Sinn.
              <button
                type="button"
                className="chat__composer-icon chat__composer-icon--assistant"
                title="Formulierungsvorschlag von Lumi"
              >
                <Sparkle size={20} weight="fill" />
              </button>
            )}
            <button
              type="button"
              className="chat__composer-icon chat__composer-icon--accent"
              title="Emoji"
              {...smileyHoverProps}
            >
              <Smiley size={20} weight={smileyFilled ? 'fill' : 'regular'} />
            </button>
            <span className="chat__composer-divider" aria-hidden="true" />
            <button
              type="button"
              className="chat__composer-icon chat__composer-icon--accent"
              title="Senden"
              onClick={handleSend}
              disabled={isAgentBusy}
              {...sendHoverProps}
            >
              <PaperPlaneRight size={20} weight={sendFilled ? 'fill' : 'regular'} />
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
