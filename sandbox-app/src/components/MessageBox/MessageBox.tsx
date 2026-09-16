import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
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
  /**
   * Nur für from="in": rendert OHNE Bubble-Hintergrund, volle Breite -
   * entspricht Figmas "LumiMessage" (Chat_Lumi, node 186:2048), NICHT dem
   * MessageBox-Bubble-Look. Gilt ausschließlich für Lumis EIGENE
   * Nachrichten im Assistenten-Chat (siehe Chat.tsx) - Kolleg:innen-DMs
   * nutzen weiterhin den normalen grauen "in"-Bubble (die Trennung läuft
   * über diesen expliziten Prop, nicht über isLumi, das eine andere
   * Bedeutung hat - Avatar/Farbe). from="out" bleibt in JEDEM Fall die
   * gefüllte Akzent-Bubble (Figma zeigt eigene Nachrichten auch im
   * Lumi-Chat als Bubble).
   */
  plain?: boolean
}

/**
 * Nur http(s)/mailto durchlassen, alles andere (insbesondere javascript:)
 * verwirft urlTransform zu einem leeren String - reine Vorsorge, siehe
 * Moduldocstring unten. Greift praktisch nie, weil der a-Tag ohnehin durch
 * einen span ersetzt wird (kein href mehr im DOM), aber billig genug, um
 * es trotzdem zu setzen.
 */
function sanitizeUrl(url: string): string {
  try {
    const parsed = new URL(url, 'https://example.invalid')
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:' || parsed.protocol === 'mailto:') {
      return url
    }
  } catch {
    // ungültige/relative URL - fällt durch auf den leeren String unten
  }
  return ''
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
  plain = false,
}: MessageBoxProps) {
  const isOut = from === 'out'
  const isPlain = !isOut && plain
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
        <div
          className={`message-box__bubble ${isOut ? 'message-box__bubble--out' : isPlain ? 'message-box__bubble--plain' : 'message-box__bubble--in'}`}
        >
          {/* Das Modell formatiert seine Antworten in Markdown (siehe
              Bericht an die Nutzerin) - kein Rohtext mehr. Bewusst OHNE
              rehype-raw: eingebettetes HTML im Modelltext wird dadurch als
              Text angezeigt, nie ausgeführt. Links werden NICHT als <a>
              gerendert (Sandbox-Fiktion: es gibt nichts, wohin ein Link
              führen könnte, ein toter/externer Klick würde die Testperson
              aus der Aufgabe reißen), sondern als reiner <span>. */}
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            urlTransform={sanitizeUrl}
            components={{
              a: ({ children }) => <span className="message-box__inline-link">{children}</span>,
            }}
          >
            {message}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
