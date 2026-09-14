import { useState } from 'react'
import { CaretDown, CaretRight } from '@phosphor-icons/react'
import type { Rationale } from '../../api/client'
import './RationaleBlock.css'

type RationaleBlockProps = {
  rationale: Rationale | null
}

/**
 * Transparenzblock ("N Schritte") unter einer Assistant-Nachricht - eigene,
 * kleine Komponente statt Wiederverwendung der bestehenden Section-Header
 * in Chat.tsx (siehe Bericht an die Nutzerin: lohnt sich erst, wenn eine
 * echte Anfragen-Liste dieselbe Kopfzeilen-Optik braucht).
 *
 * rationale===null ODER steps.length===0 rendert GAR NICHTS - kein "0
 * Schritte"-Block. Beide Fälle bedeuten "für diese Nachricht gibt es keine
 * Rationale" (transparency_level erlaubt keine, oder der Knoten hat schlicht
 * nichts beigetragen), keinen leeren, aber sichtbaren Block.
 */
export default function RationaleBlock({ rationale }: RationaleBlockProps) {
  const [expanded, setExpanded] = useState(false)

  if (!rationale || rationale.steps.length === 0) return null

  const count = rationale.steps.length
  const headline = count === 1 ? '1 Schritt' : `${count} Schritte`

  return (
    <div className="rationale-block">
      <button
        type="button"
        className="rationale-block__header"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
      >
        {/* Figma-Varianten rightUp/rightDown: zugeklappt zeigt der Pfeil
            nach RECHTS, aufgeklappt nach UNTEN - nicht nach oben. */}
        {expanded ? <CaretDown size={14} /> : <CaretRight size={14} />}
        <span>{headline}</span>
      </button>
      {expanded && (
        <ul className="rationale-block__list">
          {rationale.steps.map((step, i) => (
            <li className="rationale-block__step" key={i}>
              <span className="rationale-block__label">{step.label}</span>
              {step.detail && <span className="rationale-block__detail">{step.detail}</span>}
              {step.source?.title && (
                <span className="rationale-block__source">Quelle: {step.source.title}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
