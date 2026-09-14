import Avatar, { type AvatarColor } from '../Avatar/Avatar'
import StatusIndicator, { type StatusTone } from '../StatusIndicator/StatusIndicator'
import './UserWithStatus.css'

type UserWithStatusProps = {
  avatarSize: number
  initials?: string
  avatarColor?: AvatarColor
  isLumi?: boolean
  presence?: StatusTone
  className?: string
}

// Figmas eigene "UserWithStatus"-Komponente (node 45:7075) hat zwei
// Avatar-Größenvarianten (default 24px, big 32px), aber in BEIDEN ist der
// Status-Punkt fix 12px und der Avatar zieht per konstantem -6px
// rechtem Margin unter den Punkt – nicht proportional zur Avatar-Größe.
const STATUS_SIZE = 12
const OVERLAP_PX = -6

/**
 * Entspricht Figmas eigenem "UserWithStatus"-Baustein (dort ebenfalls in
 * ChatListItem und ChatboxHeader wiederverwendet): Avatar + Präsenz-Punkt
 * als Flex-Row, unten ausgerichtet, kein absolute Positioning.
 *
 * isLumi unterdrückt presence STRUKTURELL hier, am einzigen Ort, der von
 * ChatListItem UND der Chat-Kopfzeile UND jeder künftigen Lumi-Darstellung
 * durchlaufen wird (siehe Bericht an die Nutzerin) - "online/abwesend/
 * beschäftigt" ergibt bei einem Assistenten keinen Sinn, das gilt bei
 * Kolleg:innen weiterhin. Ein Aufrufer kann isLumi+presence also bedenkenlos
 * gemeinsam übergeben, ohne dass presence versehentlich durchschlägt.
 */
export default function UserWithStatus({
  avatarSize,
  initials,
  avatarColor,
  isLumi,
  presence,
  className,
}: UserWithStatusProps) {
  const effectivePresence = isLumi ? undefined : presence
  return (
    <span className={`user-with-status ${className ?? ''}`}>
      <span style={effectivePresence ? { marginRight: OVERLAP_PX } : undefined}>
        <Avatar icon={isLumi ? 'lumi' : 'initials'} initials={initials} color={avatarColor} size={avatarSize} />
      </span>
      {effectivePresence && <StatusIndicator status={effectivePresence} size={STATUS_SIZE} />}
    </span>
  )
}
