import type { AvatarColor } from '../Avatar/Avatar'
import type { StatusTone } from '../StatusIndicator/StatusIndicator'
import UserWithStatus from '../UserWithStatus/UserWithStatus'
import './MessageBox.css'

type MessageBoxProps = {
  message: string
  /** in = Gegenüber (Kolleg:in/Lumi), out = eigene Nachricht */
  from?: 'in' | 'out'
  /** Absendername über der Nachricht, nur bei from="in" und erster Nachricht einer Serie */
  senderName?: string
  showSender?: boolean
  avatarColor?: AvatarColor
  initials?: string
  isLumi?: boolean
  presence?: StatusTone
}

export default function MessageBox({
  message,
  from = 'in',
  senderName,
  showSender = true,
  avatarColor = 'avatar1',
  initials,
  isLumi = false,
  presence,
}: MessageBoxProps) {
  const isOut = from === 'out'
  return (
    <div className={`message-box ${isOut ? 'message-box--out' : 'message-box--in'}`}>
      {!isOut && showSender && senderName && (
        <div className="message-box__sender">{senderName}</div>
      )}
      <div className="message-box__row">
        {!isOut && (
          <span className="message-box__avatar">
            {showSender && (
              <UserWithStatus
                avatarSize={24}
                initials={initials}
                avatarColor={avatarColor}
                isLumi={isLumi}
                presence={presence}
              />
            )}
          </span>
        )}
        <div className={`message-box__bubble ${isOut ? 'message-box__bubble--out' : 'message-box__bubble--in'}`}>
          {message}
        </div>
      </div>
    </div>
  )
}
