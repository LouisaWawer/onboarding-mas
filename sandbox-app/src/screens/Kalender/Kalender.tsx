import { useState } from 'react'
import { CaretLeft, CaretRight } from '@phosphor-icons/react'
import PushButton from '../../components/PushButton/PushButton'
import { useSendToLumi } from '../../state/ChatState'
import { WEEKDAYS, HOURS, initialAppointments } from './kalenderData'
import './Kalender.css'

const MONTH_NAMES = [
  'Januar',
  'Februar',
  'März',
  'April',
  'Mai',
  'Juni',
  'Juli',
  'August',
  'September',
  'Oktober',
  'November',
  'Dezember',
]

function addDays(date: Date, days: number) {
  const next = new Date(date)
  next.setDate(date.getDate() + days)
  return next
}

/**
 * Entspricht Figmas Kalender-Screen (node 6:77): Wochenansicht Mo–Fr,
 * Stunden 08–16, ein bestehender Termin ("Welcome Meeting", Montag 09:00).
 * Nutzt echte Date-Arithmetik statt einer reinen Zahlen-Inkrementierung,
 * damit Monats-/Jahresübergänge korrekt gerechnet werden.
 *
 * "Neue Besprechung" öffnet KEIN Formular – der Klick schickt stattdessen
 * eine Nachricht an Lumi (dieselbe Konversation wie im Chat-Screen) und
 * bleibt auf dem Kalender. Lumis (gescriptete) Antwort landet im
 * Hintergrund in der Konversation; das bestehende Ungelesen-Badge am
 * Chat-Icon übernimmt die Benachrichtigung darüber.
 */
export default function Kalender() {
  const [weekStart, setWeekStart] = useState(() => new Date(2026, 8, 21)) // Montag, 21. September 2026
  const [appointments] = useState(initialAppointments)
  const sendToLumi = useSendToLumi()

  const days = WEEKDAYS.map((label, i) => ({ label, date: addDays(weekStart, i) }))
  const weekEnd = days[days.length - 1].date
  const monthLabel =
    weekStart.getMonth() === weekEnd.getMonth()
      ? MONTH_NAMES[weekStart.getMonth()]
      : `${MONTH_NAMES[weekStart.getMonth()]} / ${MONTH_NAMES[weekEnd.getMonth()]}`

  function requestNewMeeting() {
    sendToLumi(
      'Ich möchte eine neue Besprechung planen',
      'Gerne! Damit ich das für dich einträgst: Wann soll das Meeting stattfinden, wer soll dabei sein, und hast du schon einen Raum oder ein Format (vor Ort/online) im Kopf?',
    )
  }

  return (
    <div className="kalender">
      <div className="kalender__card">
        <header className="kalender__header">
          <h1 className="kalender__title">Kalender</h1>
          <PushButton label="Neue Besprechung" onClick={requestNewMeeting} />
        </header>
        <div className="kalender__divider" />

        <div className="kalender__nav">
          <span className="kalender__month">{monthLabel}</span>
          <button
            type="button"
            className="kalender__nav-arrow"
            onClick={() => setWeekStart((d) => addDays(d, -7))}
            aria-label="Vorherige Woche"
          >
            <CaretLeft size={20} color="var(--color-text)" />
          </button>
          <button
            type="button"
            className="kalender__nav-arrow"
            onClick={() => setWeekStart((d) => addDays(d, 7))}
            aria-label="Nächste Woche"
          >
            <CaretRight size={20} color="var(--color-text)" />
          </button>
        </div>

        <div className="kalender__grid">
          <div className="kalender__corner" />
          {days.map((day) => (
            <div className="kalender__day-header" key={day.label}>
              <span className="kalender__day-number">{day.date.getDate()}</span>
              <span className="kalender__day-name">{day.label}</span>
            </div>
          ))}

          {HOURS.map((hour) => (
            <div className="kalender__hour-label" key={hour} style={{ gridRow: HOURS.indexOf(hour) + 2 }}>
              {String(hour).padStart(2, '0')}:00
            </div>
          ))}

          {HOURS.map((hour) =>
            days.map((_, dayIndex) => (
              <div
                className="kalender__cell"
                key={`${hour}-${dayIndex}`}
                style={{ gridRow: HOURS.indexOf(hour) + 2, gridColumn: dayIndex + 2 }}
              />
            )),
          )}

          {appointments.map((a) => (
            <div
              className="kalender__appointment"
              key={a.id}
              style={{ gridRow: HOURS.indexOf(a.hour) + 2, gridColumn: a.day + 2 }}
            >
              <p className="kalender__appointment-title">{a.title}</p>
              <p className="kalender__appointment-location">{a.location}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
