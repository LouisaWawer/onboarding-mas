/**
 * Fetch-Wrapper für die FastAPI-Schicht (backend/api/) - ein Modul statt
 * verstreuter fetch()-Aufrufe (siehe Auftrag Punkt 1). Kein React hier -
 * reine HTTP-Funktionen, die state/AgentState.tsx orchestriert.
 *
 * Typen sind 1:1 aus backend/api/models.py übertragen, nicht generiert -
 * bei Schema-Änderungen dort müssen sie hier von Hand nachgezogen werden.
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000'

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API-Fehler ${status}: ${detail}`)
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, detail)
  }
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

// --- Typen (siehe backend/api/models.py) -----------------------------------

export type StatusValue = 'idle' | 'working' | 'waiting' | 'result' | 'error' | 'suggestion'

export type AnfrageSummary = {
  thread_id: string
  title: string | null
  created_at: string
  last_active_at: string
  status: StatusValue
}

export type PendingSuggestion = {
  screen: string
  text: string
}

export type SessionSnapshot = {
  session_id: string
  anfragen: AnfrageSummary[]
  active_thread_id: string | null
  pending_suggestion: PendingSuggestion | null
}

export type AnfrageOut = {
  thread_id: string
  title: string | null
  created_at: string
  last_active_at: string
}

export type RationaleStep = {
  label: string
  detail: string | null
  source: { title?: string; path?: string } | null
}

export type Rationale = {
  steps: RationaleStep[]
}

export type MessageOut = {
  role: 'user' | 'assistant'
  content: string
  rationale: Rationale | null
}

export type InterruptPayload = {
  proposal: Record<string, unknown> | null
  options: string[]
  change_notice: string | null
}

export type ThreadSnapshot = {
  thread_id: string
  session_id: string
  status: StatusValue
  messages: MessageOut[]
  interrupt: InterruptPayload | null
}

// --- Endpunkte ---------------------------------------------------------------

export function createSession(accessCode: string, signal?: AbortSignal): Promise<SessionSnapshot> {
  return request('/session', {
    method: 'POST',
    body: JSON.stringify({ access_code: accessCode }),
    signal,
  })
}

export function getSession(sessionId: string, signal?: AbortSignal): Promise<SessionSnapshot> {
  return request(`/session/${sessionId}`, { signal })
}

export function createAnfrage(sessionId: string): Promise<AnfrageOut> {
  return request(`/session/${sessionId}/anfrage`, { method: 'POST' })
}

export function getThread(threadId: string, sessionId: string, signal?: AbortSignal): Promise<ThreadSnapshot> {
  return request(`/thread/${threadId}?session_id=${encodeURIComponent(sessionId)}`, { signal })
}

export function postMessage(
  threadId: string,
  sessionId: string,
  text: string,
  opts?: { channel?: 'dm' | 'status_panel'; suggestionScreen?: string },
): Promise<{ accepted: boolean }> {
  return request(`/message/${threadId}`, {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      text,
      channel: opts?.channel,
      suggestion_screen: opts?.suggestionScreen,
    }),
  })
}

export function postResume(threadId: string, sessionId: string, decision: string): Promise<{ accepted: boolean }> {
  return request(`/resume/${threadId}`, {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, decision }),
  })
}

export function postThreadSeen(threadId: string, sessionId: string): Promise<{ accepted: boolean }> {
  return request(`/thread/${threadId}/seen`, {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  })
}

export function postSessionSeen(sessionId: string): Promise<{ accepted: boolean }> {
  return request(`/session/${sessionId}/seen`, { method: 'POST' })
}

export function postScreen(
  sessionId: string,
  screen: 'intranet' | 'chat' | 'hub' | 'tickets' | 'calendar',
): Promise<{ accepted: boolean }> {
  return request(`/session/${sessionId}/screen`, {
    method: 'POST',
    body: JSON.stringify({ screen }),
  })
}
