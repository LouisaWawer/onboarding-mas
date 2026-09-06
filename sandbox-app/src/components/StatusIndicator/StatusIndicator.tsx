import type { FunctionComponent, SVGProps } from 'react'
import IconOnline from '../../assets/icons/state=online.svg?react'
import IconAbsent from '../../assets/icons/state=absent.svg?react'
import IconBusy from '../../assets/icons/state=busy.svg?react'
import IconOffline from '../../assets/icons/state=offline.svg?react'
import './StatusIndicator.css'

/** Deckt exakt die vier Varianten der Figma-Komponente "Status" (node 34:671) ab. */
export type PresenceTone = 'online' | 'absent' | 'busy' | 'offline'
export type StatusTone = PresenceTone | 'processing'

type StatusIndicatorProps = {
  status: StatusTone
  /** Feste Größe unabhängig von der Avatar-Größe, in der der Punkt sitzt. */
  size?: number
  className?: string
}

/*
 * Aus Figma exportierte Original-SVGs (src/assets/icons/state=*.svg), als
 * React-Komponenten importiert (vite-plugin-svgr, "?react"-Suffix) statt
 * als statische Bild-Referenzen – Farbe/Größe bleiben dadurch per Props/
 * CSS steuerbar. "offline" hat abweichend von den anderen drei ein
 * eigenes viewBox (14x14 statt 12x12, hohler Kreis + X statt gefüllter
 * Kreis + Icon) – exakt wie im Original, die feste 12px-Größe wird unten
 * per width/height-Prop erzwungen.
 */
const PRESENCE_ICON: Record<PresenceTone, FunctionComponent<SVGProps<SVGSVGElement>>> = {
  online: IconOnline,
  absent: IconAbsent,
  busy: IconBusy,
  offline: IconOffline,
}

export default function StatusIndicator({ status, size = 12, className }: StatusIndicatorProps) {
  if (status === 'processing') {
    // Kein Zustand der Figma-Komponente "Status", sondern der
    // "assistant"-Zustand von StatusLight/TaskStatus (Tickets) – dort
    // reine Farbfläche ohne Icon.
    return (
      <span
        className={`status-indicator ${className ?? ''}`}
        style={{ width: size, height: size, backgroundColor: 'var(--color-assistant-soft)' }}
        role="status"
        aria-label={status}
      />
    )
  }

  const Icon = PRESENCE_ICON[status]
  return (
    <Icon
      width={size}
      height={size}
      className={`status-indicator ${className ?? ''}`}
      role="status"
      aria-label={status}
    />
  )
}
