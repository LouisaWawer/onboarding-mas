/**
 * SSE-Anbindung an GET /events/{session_id} - ein Handler pro Session-Leben,
 * der thread-bezogene und session-bezogene Events unterscheidet (siehe
 * backend/api/routes.py, stream_events()).
 *
 * Native EventSource statt einer Library: Keepalive-Kommentarzeilen (": ...")
 * ignoriert der Browser selbst (Teil der SSE-Spezifikation), und jede
 * event: <typ>-Zeile braucht einen eigenen addEventListener(typ, ...) -
 * ein bloßer onmessage-Handler würde NUR unbenannte Events fangen, hier gibt
 * es aber keine.
 */

import type { InterruptPayload, MessageOut, Rationale, StatusValue, SuggestionOption } from './client'

export type SSEEvent =
  | { type: 'status_changed'; thread_id: string; status: StatusValue }
  | {
      type: 'status_changed'
      thread_id: null
      status: 'suggestion'
      screen: string
      title: string
      options: SuggestionOption[]
    }
  | { type: 'status_changed'; thread_id: null; status: Exclude<StatusValue, 'suggestion'> }
  | { type: 'message_appended'; thread_id: string; message: { role: 'user' | 'assistant'; content: string }; rationale: Rationale | null }
  | ({ type: 'interrupt_pending'; thread_id: string } & InterruptPayload)
  | { type: 'interrupt_resolved'; thread_id: string }
  | { type: 'anfrage_created'; thread_id: string; title: string | null }
  | { type: 'anfrage_titled'; thread_id: string; title: string | null }

const EVENT_TYPES = [
  'status_changed',
  'message_appended',
  'interrupt_pending',
  'interrupt_resolved',
  'anfrage_created',
  'anfrage_titled',
] as const

/**
 * Öffnet die Verbindung und ruft onEvent für jedes geparste Event auf.
 * Gibt eine Cleanup-Funktion zurück (Listener abmelden + Verbindung schließen).
 */
export function subscribeToSession(
  sessionId: string,
  onEvent: (event: SSEEvent) => void,
  onError?: (err: Event) => void,
): () => void {
  const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000'
  const source = new EventSource(`${API_BASE}/events/${sessionId}`)

  const listeners = EVENT_TYPES.map((type) => {
    const listener = (evt: MessageEvent<string>) => {
      try {
        onEvent(JSON.parse(evt.data) as SSEEvent)
      } catch (err) {
        console.error('[sse] Event konnte nicht geparst werden', type, evt.data, err)
      }
    }
    source.addEventListener(type, listener)
    return { type, listener }
  })

  source.onerror = (err) => {
    console.error('[sse] Verbindungsfehler', err)
    onError?.(err)
  }

  return () => {
    for (const { type, listener } of listeners) source.removeEventListener(type, listener)
    source.close()
  }
}
