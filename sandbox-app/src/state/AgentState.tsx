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

type AgentStateContextValue = {
  sessionId: string | null
  /** true, sobald Session + erste Anfrage-Hydrierung durch sind. */
  ready: boolean
  connectionError: string | null
  anfragen: Record<string, AnfrageState>
  activeThreadId: string | null
  // Folgt 1:1 dem Backend (Events + GET /session) - Grundlage für den
  // peripheren Punkt (useOverallStatus unten). NICHT das, was die Karte im
  // Panel/Chat anzeigt, siehe displayedSuggestion.
  pendingSuggestion: api.PendingSuggestion | null
  // Was die Karte tatsächlich zeigt (siehe Bericht an die Nutzerin, Bugfix
  // nach dem ersten Testlauf von Schritt 6) - wird bei einem neuen
  // Vorschlag GLEICHZEITIG mit pendingSuggestion gesetzt, aber NUR durch
  // eine Handlung der Person gelöscht (acceptSuggestion, markSessionSeen),
  // NIE durch das generische status_changed-idle, das serverseitig auch
  // als Nebenwirkung von acknowledgeSuggestion() (POST /session/{id}/seen)
  // zurückkommt. Ohne diese Trennung hätte das Öffnen des Panels die Karte
  // im selben Moment wieder verschworfen, in dem sie sichtbar werden sollte
  // - "dem Backend sagen, dass es aufhören kann" und "die Karte verwerfen"
  // sind zwei verschiedene Dinge, siehe acknowledgeSuggestion-Docstring
  // unten.
  displayedSuggestion: api.PendingSuggestion | null
  setActiveThreadId: (threadId: string) => void
  createAnfrage: () => Promise<string>
  sendMessage: (text: string, opts?: { suggestionScreen?: string }) => Promise<void>
  // Wie sendMessage, aber mit explizitem thread_id statt activeThreadId aus
  // der Closure (siehe acceptSuggestion unten - createAnfrage() setzt
  // activeThreadId per setState, das ist beim direkt folgenden Aufruf
  // innerhalb DERSELBEN Funktion noch nicht sichtbar, ein sendMessage()
  // direkt danach würde also den FALSCHEN/alten Thread treffen). sendMessage
  // selbst ist jetzt ein dünner Wrapper darüber (siehe unten) - eine Quelle,
  // nicht zwei Kopien derselben Logik.
  sendMessageToThread: (threadId: string, text: string, opts?: { suggestionScreen?: string }) => Promise<void>
  resume: (decision: string) => Promise<void>
  markThreadSeen: (threadId: string) => Promise<void>
  // Voller "erledigt"-Zustand: löscht pendingSuggestion LOKAL (die Karte
  // verschwindet) UND meldet es dem Backend. Für: Screenwechsel weg vom
  // Screen, auf den sich der Vorschlag bezieht, UND die Karte-eigene
  // Schließen-Option (X) - beides bedeutet "dieser Vorschlag ist erledigt/
  // hinfällig", nicht nur "gesehen".
  markSessionSeen: () => Promise<void>
  // NUR das Backend informieren (Statuspunkt hört auf zu signalisieren) -
  // OHNE pendingSuggestion lokal zu löschen. Für: Panel-Öffnen (siehe
  // Bericht an die Nutzerin, Schritt 6) - die Karte soll dabei sichtbar UND
  // anklickbar bleiben, nicht im selben Moment verschwinden, in dem sie
  // erst sichtbar wird. markSessionSeen() würde das lokale pendingSuggestion
  // sofort auf null setzen und die Karte damit unmounten, bevor die Person
  // sie überhaupt anklicken kann - deshalb ein separater, bewusst
  // "schwächerer" Aufruf. Ruft serverseitig einen EIGENEN Endpoint auf
  // (POST /session/{id}/acknowledge_suggestion, NICHT mehr /seen -
  // Testpunkt-8-Nachbesserung: /seen löschte den Vorschlag serverseitig
  // komplett, die Karte überlebte dadurch keinen Reload nach dem Öffnen
  // des Panels, siehe routes.py für die volle Begründung).
  acknowledgeSuggestion: () => Promise<void>
  // Erzeugt IMMER eine neue Anfrage (siehe Bericht an die Nutzerin - nie in
  // eine ggf. aktive/beschäftigte Anfrage senden, das gäbe 409) und sendet
  // option.submitted dorthin, mit suggestion_screen = pendingSuggestion.screen
  // (Annahmequote-Logging). Löscht pendingSuggestion lokal SOFORT
  // (optimistisch) - der Klick selbst ist bereits die Handlung, kein
  // Warten auf einen Server-Echo nötig; das Backend räumt
  // pending_suggestion_screen ohnehin defensiv mit auf (siehe post_message,
  // routes.py), ein zusätzlicher markSessionSeen()-Aufruf hier wäre
  // redundant.
  // Liest den Screen aus displayedSuggestion, NICHT pendingSuggestion (das
  // kann zu diesem Zeitpunkt bereits null sein, siehe oben) - siehe
  // displayedSuggestion-Docstring.
  acceptSuggestion: (option: api.SuggestionOption) => Promise<void>
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
  const [pendingSuggestion, setPendingSuggestion] = useState<api.PendingSuggestion | null>(null)
  const [displayedSuggestion, setDisplayedSuggestion] = useState<api.PendingSuggestion | null>(null)

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
          if (event.status === 'suggestion') {
            // acknowledged: false hartcodiert statt aus dem Event gelesen -
            // ein frisch publiziertes suggestion-Event bedeutet strukturell
            // IMMER "gerade neu gesetzt" (set_pending_suggestion() setzt
            // pending_suggestion_acknowledged serverseitig in derselben
            // UPDATE-Anweisung auf 0 zurück, siehe store.py) - kein Feld
            // extra über die Leitung nötig.
            const suggestion = { screen: event.screen, title: event.title, options: event.options, acknowledged: false }
            setPendingSuggestion(suggestion)
            setDisplayedSuggestion(suggestion)
          } else {
            // NUR pendingSuggestion (Punkt) - displayedSuggestion (Karte)
            // bewusst unangetastet, siehe dessen Docstring oben: dieser
            // Zweig feuert auch als serverseitige Nebenwirkung von
            // acknowledgeSuggestion(), nicht nur bei einem echten Verwerfen.
            setPendingSuggestion(null)
          }
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
        // Reload-Fall (siehe Bericht an die Nutzerin, Testpunkt 8): ein
        // beim Laden bereits anstehender Vorschlag kommt hier aus GET
        // /session, nicht aus einem Event - BEIDE States müssen ihn
        // bekommen, sonst wäre die Karte nach einem Reload weg, obwohl das
        // Backend sie noch führt (displayedSuggestion würde sonst nur über
        // den Event-Zweig oben befüllt, hier aber leer bleiben).
        //
        // pendingSuggestion (Punkt) bekommt den Vorschlag NUR, wenn er noch
        // nicht bestätigt ist (acknowledged, siehe PendingSuggestion-Typ,
        // client.ts) - Testpunkt-8-Nachbesserung: sonst würde ein Reload
        // NACH dem Öffnen des Panels den Punkt wieder unnötig auf
        // "suggestion" springen lassen, obwohl die Person schon hingesehen
        // hatte. displayedSuggestion (Karte) bekommt ihn IMMER, unabhängig
        // von acknowledged - die Karte soll ja gerade bestehen bleiben.
        setDisplayedSuggestion(snapshot.pending_suggestion)
        setPendingSuggestion(
          snapshot.pending_suggestion && !snapshot.pending_suggestion.acknowledged ? snapshot.pending_suggestion : null,
        )

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

  const sendMessageToThread = useCallback(
    async (threadId: string, text: string, opts?: { suggestionScreen?: string }) => {
      if (!sessionId) throw new Error('Keine aktive Session.')
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
    [sessionId],
  )

  const sendMessage = useCallback(
    async (text: string, opts?: { suggestionScreen?: string }) => {
      if (!activeThreadId) throw new Error('Keine aktive Anfrage.')
      await sendMessageToThread(activeThreadId, text, opts)
    },
    [activeThreadId, sendMessageToThread],
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
    setDisplayedSuggestion(null)
    await api.postSessionSeen(sessionId)
  }, [sessionId])

  // Siehe Docstring an acknowledgeSuggestion im Context-Typ oben - bewusst
  // KEIN setPendingSuggestion(null) hier, nur der Backend-Aufruf. Bugfix
  // (Testpunkt-8-Nachbesserung): ruft jetzt den EIGENEN Endpoint auf
  // (POST /session/{id}/acknowledge_suggestion), nicht mehr
  // postSessionSeen() - der löschte pending_suggestion_screen serverseitig
  // komplett, wodurch die Karte einen Reload nach dem Öffnen des Panels
  // nicht überlebte (GET /session fand danach nichts mehr, unabhängig
  // davon, dass displayedSuggestion hier lokal unangetastet blieb).
  const acknowledgeSuggestion = useCallback(async () => {
    if (!sessionId) return
    await api.postAcknowledgeSuggestion(sessionId)
  }, [sessionId])

  const acceptSuggestion = useCallback(
    async (option: api.SuggestionOption) => {
      if (!sessionId || !displayedSuggestion) return
      const screen = displayedSuggestion.screen
      setPendingSuggestion(null)
      setDisplayedSuggestion(null)
      const threadId = await createAnfrage()
      await sendMessageToThread(threadId, option.submitted, { suggestionScreen: screen })
    },
    [sessionId, displayedSuggestion, createAnfrage, sendMessageToThread],
  )

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
    displayedSuggestion,
    setActiveThreadId,
    createAnfrage,
    sendMessage,
    sendMessageToThread,
    resume,
    markThreadSeen,
    markSessionSeen,
    acknowledgeSuggestion,
    acceptSuggestion,
    reportScreenDwell,
  }

  return <AgentStateContext.Provider value={value}>{children}</AgentStateContext.Provider>
}

