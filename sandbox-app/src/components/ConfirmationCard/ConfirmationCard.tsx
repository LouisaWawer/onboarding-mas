import { useState } from 'react'
import { CaretDown, CaretUp, Warning } from '@phosphor-icons/react'
import type { InterruptPayload } from '../../api/client'
import PushButton from '../PushButton/PushButton'
import './ConfirmationCard.css'

type ConfirmationCardProps = {
  interrupt: InterruptPayload
  onResume: (decision: string) => Promise<void>
}

// 0=Montag...4=Freitag, deckungsgleich mit graph.py (WEEKDAY_NAMES) und
// kalenderData.ts (Appointment.day) - siehe Bericht an die Nutzerin: eine
// Karte, die "weekday: 3" anzeigt, ist für eine Testperson nicht zu
// gebrauchen, sie soll eine informierte Entscheidung treffen können.
const WEEKDAY_NAMES = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']

/**
 * Kontextzeile je Tool - GENERISCH über einen Fallback abgesichert (siehe
 * unten), diese Map deckt nur die beiden aktuell erreichbaren Tools ab
 * (siehe Setup_Dokumentation.md Abschnitt 2, "Erreichbar"). Ein künftiges,
 * hier unbekanntes Tool zeigt seinen rohen Tool-Namen statt zu crashen.
 */
function contextLine(tool: string, args: Record<string, unknown>): string {
  if (tool === 'create_ticket') {
    const department = typeof args.department === 'string' ? args.department : 'IT'
    return `Ticket bei ${department} erstellen`
  }
  if (tool === 'add_calendar_event') return 'Termin eintragen'
  return tool
}

function formatFieldValue(key: string, value: unknown): string | null {
  if (value === null || value === undefined || value === '') return null
  // Die beiden einzigen Felder, die roh (als Zahl) für eine Testperson
  // unlesbar wären - siehe Moduldocstring.
  if (key === 'weekday' && typeof value === 'number') return WEEKDAY_NAMES[value] ?? String(value)
  if (key === 'hour' && typeof value === 'number') return `${String(value).padStart(2, '0')}:00`
  return String(value)
}

/**
 * Alles aus proposal.args, was nicht schon als Betreff (subject/title) oder
 * in der Kontextzeile (department) gezeigt wird - GENERISCH über
 * Object.entries, nicht auf create_ticket/add_calendar_event festgelegt:
 * für create_ticket bleibt aktuell "priority" übrig (description separat,
 * siehe unten), für add_calendar_event weekday/hour/location/organizer -
 * beides landet automatisch hinter dem Auf-/Zuklapp-Chevron (siehe
 * ConfirmationCard, expanded-State unten), kein tool-spezifischer
 * Sonderfall im Code nötig.
 */
function detailParts(args: Record<string, unknown>): string[] {
  const consumed = new Set(['subject', 'title', 'department', 'description'])
  return Object.entries(args)
    .filter(([key]) => !consumed.has(key))
    .map(([key, value]) => formatFieldValue(key, value))
    .filter((v): v is string => v !== null)
}

export default function ConfirmationCard({ interrupt, onResume }: ConfirmationCardProps) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Figma (ConfirmationCard, node 228:5579/229:5687) zeigt seit der
  // Prioritäts-Ergänzung einen Chevron am Betreff - der graue Block ist
  // dort keine feste 2-/3-Zeilen-Fläche mehr, sondern klappt zusätzliche
  // Felder auf/zu (gleiches Prinzip wie RationaleBlock). Kein eigenes
  // Referenzbild für den EINGEKLAPPTEN Zustand in der Datei vorhanden (nur
  // eine statische Variante je Karten-Zustand) - Standardkonvention
  // übernommen: zu (CaretDown) = mehr vorhanden, auf (CaretUp) = weniger.
  const [expanded, setExpanded] = useState(false)

  const proposal = (interrupt.proposal ?? {}) as Record<string, unknown>
  const tool = typeof proposal.tool === 'string' ? proposal.tool : ''
  const args = (proposal.args ?? {}) as Record<string, unknown>
  const subject = (typeof args.subject === 'string' && args.subject) || (typeof args.title === 'string' && args.title) || ''
  const reason = typeof proposal.reason === 'string' ? proposal.reason : ''
  // description (create_ticket) ist an den Ticketempfänger gerichtet,
  // dritte Person - NICHT zu verwechseln mit reason (zweite Person, an die
  // Nutzer:in, unten außerhalb des grauen Blocks). Design: grauer Block =
  // was ins Ticket geht (inkl. description), Text darunter = warum, an die
  // Person gerichtet. Eigene Zeile statt in details eingereiht - ein voller
  // Satz neben kurzen Werten wie "normal" über " · " gejoint sähe falsch
  // aus.
  const description = typeof args.description === 'string' ? args.description : ''
  const details = detailParts(args)
  const hasExpandableContent = Boolean(description) || details.length > 0
  const isWarning = Boolean(interrupt.change_notice)

  async function handleClick(decision: string) {
    if (submitting) return
    setSubmitting(true)
    setError(null)
    try {
      await onResume(decision)
      // Kein setSubmitting(false) im Erfolgsfall: interrupt_resolved kommt
      // per SSE und lässt die Karte unmounten (siehe Chat.tsx) - ein Reset
      // hier würde nur für einen kurzen Moment nutzlose, wieder aktive
      // Buttons zeigen, bevor sie ohnehin verschwinden.
    } catch (err) {
      console.error('[confirmation-card] resume fehlgeschlagen', err)
      setError('Konnte nicht gesendet werden - bitte noch einmal versuchen.')
      setSubmitting(false)
    }
  }

  return (
    <div className="confirmation-card">
      <div className="confirmation-card__header">Ich brauche deine Bestätigung</div>

      {isWarning && (
        <div className="confirmation-card__warning">
          <Warning size={24} weight="fill" color="var(--color-warning-muted)" />
          <span>{interrupt.change_notice}</span>
        </div>
      )}

      <div className="confirmation-card__action">
        <span className="confirmation-card__context">{contextLine(tool, args)}</span>
        <div className="confirmation-card__subject-row">
          <span className="confirmation-card__subject">{subject}</span>
          {hasExpandableContent && (
            <button
              type="button"
              className="confirmation-card__expand-toggle"
              onClick={() => setExpanded((prev) => !prev)}
              aria-expanded={expanded}
              aria-label={expanded ? 'Details einklappen' : 'Details anzeigen'}
            >
              {expanded ? <CaretUp size={20} /> : <CaretDown size={20} />}
            </button>
          )}
        </div>
        {expanded && description && <p className="confirmation-card__description">{description}</p>}
        {expanded && details.length > 0 && (
          <span className="confirmation-card__details">{details.join(' · ')}</span>
        )}
      </div>

      {reason && <p className="confirmation-card__reasoning">{reason}</p>}

      {error && <p className="confirmation-card__error">{error}</p>}

      <div className="confirmation-card__buttons">
        {interrupt.options.map((option, i) => (
          <PushButton
            key={option}
            label={option.charAt(0).toUpperCase() + option.slice(1)}
            showIcon={false}
            // Erste Option ist laut graph.py (human_review_node/
            // updated_query_node) immer die zustimmende - kein fest
            // verdrahteter String-Vergleich, reine Positionsregel.
            variant={i === 0 ? 'primary' : 'secondary'}
            disabled={submitting}
            onClick={() => handleClick(option)}
          />
        ))}
      </div>
    </div>
  )
}
