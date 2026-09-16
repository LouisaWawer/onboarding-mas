import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
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

// Reine Ansichtsinformation, kein Sitzungszustand (siehe Bericht an die
// Nutzerin) - deshalb NICHT über GET /session rekonstruiert (das würde
// einen Backend-Roundtrip UND ein Feld im Session-Snapshot brauchen), nur
// direkt aus localStorage gelesen, exakt derselbe, bereits etablierte Weg
// wie SESSION_STORAGE_KEY (AgentState.tsx) - synchron beim ersten Render
// verfügbar, kein Flackern über 'chat' hinweg.
const SCREEN_STORAGE_KEY = 'onboarding-mas:active_screen'
const VALID_SCREENS: readonly SidebarItemId[] = ['intranet', 'chat', 'calendar', 'tickets', 'hub']

function isValidScreen(value: string | null): value is SidebarItemId {
  return value !== null && VALID_SCREENS.includes(value as SidebarItemId)
}

export function NavigationProvider({ children }: { children: ReactNode }) {
  const [activeScreen, setActiveScreen] = useState<SidebarItemId>(() => {
    const stored = typeof window !== 'undefined' ? localStorage.getItem(SCREEN_STORAGE_KEY) : null
    return isValidScreen(stored) ? stored : 'chat'
  })

  // useCallback statt der rohen setState-Funktion direkt im Context-Value
  // (wie vorher) - jetzt macht navigateTo ZWEI Dinge (State + localStorage),
  // eine unmemoisierte Wrapper-Funktion wäre bei jedem Render eine neue
  // Referenz und hätte z.B. useSendToLumi() (AgentState.tsx), das
  // navigateTo in seiner eigenen Dependency-Liste hat, unnötig destabilisiert.
  const navigateTo = useCallback((screen: SidebarItemId) => {
    setActiveScreen(screen)
    localStorage.setItem(SCREEN_STORAGE_KEY, screen)
  }, [])

  return <NavigationContext.Provider value={{ activeScreen, navigateTo }}>{children}</NavigationContext.Provider>
}

export function useNavigation() {
  const ctx = useContext(NavigationContext)
  if (!ctx) throw new Error('useNavigation must be used within NavigationProvider')
  return ctx
}
