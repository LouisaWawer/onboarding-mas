import { useEffect, useState } from 'react'
import TaskStatus from '../../components/TaskStatus/TaskStatus'
import { useReportBadge } from '../../state/AppNotifications'
import { useAgentState } from '../../state/AgentState'
import * as api from '../../api/client'
import { tickets as initialTickets, type Ticket } from './ticketsData'
import './Tickets.css'

/**
 * Entspricht Figmas Tickets-Screen (node 44:6215). Reine Listenansicht,
 * kein "Neues Ticket"-Formular im Figma-Header vorhanden – laut
 * docs/Szenario_Interaktionsdesign.md läuft das Anlegen neuer Anfragen
 * (u.a. VPN-Zugang) über den Onboarding-Assistenten Lumi im Chat, nicht
 * über ein manuelles Formular hier.
 *
 * Von Lumi angelegte Tickets (siehe Bericht an die Nutzerin) werden einmal
 * beim Betreten des Screens geladen (GET /session/{id}/tickets, kein
 * Live-Sync) und VOR den drei festen Demo-Tickets eingefügt - ohne das
 * würde Lumi "Erledigt" sagen, aber hier erschiene nichts, was für RQ1
 * irreführend wäre.
 */
export default function Tickets() {
  const { sessionId } = useAgentState()
  const [tickets, setTickets] = useState<Ticket[]>(initialTickets)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) return
    const controller = new AbortController()
    api
      .getSessionTickets(sessionId, controller.signal)
      .then((res) => {
        const synced: Ticket[] = res.tickets.map((t) => ({
          id: `synced-${t.ticketid}`,
          date: t.date,
          topic: t.topic,
          department: t.department,
          status: t.status,
          ticketid: t.ticketid,
          // Ehrlicher Platzhalter statt einer erfundenen Dauer - dieselbe
          // Begründung wie bei der Priorität im Bestätigungskarten-Fund
          // (siehe Bericht an die Nutzerin): das Backend trackt keine
          // Bearbeitungszeit, eine plausibel aussehende Zahl wäre erfunden.
          estimate: '–',
          isNew: t.is_new,
        }))
        setTickets([...synced, ...initialTickets])
      })
      .catch((err) => {
        // Abbruch beim Verlassen des Screens ist erwartet, kein echter
        // Fehler (gleiches Prinzip wie im Session-Bootstrap, siehe
        // AgentState.tsx).
        const isAbort = err instanceof DOMException && err.name === 'AbortError'
        if (!isAbort) console.error('[tickets] Sync mit Lumi-Tickets fehlgeschlagen', err)
      })
    return () => controller.abort()
  }, [sessionId])

  useReportBadge('tickets', tickets.some((t) => t.isNew))

  function selectTicket(id: string) {
    setSelectedId(id)
    setTickets((prev) => prev.map((t) => (t.id === id ? { ...t, isNew: false } : t)))
  }

  return (
    <div className="tickets">
      <div className="tickets__card">
        <header className="tickets__header">
          <h1 className="tickets__title">Tickets</h1>
        </header>
        <div className="tickets__divider" />

        <div className="tickets__table">
          <div className="tickets__row tickets__row--header">
            <span className="tickets__col tickets__col--date">Datum</span>
            <span className="tickets__col tickets__col--topic">Thema</span>
            <span className="tickets__col tickets__col--department">Abteilung</span>
            <span className="tickets__col tickets__col--status">Status</span>
            <span className="tickets__col tickets__col--ticketid">Ticket ID</span>
            <span className="tickets__col tickets__col--estimate">geschätzte Bearbeitungszeit</span>
            <span className="tickets__col tickets__col--indicator" />
          </div>

          {tickets.map((ticket) => (
            <button
              type="button"
              className={`tickets__row ${ticket.id === selectedId ? 'tickets__row--active' : ''}`}
              key={ticket.id}
              onClick={() => selectTicket(ticket.id)}
            >
              <span className="tickets__col tickets__col--date">{ticket.date}</span>
              <span className="tickets__col tickets__col--topic">{ticket.topic}</span>
              <span className="tickets__col tickets__col--department">{ticket.department}</span>
              <span className="tickets__col tickets__col--status">
                <TaskStatus state={ticket.status} />
              </span>
              <span className="tickets__col tickets__col--ticketid">{ticket.ticketid}</span>
              <span className="tickets__col tickets__col--estimate">{ticket.estimate}</span>
              <span className="tickets__col tickets__col--indicator">
                {ticket.isNew && <span className="tickets__new-dot" aria-label="Neues Ticket" />}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
