import { X } from '@phosphor-icons/react'
import './OptionsCard.css'

export type OptionsCardOption = {
  label: string
  onClick: () => void
}

type OptionsCardProps = {
  title: string
  options: OptionsCardOption[]
  onClose: () => void
}

/**
 * Generischer Layoutbaustein für die Figma-Variante "ConfirmationCard,
 * type=options" (node 219:4794/219:4795, default/hover) - Titel + eine
 * nummerierte Optionsliste + Schließen (X). Kennt NICHTS von Vorschlägen,
 * Screens oder Backend-Formen - der Aufrufer entscheidet, was `label`
 * bedeutet und was ein Klick auslöst (siehe Bericht an die Nutzerin,
 * Schritt 6: aktuell für den proaktiven Screenwechsel-Vorschlag genutzt,
 * LumiConversation.tsx). Die zweite, im Backlog stehende Verwendung
 * derselben Design-Variante (Lumi fragt beim Erkennen mehrerer
 * Teilschritte, womit begonnen werden soll - neuer Graph-Knoten, neuer
 * Interrupt-Typ, JETZT NICHT gebaut) kann diesen Baustein später ohne
 * Änderung hier wiederverwenden, solange ihre Daten sich auf
 * title+options abbilden lassen.
 *
 * "Etwas anderes" bewusst NICHT gebaut (siehe Bericht an die Nutzerin) -
 * die Person kann jederzeit frei in den Composer tippen, dafür braucht es
 * keine eigene Option in der Karte.
 */
export default function OptionsCard({ title, options, onClose }: OptionsCardProps) {
  return (
    <div className="options-card">
      <div className="options-card__header">
        <span className="options-card__title">{title}</span>
        <button type="button" className="options-card__close" onClick={onClose} aria-label="Schließen">
          <X size={20} />
        </button>
      </div>
      <div className="options-card__options">
        {options.map((option, i) => (
          <button key={option.label} type="button" className="options-card__option" onClick={option.onClick}>
            <span className="options-card__option-number">{i + 1}</span>
            <span className="options-card__option-label">{option.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
