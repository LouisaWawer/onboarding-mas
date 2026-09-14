import { createContext, useContext, useState, type ReactNode } from 'react'
import type { SidebarItemId } from '../components/Sidebar/Sidebar'

/**
 * Welcher Screen gerade aktiv ist - vorher lokaler useState in App.tsx.
 * Als eigener Context gehoben, weil useSendToLumi() (state/AgentState.tsx)
 * beim Aufruf aus Kalender.tsx/Intranet.tsx in den Chat wechseln muss, ohne
 * dass diese Screens eine Navigations-Prop durchgereicht bekommen - und
 * damit auch die "Neue Anfrage"-Aktion in der Topbar (späterer Schritt)
 * denselben Mechanismus nutzen kann, statt eine zweite Lösung zu bauen.
 */
type NavigationContextValue = {
  activeScreen: SidebarItemId
  navigateTo: (screen: SidebarItemId) => void
}

const NavigationContext = createContext<NavigationContextValue | null>(null)

export function NavigationProvider({ children }: { children: ReactNode }) {
  const [activeScreen, setActiveScreen] = useState<SidebarItemId>('chat')
  return <NavigationContext.Provider value={{ activeScreen, navigateTo: setActiveScreen }}>{children}</NavigationContext.Provider>
}

export function useNavigation() {
  const ctx = useContext(NavigationContext)
  if (!ctx) throw new Error('useNavigation must be used within NavigationProvider')
  return ctx
}
