import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import * as api from '../api/client'
import { subscribeToSession, type SSEEvent } from '../api/events'
import { useNavigation } from './Navigation'

const SESSION_STORAGE_KEY = 'onboarding-mas:session_id'
const ACCESS_CODE = (import.meta.env.VITE_ACCESS_CODE as string | undefined) ?? ''

/**
 * MessageOut (Backend) trägt KEINEN Zeitstempel - für den Datums-Trenner
 * und "vor X Minuten" unter jeder Lumi-Nachricht (siehe Bericht an die
 * Nutzerin) brauchen wir trotzdem einen. receivedAt wird deshalb rein
 * clientseitig beim ERSTEN Beobachten einer Nachricht gesetzt (live per SSE
 * oder bei der Hydrierung). Bekannte Ungenauigkeit: bei einem Reload/einer
 * Hydrierung bekommen ALLE bereits vorhandenen Nachrichten denselben
 * Zeitpunkt (den der Hydrierung) - für eine frische Studien-Sitzung in
 * einer Sitzung unkritisch, würde aber über einen echten zeitlichen Abstand
 * hinweg falsch aussehen. Keine Backend-Änderung hierfür vorgenommen -
 * außerhalb des Auftrags ("reine Darstellung").
 */
export type DisplayMessage = api.MessageOut & { receivedAt: number }

export type AnfrageState = {
  threadId: string
  title: string | null
  status: api.StatusValue
  messages: DisplayMessage[]
  interrupt: api.InterruptPayload | null
}

type PendingSuggestion = {
  screen: string
  text: string
}

type AgentStateContextValue = {
  sessionId: string | null
  /** true, sobald Session + erste Anfrage-Hydrierung durch sind. */
  ready: boolean
  connectionError: string | null
  anfragen: Record<string, AnfrageState>
  activeThreadId: string | null
  pendingSuggestion: PendingSuggestion | null
  setActiveThreadId: (threadId: string) => void
  createAnfrage: () => Promise<string>
  sendMessage: (text: string, opts?: { suggestionScreen?: string }) => Promise<void>
  resume: (decision: string) => Promise<void>
  markThreadSeen: (threadId: string) => Promise<void>
  markSessionSeen: () => Promise<void>
  reportScreenDwell: (screen: 'intranet' | 'hub' | 'tickets' | 'calendar') => Promise<void>
}

const AgentStateContext = createContext<AgentStateContextValue | null>(null)

function anfrageFromSummary(s: api.AnfrageSummary): AnfrageState {
  return { threadId: s.thread_id, title: s.title, status: s.status, messages: [], interrupt: null }
}

function mergeThreadSnapshot(prev: AnfrageState | undefined, threadId: string, snapshot: api.ThreadSnapshot): AnfrageState {
  // receivedAt hier einheitlich "jetzt" für die gesamte Historie - siehe
  // Docstring von DisplayMessage für die bekannte Ungenauigkeit.
  const now = Date.now()
  return {
    threadId,
    title: prev?.title ?? null,
    status: snapshot.status,
    messages: snapshot.messages.map((m) => ({ ...m, receivedAt: now })),
    interrupt: snapshot.interrupt,
  }
}

