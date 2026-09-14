import { useState } from 'react'
import Sidebar, { type SidebarItemId } from './components/Sidebar/Sidebar'
import Topbar from './components/Topbar/Topbar'
import Chat from './screens/Chat/Chat'
import KnowledgeHub from './screens/KnowledgeHub/KnowledgeHub'
import Tickets from './screens/Tickets/Tickets'
import Kalender from './screens/Kalender/Kalender'
import Intranet from './screens/Intranet/Intranet'
import { AppNotificationsProvider, useAppNotifications } from './state/AppNotifications'
import { ChatStateProvider } from './state/ChatState'
import { AgentStateProvider } from './state/AgentState'
import { NavigationProvider, useNavigation } from './state/Navigation'
import './App.css'

function AppContent() {
  const { activeScreen, navigateTo } = useNavigation()
  const [hubResetToken, setHubResetToken] = useState(0)
  const { badges } = useAppNotifications()

  function handleNavigate(id: SidebarItemId) {
    navigateTo(id)
    // Sidebar-Icon dient als Home-Button für den Knowledge Hub: jeder Klick
    // (auch bei bereits aktivem Bereich) soll zur Landing-Ansicht zurückführen.
    if (id === 'hub') setHubResetToken((prev) => prev + 1)
  }

  return (
    <div className="app-shell">
      <Topbar />
      <div className="app-shell__body">
        <Sidebar active={activeScreen} onNavigate={handleNavigate} badges={badges} />
        <main className="app-shell__screen">
          {activeScreen === 'chat' ? (
            <Chat />
          ) : activeScreen === 'hub' ? (
            <KnowledgeHub resetToken={hubResetToken} />
          ) : activeScreen === 'tickets' ? (
            <Tickets />
          ) : activeScreen === 'calendar' ? (
            <Kalender />
          ) : (
            <Intranet />
          )}
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <NavigationProvider>
      <AgentStateProvider>
        <AppNotificationsProvider>
          <ChatStateProvider>
            <AppContent />
          </ChatStateProvider>
        </AppNotificationsProvider>
      </AgentStateProvider>
    </NavigationProvider>
  )
}
