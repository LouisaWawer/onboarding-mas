import { useState } from 'react'
import logoUrl from '../../assets/icons/Logo.svg'
import SidebarIcon, { type SidebarApp } from './SidebarIcon'
import './Sidebar.css'

export type SidebarItemId = SidebarApp

const NAV_ITEMS: { id: SidebarItemId; label: string }[] = [
  { id: 'intranet', label: 'Intranet' },
  { id: 'chat', label: 'Chat' },
  { id: 'calendar', label: 'Kalender' },
  { id: 'tickets', label: 'Tickets' },
  { id: 'hub', label: 'Knowledge Hub' },
]

type SidebarProps = {
  active: SidebarItemId
  onNavigate?: (id: SidebarItemId) => void
  /** Welche Bereiche echten neuen Inhalt haben (siehe Vorschlag zur Verwaltung). */
  badges?: Partial<Record<SidebarItemId, boolean>>
}

export default function Sidebar({ active, onNavigate, badges }: SidebarProps) {
  const [hovered, setHovered] = useState<SidebarItemId | null>(null)

  return (
    <nav className="sidebar" aria-label="Hauptnavigation">
      <div className="sidebar__logo" aria-hidden="true">
        <img src={logoUrl} alt="Nordlicht Software" width={53} height={40} />
      </div>
      <ul className="sidebar__list">
        {NAV_ITEMS.map(({ id, label }) => (
          <li key={id} onMouseEnter={() => setHovered(id)} onMouseLeave={() => setHovered(null)}>
            <SidebarIcon
              app={id}
              label={label}
              state={id === active ? 'active' : id === hovered ? 'hover' : 'default'}
              hasBadge={!!badges?.[id]}
              onClick={() => onNavigate?.(id)}
            />
          </li>
        ))}
      </ul>
    </nav>
  )
}
