import { useState } from 'react'
import { ArrowClockwise, Check, Copy, ThumbsDown, ThumbsUp } from '@phosphor-icons/react'
import { formatRelativeTime } from '../../utils/formatTime'
import './LumiMessageIcons.css'

type LumiMessageIconsProps = {
  message: string
  receivedAt: number
}

/**
 * Icon-Zeile unter jeder Lumi-Nachricht (Figma: "LumiMessageIcons").
 * NUR Kopieren ist funktionsfähig (siehe Auftrag). Daumen hoch/runter und
 * "Neu generieren" sind sichtbar, aber deaktiviert - der Feedback-Endpunkt
 * existiert im Backend nicht (separat nachgebaut, siehe Bericht an die
 * Nutzerin von vor zwei Nachrichten), "Neu generieren" steht im Backlog
 * (würde den an der alten Nachricht hängenden pending_action ungültig
 * machen). Deaktiviert heißt sichtbar+nicht klickbar, nicht ausgeblendet -
 * Testpersonen sollen sehen, dass es die Funktionen gibt.
 */
export default function LumiMessageIcons({ message, receivedAt }: LumiMessageIconsProps) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(message)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch (err) {
      console.error('[lumi-message-icons] Kopieren fehlgeschlagen', err)
    }
  }

  return (
    <div className="lumi-message-icons">
      <button type="button" className="lumi-message-icons__icon" title="Kopieren" onClick={handleCopy}>
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </button>
      <button type="button" className="lumi-message-icons__icon" title="Hilfreich" disabled>
        <ThumbsUp size={14} />
      </button>
      <button type="button" className="lumi-message-icons__icon" title="Nicht hilfreich" disabled>
        <ThumbsDown size={14} />
      </button>
      <button type="button" className="lumi-message-icons__icon" title="Neu generieren" disabled>
        <ArrowClockwise size={14} />
      </button>
      <span className="lumi-message-icons__timestamp">{formatRelativeTime(receivedAt)}</span>
    </div>
  )
}
