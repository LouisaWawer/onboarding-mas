import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { conversations as initialConversations, type Conversation } from '../screens/Chat/chatData'

type ChatStateContextValue = {
  conversations: Conversation[]
  setConversations: React.Dispatch<React.SetStateAction<Conversation[]>>
}

const ChatStateContext = createContext<ChatStateContextValue | null>(null)

/**
 * Der Chat-Zustand liegt hier statt lokal in Chat.tsx, damit auch andere
 * Screens (z.B. Kalender) Nachrichten in eine bestehende Konversation
 * schreiben können, während die Nutzer:in nicht im Chat ist.
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

/**
 * Schreibt eine Nutzer-Nachricht + eine gescriptete Lumi-Antwort in die
 * Lumi-Konversation und markiert sie als ungelesen – für Aktionen, die
 * Lumi von einem anderen Screen aus "im Hintergrund" ansprechen (z.B.
 * "Neue Besprechung" im Kalender), ohne in den Chat zu navigieren.
 */
export function useSendToLumi() {
  const { setConversations } = useChatState()
  return useCallback(
    (userText: string, lumiReply: string) => {
      setConversations((prev) =>
        prev.map((c) =>
          c.id === 'lumi'
            ? {
                ...c,
                unread: true,
                messages: [...c.messages, { from: 'out', text: userText }, { from: 'in', text: lumiReply }],
              }
            : c,
        ),
      )
    },
    [setConversations],
  )
}
