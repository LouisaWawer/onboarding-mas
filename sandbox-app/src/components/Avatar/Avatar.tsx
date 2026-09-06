import { Sparkle } from '@phosphor-icons/react'
import './Avatar.css'

export type AvatarColor =
  | 'avatar1'
  | 'avatar2'
  | 'avatar3'
  | 'avatar4'
  | 'avatar5'
  | 'avatar6'
  /** für den Topbar-"DU"-Avatar (Figma nutzt dort color/accent statt einer Avatar-Farbe) */
  | 'accent'

type AvatarProps = {
  /** initials = menschliche Kolleg:innen, lumi = Onboarding-Assistent */
  icon?: 'initials' | 'lumi'
  /** Initialen, nur bei icon="initials" relevant */
  initials?: string
  /** Figma-Avatarfarbe (avatar1–avatar6), nur bei icon="initials" relevant */
  color?: AvatarColor
  size?: number
  className?: string
}

/**
 * Lumi ist genauso rund wie die Personen-Avatare – die Unterscheidung
 * Mensch/Agent erfolgt allein über das Funken-Symbol, nicht über die Form
 * (siehe docs/Fiktive_Firma_und_Kollegen.md).
 */
export default function Avatar({
  icon = 'initials',
  initials = '',
  color = 'avatar1',
  size = 24,
  className,
}: AvatarProps) {
  const isLumi = icon === 'lumi'
  return (
    <div
      className={`avatar ${className ?? ''}`}
      style={{
        width: size,
        height: size,
        backgroundColor: isLumi ? 'var(--color-assistant)' : `var(--color-${color})`,
      }}
    >
      {isLumi ? (
        <Sparkle size={Math.round(size * 0.6)} color="var(--color-overlay)" weight="fill" />
      ) : (
        <span className="avatar__initials" style={{ fontSize: Math.round(size * 0.42) }}>
          {initials}
        </span>
      )}
    </div>
  )
}
