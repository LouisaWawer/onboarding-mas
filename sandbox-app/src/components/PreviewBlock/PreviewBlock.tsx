import { File } from '@phosphor-icons/react'
import './PreviewBlock.css'

type PreviewBlockProps = {
  headline: string
  path: string
  content: string
  /** default = Listenzeile (Knowledge Hub Landing/gefiltert), card = Kachel (Detail-Verweis) */
  variant?: 'default' | 'card'
  onClick?: () => void
}

export default function PreviewBlock({
  headline,
  path,
  content,
  variant = 'default',
  onClick,
}: PreviewBlockProps) {
  const isCard = variant === 'card'
  return (
    <button
      type="button"
      className={`preview-block ${isCard ? 'preview-block--card' : 'preview-block--default'}`}
      onClick={onClick}
    >
      <File size={24} color="var(--color-text)" />
      <span className={`preview-block__text ${isCard ? 'preview-block__text--center' : ''}`}>
        <span className="preview-block__headline">{headline}</span>
        <span className="preview-block__path">{path}</span>
        <span className="preview-block__content">{content}</span>
      </span>
    </button>
  )
}
