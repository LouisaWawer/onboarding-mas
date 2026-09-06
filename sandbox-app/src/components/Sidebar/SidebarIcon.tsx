import type { Icon } from '@phosphor-icons/react'
import { ChatTeardropText, HouseSimple, Brain, Headset, CalendarDots } from '@phosphor-icons/react'
import './SidebarIcon.css'

export type SidebarApp = 'intranet' | 'chat' | 'calendar' | 'tickets' | 'hub'
export type SidebarIconState = 'default' | 'hover' | 'active'

type SidebarIconProps = {
  app: SidebarApp
  state?: SidebarIconState
  /** Benachrichtigungspunkt – nur zeigen, wenn es echten neuen Inhalt gibt. */
  hasBadge?: boolean
  label: string
  onClick?: () => void
}

/*
 * Zurück auf @phosphor-icons/react für die Sidebar-Navigation: die
 * Figma-Exporte (src/assets/icons/{chat,intranet,knowledgehub,ticket,
 * calendar}.svg) sind als volle Fläche gezeichnet, nicht als Outline –
 * ein sauberes "Kontur bei default, gefüllt bei hover/active" ließ sich
 * daraus nicht per CSS herleiten (stroke auf den Fill-Pfaden sah an den
 * Kurven unruhig aus). Phosphor liefert dafür echte, sauber gezeichnete
 * regular/fill-Paare. Icon-Form weicht dadurch leicht vom exakten
 * Figma-Export ab, Farbe/Zustandslogik bleiben unverändert (color/accent,
 * kein Hintergrund).
 */
const ICON: Record<SidebarApp, Icon> = {
  intranet: HouseSimple,
  chat: ChatTeardropText,
  hub: Brain,
  tickets: Headset,
  calendar: CalendarDots,
}

export default function SidebarIcon({ app, state = 'default', hasBadge = false, label, onClick }: SidebarIconProps) {
  const IconComponent = ICON[app]
  return (
    <button
      type="button"
      className="sidebar-icon"
      onClick={onClick}
      aria-current={state === 'active' ? 'page' : undefined}
      title={label}
    >
      <IconComponent size={24} weight={state === 'default' ? 'regular' : 'fill'} color="var(--color-accent)" />
      {hasBadge && <span className="sidebar-icon__badge" aria-label="Neue Inhalte" />}
    </button>
  )
}