export function useAgentState() {
  const ctx = useContext(AgentStateContext)
  if (!ctx) throw new Error('useAgentState must be used within AgentStateProvider')
  return ctx
}

// Rangfolge über ALLE Anfragen der Session (siehe Bericht an die Nutzerin,
// Schritt 5 - peripherer Statuspunkt): GET /session liefert pro Anfrage
// einen eigenen Status, das Backend kürt bewusst keinen Gewinner ("das ist
// eine Frontend-Entscheidung"). "waiting" schlägt alles andere - was eine
// Antwort braucht, schlägt was nur informiert -, "idle" verliert immer.
// "suggestion" ist SESSION-weit (status_changed mit thread_id: null),
// nicht Teil der Anfragen-Map - fließt hier als eigener Kandidat ein,
// nicht über anfragen[...].status.
const STATUS_PRIORITY: api.StatusValue[] = ['waiting', 'error', 'working', 'result', 'suggestion', 'idle']

/**
 * Ein einzelner Statuswert für den peripheren Punkt (StatusDot) - über alle
 * gleichzeitig offenen Anfragen der Session hinweg aufgelöst, per fester
 * Rangfolge (siehe oben). Eigener Hook statt Inline-Logik im StatusDot,
 * damit die Rangfolge an einer Stelle steht, nicht in jeder Komponente, die
 * sie braucht.
 */
