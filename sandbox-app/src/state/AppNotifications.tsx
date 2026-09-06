import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { SidebarItemId } from '../components/Sidebar/Sidebar'

type Badges = Partial<Record<SidebarItemId, boolean>>

type AppNotificationsContextValue = {
  badges: Badges
  setBadge: (id: SidebarItemId, value: boolean) => void
}

const AppNotificationsContext = createContext<AppNotificationsContextValue | null>(null)

/**
 * Zentrale Stelle für "gibt es echten neuen Inhalt in Bereich X" – jeder
 * Screen meldet seinen eigenen Zustand über useReportBadge, die Sidebar
 * liest nur noch daraus (statt eine manuell gesetzte Prop zu brauchen).
 */
export function AppNotificationsProvider({ children }: { children: ReactNode }) {
  const [badges, setBadges] = useState<Badges>({})

  const setBadge = useCallback((id: SidebarItemId, value: boolean) => {
    setBadges((prev) => (prev[id] === value ? prev : { ...prev, [id]: value }))
  }, [])

  const value = useMemo(() => ({ badges, setBadge }), [badges, setBadge])

  return <AppNotificationsContext.Provider value={value}>{children}</AppNotificationsContext.Provider>
}

export function useAppNotifications() {
  const ctx = useContext(AppNotificationsContext)
  if (!ctx) throw new Error('useAppNotifications must be used within AppNotificationsProvider')
  return ctx
}

/**
 * Von einem Screen aufgerufen, um seinen Badge-Status aus echten Daten zu
 * melden, z.B. `useReportBadge('chat', conversations.some((c) => c.unread))`.
 * Aktualisiert sich automatisch, wenn sich hasNew ändert.
 */
export function useReportBadge(id: SidebarItemId, hasNew: boolean) {
  const { setBadge } = useAppNotifications()
  useEffect(() => {
    setBadge(id, hasNew)
  }, [id, hasNew, setBadge])
}
