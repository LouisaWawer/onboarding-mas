import { Plus } from '@phosphor-icons/react'
import './PushButton.css'

type PushButtonProps = {
  label: string
  /** Icon ausblenden, z.B. für reine Text-Buttons ohne "Neu"-Aktion */
  showIcon?: boolean
  type?: 'button' | 'submit'
  onClick?: () => void
}

export default function PushButton({ label, showIcon = true, type = 'button', onClick }: PushButtonProps) {
  return (
    <button type={type} className="push-button" onClick={onClick}>
      {showIcon && <Plus size={17.5} color="var(--color-overlay)" weight="bold" />}
      <span>{label}</span>
    </button>
  )
}