export function useOverallStatus(): api.StatusValue {
  const { anfragen, pendingSuggestion } = useAgentState()
  const present = new Set<api.StatusValue>(Object.values(anfragen).map((a) => a.status))
  if (pendingSuggestion) present.add('suggestion')
  for (const candidate of STATUS_PRIORITY) {
    if (present.has(candidate)) return candidate
  }
  return 'idle'
}

/**
 * Ersatz für das frühere useSendToLumi() aus state/ChatState.tsx - schickt
 * jetzt eine ECHTE Nutzernachricht an die aktive Anfrage (statt eine feste
 * Antwort in einen lokalen Mock zu schreiben) und wechselt in den Chat, wo
 * die echte Antwort über SSE eintrifft (siehe Chat.tsx). Aufrufer: bisher
 * nur Kalender.tsx ("Neue Besprechung") - der Intranet-Trigger wurde wieder
 * entfernt (siehe Intranet.tsx-Kommentar).
 *
 * Nur EIN Text-Parameter (statt vorher userText+lumiReply) - eine
 * gescriptete Antwort gibt es nicht mehr, die kommt vom echten Agenten.
 *
 * Bugfix (siehe Bericht an die Nutzerin, Schritt 4): die frühere Lücke
 * ("sendet unbedingt, auch wenn die aktive Anfrage working/waiting ist,
 * führt dann zu einem serverseitig abgelehnten 409, sichtbar nur in der
 * Konsole") ist behoben - `busy` gibt den Beschäftigt-Zustand der AKTIVEN
 * Anfrage zurück, damit der Aufrufer seinen eigenen Auslöser (Button)
 * deaktivieren kann, statt den Klick stillschweigend ins Leere laufen zu
 * lassen. Gleicher Mechanismus wie beim Chat-Composer selbst
 * (isAgentBusy in Chat.tsx), nicht eine zweite UI-Sprache dafür. `send`
 * lehnt zusätzlich defensiv ab, wenn trotzdem während `busy` aufgerufen
 * wird (z.B. ein Klick knapp vor dem Disabled-Zustand) - kein 409 mehr,
 * der nur in der Konsole landet.
 */
export function useSendToLumi() {
  const { sendMessage, activeThreadId, anfragen } = useAgentState()
  const { navigateTo } = useNavigation()
  const activeStatus = activeThreadId ? anfragen[activeThreadId]?.status : undefined
  const busy = activeStatus === 'working' || activeStatus === 'waiting'
  const send = useCallback(
    (text: string) => {
      if (busy) return
      navigateTo('chat')
      sendMessage(text).catch((err) => console.error('[send-to-lumi] sendMessage fehlgeschlagen', err))
    },
    [busy, sendMessage, navigateTo],
  )
  return { send, busy }
}
