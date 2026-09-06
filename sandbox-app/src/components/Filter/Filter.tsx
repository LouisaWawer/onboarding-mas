import './Filter.css'

type FilterProps = {
  label: string
  active?: boolean
  /** high = dringend/ungelöst, hebt sich mit Fehlerfarbe ab (z.B. Tickets) */
  importance?: 'normal' | 'high'
  onClick?: () => void
}

export default function Filter({ label, active = false, importance = 'normal', onClick }: FilterProps) {
  return (
    <button
      type="button"
      className={`filter ${active ? 'filter--active' : ''} ${importance === 'high' ? 'filter--high' : ''}`}
      aria-pressed={active}
      onClick={onClick}
    >
      {label}
    </button>
  )
}
