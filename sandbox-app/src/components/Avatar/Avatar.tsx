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
  /** Initialen menschlicher Kolleg:innen - Lumi läuft seit Schritt 5 über
      LumiAvatar (lumiwithsparklesmall.riv), nicht mehr über diese
      Komponente (siehe Bericht an die Nutzerin: der frühere icon="lumi"-
      Zweig mit statischem Sparkle-Icon ist entfernt, kein Aufrufer nutzt
      ihn mehr). */
  initials?: string
  color?: AvatarColor
  size?: number
  className?: string
}

export default function Avatar({ initials = '', color = 'avatar1', size = 24, className }: AvatarProps) {
  return (
    <div
      className={`avatar ${className ?? ''}`}
      style={{ width: size, height: size, backgroundColor: `var(--color-${color})` }}
    >
      <span className="avatar__initials" style={{ fontSize: Math.round(size * 0.42) }}>
        {initials}
      </span>
    </div>
  )
}
