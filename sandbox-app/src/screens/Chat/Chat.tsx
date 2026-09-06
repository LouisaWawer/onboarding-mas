import { useState } from 'react'
import { CaretDown, CaretUp, Sparkle, Smiley, PaperPlaneRight, ChatCircle } from '@phosphor-icons/react'
import ChatListItem from '../../components/ChatListItem/ChatListItem'
import MessageBox from '../../components/MessageBox/MessageBox'
import UserWithStatus from '../../components/UserWithStatus/UserWithStatus'
import { useReportBadge } from '../../state/AppNotifications'
import { useChatState } from '../../state/ChatState'
import type { Conversation } from './chatData'
import './Chat.css'

type SectionId = 'assistant' | 'channels' | 'dms'

const SECTIONS: { id: SectionId; title: string; filter: (c: Conversation) => boolean }[] = [
  { id: 'assistant', title: 'Onboarding-Assistent', filter: (c) => !!c.isLumi },
  { id: 'channels', title: 'Kanäle', filter: (c) => !!c.isChannel },
  { id: 'dms', title: 'Direktnachrichten', filter: (c) => !c.isLumi && !c.isChannel },
]

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
  const [activeId, setActiveId] = useState('lumi')
  const [collapsed, setCollapsed] = useState<Record<SectionId, boolean>>({
    assistant: false,
    channels: false,
    dms: false,
  })
  const [draft, setDraft] = useState('')
  const [smileyFilled, smileyHoverProps] = useIconFill()
  const [sendFilled, sendHoverProps] = useIconFill()

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0]

  useReportBadge('chat', conversations.some((c) => c.unread))

  function openConversation(id: string) {
    setActiveId(id)
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, unread: false } : c)))
  }

  function sendMessage() {
    const text = draft.trim()
    if (!text) return
    setConversations((prev) =>
      prev.map((c) => (c.id === activeId ? { ...c, messages: [...c.messages, { from: 'out', text }] } : c)),
    )
    setDraft('')
  }

  return (
    <div className="chat">
      <aside className="chat__overview">
        <h1 className="chat__overview-title">Chat</h1>
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
                      active={c.id === activeId}
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
          {active.isChannel ? (
            <ChatCircle size={28} color="var(--color-accent)" />
          ) : (
            <UserWithStatus
              avatarSize={32}
              initials={active.initials}
              avatarColor={active.avatarColor}
              isLumi={active.isLumi}
              presence={active.presence}
            />
          )}
          <span className="chat__header-name">{active.name}</span>
        </header>

        <div className="chat__messages">
          {active.messages.map((m, i) => {
            const showSender = !active.isChannel && m.from === 'in' && (i === 0 || active.messages[i - 1].from !== 'in')
            return (
              <MessageBox
                key={i}
                from={m.from}
                message={m.text}
                senderName={active.name}
                showSender={showSender}
                initials={active.initials}
                avatarColor={active.avatarColor}
                isLumi={active.isLumi}
                presence={showSender ? active.presence : undefined}
              />
            )
          })}
        </div>

        <div className="chat__composer">
          <input
            type="text"
            placeholder="Nachricht eingeben"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') sendMessage()
            }}
          />
          <div className="chat__composer-icons">
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
              onClick={sendMessage}
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
