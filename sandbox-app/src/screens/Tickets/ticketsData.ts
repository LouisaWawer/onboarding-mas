import type { TaskState } from '../../components/TaskStatus/TaskStatus'

export type Ticket = {
  id: string
  date: string
  topic: string
  department: string
  status: TaskState
  ticketid: string
  estimate: string
  /** Steuert den Sidebar-Badge, solange die Tickets-Ansicht noch nicht geöffnet wurde. */
  isNew?: boolean
}

/* 1:1 aus Figma übernommen (Table, node 45:7245). */
export const tickets: Ticket[] = [
  { id: 't1', date: '22. Aug', topic: 'VPN-Zugang beantragen', department: 'IT', status: 'open', ticketid: 'N0012', estimate: '2 Tage' },
  {
    id: 't2',
    date: '23. Aug',
    topic: 'Software-Update durchführen',
    department: 'IT',
    status: 'processing',
    ticketid: 'N0013',
    estimate: '1 Stunde',
    isNew: true,
  },
  {
    id: 't3',
    date: '24. Aug',
    topic: 'Sicherheitsrichtlinien prüfen',
    department: 'IT',
    status: 'done',
    ticketid: 'N0014',
    estimate: '3 Tage',
  },
]
