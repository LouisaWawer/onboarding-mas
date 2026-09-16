import { useState } from 'react'
import { CaretDown, CaretUp, ChatTeardropText, Sparkle, Smiley, PaperPlaneRight, ChatCircle } from '@phosphor-icons/react'
import ChatListItem from '../../components/ChatListItem/ChatListItem'
import LumiConversation from '../../components/LumiConversation/LumiConversation'
import MessageBox from '../../components/MessageBox/MessageBox'
import UserWithStatus from '../../components/UserWithStatus/UserWithStatus'
import { useReportBadge } from '../../state/AppNotifications'
import { useChatState } from '../../state/ChatState'
import { useAgentState } from '../../state/AgentState'
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
  const { anfragen, activeThreadId, createAnfrage } = useAgentState()
  const [selection, setSelection] = useState<ActiveSelection>({ kind: 'agent' })
  const [collapsed, setCollapsed] = useState<Record<SectionId | 'assistant', boolean>>({
    assistant: false,
    channels: false,
    dms: false,
  })
  // Nur noch für den Kolleg:innen-Zweig - die Lumi-Konversation hat ihren
  // eigenen Entwurf/Composer jetzt in LumiConversation.tsx (siehe Bericht
  // an die Nutzerin, Schritt 5: "zwei Ansichten auf dieselben Daten").
  const [draft, setDraft] = useState('')
  const [smileyFilled, smileyHoverProps] = useIconFill()
  const [sendFilled, sendHoverProps] = useIconFill()

  const activeAnfrage = activeThreadId ? anfragen[activeThreadId] : undefined
  const activeConversation =
    selection.kind === 'conversation' ? (conversations.find((c) => c.id === selection.id) ?? conversations[0]) : undefined

  // Sidebar-Badge: bestehende gescriptete Konversationen ODER eine frische,
  // noch nicht gesehene Antwort/Fehlermeldung vom Agenten (siehe Bericht:
  // "result"/"error" sind genau dafür da, siehe Setup_Dokumentation.md §7).
  useReportBadge(
    'chat',
    conversations.some((c) => c.unread) || activeAnfrage?.status === 'result' || activeAnfrage?.status === 'error',
  )

  function openConversation(id: string) {
    setSelection({ kind: 'conversation', id })
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, unread: false } : c)))
  }

  function handleSend() {
    const text = draft.trim()
    if (!text || selection.kind !== 'conversation') return
    setDraft('')
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

        {selection.kind === 'agent' ? (
          <LumiConversation />
        ) : (
          <>
            <div className="chat__messages">
              {(activeConversation?.messages ?? []).map((m, i) => {
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
              })}
            </div>

            <div className="chat__composer">
              <textarea
                placeholder="Nachricht eingeben"
                value={draft}
                rows={1}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
              />
              <div className="chat__composer-icons">
                {/* AskLumi-Funke gehört nur in Kolleg:innen-Composer, nicht in
                    den Lumi-Chat selbst (siehe Bericht) - im Lumi-Chat ergäbe
                    "frag Lumi nach einem Formulierungsvorschlag für Lumi" keinen Sinn. */}
                <button
                  type="button"
                  className="chat__composer-icon chat__composer-icon--assistant"
                  title="Formulierungsvorschlag von Lumi"
                >
                  <Sparkle size={20} weight="fill" />
                </button>
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
                  {...sendHoverProps}
                >
                  <PaperPlaneRight size={20} weight={sendFilled ? 'fill' : 'regular'} />
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  )
}
