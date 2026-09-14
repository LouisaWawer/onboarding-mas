import { createContext, useContext, useState, type ReactNode } from 'react'
import { conversations as initialConversations, type Conversation } from '../screens/Chat/chatData'

type ChatStateContextValue = {
  conversations: Conversation[]
  setConversations: React.Dispatch<React.SetStateAction<Conversation[]>>
}

const ChatStateContext = createContext<ChatStateContextValue | null>(null)

/**
 * Zustand der weiterhin bewusst gescripteten Kolleg:innen-Chats/Kanäle
 * (siehe chatData.ts) - Lumi/der Agent lebt seit der Frontend-Anbindung
 * NICHT mehr hier, sondern in state/AgentState.tsx (useSendToLumi() zieht
 * dort auch ein, siehe dort).
 */
export function ChatStateProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>(initialConversations)
  return <ChatStateContext.Provider value={{ conversations, setConversations }}>{children}</ChatStateContext.Provider>
}

export function useChatState() {
  const ctx = useContext(ChatStateContext)
  if (!ctx) throw new Error('useChatState must be used within ChatStateProvider')
  return ctx
}