export function AgentStateProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [anfragen, setAnfragen] = useState<Record<string, AnfrageState>>({})
  const [activeThreadId, setActiveThreadIdState] = useState<string | null>(null)
  const [pendingSuggestion, setPendingSuggestion] = useState<PendingSuggestion | null>(null)

  // Schließt die vorherige SSE-Verbindung, falls die Provider-Instanz aus
  // irgendeinem Grund neu mounten sollte (StrictMode-Doppel-Mount in Dev).
  const unsubscribeRef = useRef<(() => void) | undefined>(undefined)

  const hydrateThread = useCallback(async (threadId: string, currentSessionId: string, signal?: AbortSignal) => {
    const snapshot = await api.getThread(threadId, currentSessionId, signal)
    setAnfragen((prev) => ({ ...prev, [threadId]: mergeThreadSnapshot(prev[threadId], threadId, snapshot) }))
  }, [])

  const handleEvent = useCallback((event: SSEEvent) => {
    console.log('[agent-event]', event)
    switch (event.type) {
      case 'status_changed': {
        if (event.thread_id === null) {
          setPendingSuggestion(event.status === 'suggestion' ? { screen: event.screen, text: event.text } : null)
        } else {
          const threadId = event.thread_id
          setAnfragen((prev) => (prev[threadId] ? { ...prev, [threadId]: { ...prev[threadId], status: event.status } } : prev))
        }
        break
      }
      case 'message_appended': {
        const threadId = event.thread_id
        setAnfragen((prev) => {
          const existing = prev[threadId]
          if (!existing) return prev
          const message: DisplayMessage = { ...event.message, rationale: event.rationale, receivedAt: Date.now() }
          return { ...prev, [threadId]: { ...existing, messages: [...existing.messages, message] } }
        })
        break
      }
      case 'interrupt_pending': {
        const threadId = event.thread_id
        setAnfragen((prev) =>
          prev[threadId]
            ? {
                ...prev,
                [threadId]: {
                  ...prev[threadId],
                  interrupt: { proposal: event.proposal, options: event.options, change_notice: event.change_notice },
                },
              }
            : prev,
        )
        break
      }
      case 'interrupt_resolved': {
        const threadId = event.thread_id
        setAnfragen((prev) => (prev[threadId] ? { ...prev, [threadId]: { ...prev[threadId], interrupt: null } } : prev))
        break
      }
      case 'anfrage_created': {
        const threadId = event.thread_id
        setAnfragen((prev) =>
          prev[threadId]
            ? prev
            : { ...prev, [threadId]: { threadId, title: event.title, status: 'idle', messages: [], interrupt: null } },
        )
        break
      }
      case 'anfrage_titled': {
        const threadId = event.thread_id
        setAnfragen((prev) => (prev[threadId] ? { ...prev, [threadId]: { ...prev[threadId], title: event.title } } : prev))
        break
      }
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    // AbortController zusätzlich zum cancelled-Flag: cancelled verhindert nur,
    // dass eine bereits abgeschlossene Antwort noch verarbeitet wird - das
    // fetch()-Request selbst läuft server-seitig trotzdem zu Ende. In
    // StrictMode (Dev, doppelter Mount) entsteht dadurch sonst pro Erstladung
    // eine verwaiste Session samt zweier Preseed-Anfragen im Backend. abort()
    // storniert das Request clientseitig, sodass der zweite Mount (die
    // "echte" Instanz) i.d.R. als einzige tatsächlich eine Session anlegt -
    // je nachdem, wie weit das erste Request beim Abbruch schon raus war,
    // kann das Backend es trotzdem noch verarbeitet haben, aber der
    // Normalfall wird dadurch sauber.
    const controller = new AbortController()

    async function bootstrap() {
      if (!ACCESS_CODE) {
        setConnectionError('Kein Zugangscode konfiguriert (VITE_ACCESS_CODE fehlt - sandbox-app/.env anlegen, siehe .env.example).')
        return
      }
      try {
        // Reconnect: dieselbe Session über einen Reload hinweg wiederverwenden
        // statt bei jedem Laden neue (mit frischen, leeren Preseed-Anfragen)
        // anzulegen - GET /session ist genau dafür ausgelegt (siehe Auftrag,
        // Abschnitt RECONNECT).
        const storedSessionId = localStorage.getItem(SESSION_STORAGE_KEY)
        let snapshot: api.SessionSnapshot
        if (storedSessionId) {
          try {
            snapshot = await api.getSession(storedSessionId, controller.signal)
          } catch (err) {
            if (err instanceof api.ApiError && err.status === 404) {
              snapshot = await api.createSession(ACCESS_CODE, controller.signal)
            } else {
              throw err
            }
          }
        } else {
          snapshot = await api.createSession(ACCESS_CODE, controller.signal)
        }
        if (cancelled) return

        localStorage.setItem(SESSION_STORAGE_KEY, snapshot.session_id)
        setSessionId(snapshot.session_id)
        setAnfragen(Object.fromEntries(snapshot.anfragen.map((a) => [a.thread_id, anfrageFromSummary(a)])))
        setActiveThreadIdState(snapshot.active_thread_id)
        setPendingSuggestion(snapshot.pending_suggestion)

        if (snapshot.active_thread_id) {
          await hydrateThread(snapshot.active_thread_id, snapshot.session_id, controller.signal)
        }
        if (cancelled) return
        setReady(true)

        unsubscribeRef.current = subscribeToSession(snapshot.session_id, handleEvent, () =>
          setConnectionError('SSE-Verbindung unterbrochen - Browser versucht automatisch, neu zu verbinden.'),
        )
      } catch (err) {
        // Ein abgebrochenes Request (StrictMode-Doppel-Mount) ist erwartet,
        // kein echter Fehler - cancelled ist an dieser Stelle ohnehin schon
        // true (Cleanup läuft synchron vor dem Reject), aber die eigene
        // AbortError-Prüfung hält die Konsole zusätzlich sauber.
        const isAbort = err instanceof DOMException && err.name === 'AbortError'
        if (!isAbort) console.error('[agent-state] Session-Bootstrap fehlgeschlagen', err)
        if (!cancelled && !isAbort) setConnectionError(err instanceof Error ? err.message : String(err))
      }
    }

    bootstrap()
    return () => {
      cancelled = true
      controller.abort()
      unsubscribeRef.current?.()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const setActiveThreadId = useCallback(
    (threadId: string) => {
      setActiveThreadIdState(threadId)
      if (sessionId) {
        hydrateThread(threadId, sessionId).catch((err) => console.error('[agent-state] hydrateThread fehlgeschlagen', err))
      }
    },
    [sessionId, hydrateThread],
  )

  const createAnfrage = useCallback(async (): Promise<string> => {
    if (!sessionId) throw new Error('Keine aktive Session.')
    const created = await api.createAnfrage(sessionId)
    setAnfragen((prev) => ({
      ...prev,
      [created.thread_id]: { threadId: created.thread_id, title: created.title, status: 'idle', messages: [], interrupt: null },
    }))
    setActiveThreadIdState(created.thread_id)
    return created.thread_id
  }, [sessionId])

  const sendMessage = useCallback(
    async (text: string, opts?: { suggestionScreen?: string }) => {
      if (!sessionId || !activeThreadId) throw new Error('Keine aktive Anfrage.')
      const threadId = activeThreadId
      // WICHTIG: das Backend sendet die eigene Nutzernachricht NIE über
      // message_appended zurück (known_message_count in graph_runner.py
      // zählt sie ab dem Moment des Aufrufs schon mit) - deshalb hier
      // optimistisch lokal anhängen, nicht auf ein Echo warten.
      setAnfragen((prev) =>
        prev[threadId]
          ? {
              ...prev,
              [threadId]: {
                ...prev[threadId],
                messages: [...prev[threadId].messages, { role: 'user', content: text, rationale: null, receivedAt: Date.now() }],
              },
            }
          : prev,
      )
      await api.postMessage(threadId, sessionId, text, { suggestionScreen: opts?.suggestionScreen })
    },
    [sessionId, activeThreadId],
  )

  const resume = useCallback(
    async (decision: string) => {
      if (!sessionId || !activeThreadId) throw new Error('Keine aktive Anfrage.')
      await api.postResume(activeThreadId, sessionId, decision)
    },
    [sessionId, activeThreadId],
  )

  const markThreadSeen = useCallback(
    async (threadId: string) => {
      if (!sessionId) return
      await api.postThreadSeen(threadId, sessionId)
    },
    [sessionId],
  )

  const markSessionSeen = useCallback(async () => {
    if (!sessionId) return
    setPendingSuggestion(null)
    await api.postSessionSeen(sessionId)
  }, [sessionId])

  const reportScreenDwell = useCallback(
    async (screen: 'intranet' | 'hub' | 'tickets' | 'calendar') => {
      if (!sessionId) return
      await api.postScreen(sessionId, screen)
    },
    [sessionId],
  )

  const value: AgentStateContextValue = {
    sessionId,
    ready,
    connectionError,
    anfragen,
    activeThreadId,
    pendingSuggestion,
    setActiveThreadId,
    createAnfrage,
    sendMessage,
    resume,
    markThreadSeen,
    markSessionSeen,
    reportScreenDwell,
  }

  return <AgentStateContext.Provider value={value}>{children}</AgentStateContext.Provider>
}

export function useAgentState() {
  const ctx = useContext(AgentStateContext)
  if (!ctx) throw new Error('useAgentState must be used within AgentStateProvider')
  return ctx
}

/**
 * Ersatz für das frühere useSendToLumi() aus state/ChatState.tsx - schickt
 * jetzt eine ECHTE Nutzernachricht an die aktive Anfrage (statt eine feste
 * Antwort in einen lokalen Mock zu schreiben) und wechselt in den Chat, wo
 * die echte Antwort über SSE eintrifft (siehe Chat.tsx). Aufrufer: bisher
 * Kalender.tsx ("Neue Besprechung") und Intranet.tsx ("Angaben nicht
 * aktuell? Melden").
 *
 * Nur EIN Text-Parameter (statt vorher userText+lumiReply) - eine
 * gescriptete Antwort gibt es nicht mehr, die kommt vom echten Agenten.
 *
 * Bekannte Lücke für diese Stufe: sendet unbedingt, auch wenn die aktive
 * Anfrage gerade "working"/"waiting" ist - führt dann zu einem serverseitig
 * abgelehnten (409) Aufruf, sichtbar nur in der Konsole. Kalender.tsx/
 * Intranet.tsx zeigen dafür aktuell keine eigene Rückmeldung an - für
 * Schritt 2 bewusst nicht gebaut.
 */
export function useSendToLumi() {
  const { sendMessage } = useAgentState()
  const { navigateTo } = useNavigation()
  return useCallback(
    (text: string) => {
      navigateTo('chat')
      sendMessage(text).catch((err) => console.error('[send-to-lumi] sendMessage fehlgeschlagen', err))
    },
    [sendMessage, navigateTo],
  )
}
