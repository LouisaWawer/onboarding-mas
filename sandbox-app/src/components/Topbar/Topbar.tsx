import { MagnifyingGlass, DotsThree } from '@phosphor-icons/react'
import UserWithStatus from '../UserWithStatus/UserWithStatus'
import './Topbar.css'

/**
 * Entspricht Figmas "Topbar" (node 35:855), auf jedem Screen vorhanden:
 * Fenster-Steuerelemente links (macOS-Traffic-Lights, rein dekorativ –
 * echte OS-native Farben, bewusst außerhalb des App-Farbsystems), Suche
 * mittig (Figma: "Liquid Glass"/Frost-Effekt, hier als CSS-Näherung),
 * Mehr-Menü + eigener Avatar rechts ("DU", in color/accent statt einer
 * Avatar-Farbe – die Testperson hat bewusst keine eigene Identität, siehe
 * docs/Fiktive_Firma_und_Kollegen.md).
 */
export default function Topbar() {
  return (
    <header className="topbar">
      <div className="topbar__window-controls" aria-hidden="true">
        <span className="topbar__dot topbar__dot--close" />
        <span className="topbar__dot topbar__dot--minimize" />
        <span className="topbar__dot topbar__dot--zoom" />
      </div>
      <div className="topbar__search">
        <MagnifyingGlass size={16} color="var(--color-faded)" />
        <input type="text" placeholder="Suche" aria-label="Suchen" />
      </div>
      <div className="topbar__end">
        <button type="button" className="topbar__more" title="Mehr" aria-label="Mehr">
          <DotsThree size={20} color="var(--color-text)" weight="bold" />
        </button>
        <UserWithStatus avatarSize={24} initials="DU" avatarColor="accent" presence="online" />
      </div>
    </header>
  )
}
