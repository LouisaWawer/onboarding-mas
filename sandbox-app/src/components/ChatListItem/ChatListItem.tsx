import type { AvatarColor } from '../Avatar/Avatar'
import type { StatusTone } from '../StatusIndicator/StatusIndicator'
import UserWithStatus from '../UserWithStatus/UserWithStatus'
import './ChatListItem.css'

type ChatListItemProps = {
  name: string
  preview: string
  time?: string
  initials?: string
  avatarColor?: AvatarColor
  isLumi?: boolean
  presence?: StatusTone
  unread?: boolean
  active?: boolean
  onClick?: () => void
}

export default function ChatListItem({
  name,
  preview,
  time,
  initials,
  avatarColor = 'avatar1',
  isLumi = false,
  presence,
  unread = false,
  active = false,
  onClick,
}: ChatListItemProps) {
  return (
    <button
      type="button"
      className={`chat-list-item ${active ? 'chat-list-item--active' : ''}`}
      onClick={onClick}
    >
      <UserWithStatus
        avatarSize={32}
        initials={initials}
        avatarColor={avatarColor}
        isLumi={isLumi}
        presence={presence}
      />
      <span className="chat-list-item__body">
        <span className="chat-list-item__row">
          <span className="chat-list-item__name">{name}</span>
          {time && <span className="chat-list-item__time">{time}</span>}
        </span>
        <span className="chat-list-item__preview">{preview}</span>
      </span>
      {unread && <span className="chat-list-item__badge" aria-label="ungelesen" />}
    </button>
  )
}
