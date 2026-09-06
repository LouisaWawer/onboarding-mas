# Komponenten

Geteilte, wiederverwendbare UI-Bausteine, gebaut aus der Figma-Elements-Bibliothek (`node-id=10-22`). Nutzen ausschließlich Tokens aus `src/styles/colors.css`, keine hartcodierten Hex-Werte. Barrel-Export in `index.ts`.

| Komponente | Zweck |
|---|---|
| [`Topbar`](#topbar) | App-weite Kopfzeile (Fensterknöpfe, Suche, Mehr-Menü, eigener Avatar) |
| [`Sidebar`](#sidebar) | App-weite Hauptnavigation (5 Bereiche) |
| [`SidebarIcon`](#sidebaricon) | Einzelnes Sidebar-Icon mit Zustand + Badge |
| [`Avatar`](#avatar) | Rundes Profilbild – Initialen oder Lumi-Sparkle |
| [`StatusIndicator`](#statusindicator) | Präsenz-/Status-Punkt (online/absent/busy/offline + processing) |
| [`UserWithStatus`](#userwithstatus) | Avatar + StatusIndicator kombiniert |
| [`ChatListItem`](#chatlistitem) | Zeile in der Chat-Kontaktliste |
| [`MessageBox`](#messagebox) | Eine Nachricht im Chatverlauf (in/out) |
| [`Tree`](#tree) | Rekursive Baumnavigation (Knowledge Hub) |
| [`PreviewBlock`](#previewblock) | Artikel-Vorschau (Liste oder Kachel) |
| [`Filter`](#filter) | Filter-Chip mit Zuständen |
| [`PushButton`](#pushbutton) | Primärer Aktions-Button |
| [`TaskStatus`](#taskstatus) | Status-Punkt + Label für Tickets (open/processing/done/error) |

---

## Topbar

`components/Topbar/Topbar.tsx`

Kopfzeile über Sidebar + Screen, auf jedem Bereich vorhanden (Figma node 35:855). Fenster-Steuerelemente links (rein dekorativ, echte macOS-Farben statt App-Tokens), Suche mittig (Näherung an Figmas „Liquid Glass"-Effekt), Mehr-Menü + eigener Avatar rechts (Initialen „DU", `color/accent` statt einer Avatar-Farbe – die Testperson bleibt bewusst unbenannt). Keine Props, wird einmal in `App.tsx` gerendert.

## Sidebar

`components/Sidebar/Sidebar.tsx`

App-weite Navigation links (Chat/Intranet/Knowledge Hub/Tickets/Kalender). Logo als statisches Asset (`assets/icons/Logo.svg`, 1:1 aus Figma node 33:572 exportiert, enthält eingebettetes Raster – daher als `<img>` statt React-Komponente eingebunden). Rendert pro Eintrag ein `SidebarIcon`, trackt Hover lokal.

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `active` | `SidebarItemId` (`'chat' \| 'intranet' \| 'hub' \| 'tickets' \| 'calendar'`) | – | aktuell aktiver Bereich |
| `onNavigate` | `(id: SidebarItemId) => void` | – | Callback bei Klick auf ein Icon |
| `badges` | `Partial<Record<SidebarItemId, boolean>>` | – | welche Bereiche einen Benachrichtigungspunkt zeigen (aus echtem App-Zustand, siehe Vorschlag im Chat) |

## SidebarIcon

`components/Sidebar/SidebarIcon.tsx`

Einzelnes Icon der Sidebar. Nutzt `@phosphor-icons/react` statt der Figma-Exporte (`assets/icons/{chat,intranet,knowledgehub,ticket,calendar}.svg`, liegen weiterhin im Projekt, werden aber nicht mehr importiert) – die Figma-Pfade sind als volle Fläche gezeichnet, ein sauberes Outline/Fill-Paar ließ sich daraus nicht per CSS herleiten. Kein Hintergrund in irgendeinem Zustand: `default` = `weight="regular"` (Kontur), `hover`/`active` = `weight="fill"`, immer in `--color-accent`.

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `app` | `SidebarApp` (`'chat' \| 'intranet' \| 'hub' \| 'tickets' \| 'calendar'`) | – | welches Icon |
| `state` | `'default' \| 'hover' \| 'active'` | `'default'` | visueller Zustand |
| `hasBadge` | `boolean` | `false` | Benachrichtigungspunkt anzeigen |
| `label` | `string` | – | Tooltip/aria-Label |
| `onClick` | `() => void` | – | Klick-Handler |

## Avatar

`components/Avatar/Avatar.tsx`

Rundes Profilbild. `icon="lumi"` zeigt ein Sparkle-Icon (Onboarding-Assistent) statt Initialen – Unterscheidung Mensch/Agent erfolgt nur über das Icon, nicht über die Form (beide rund).

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `icon` | `'initials' \| 'lumi'` | `'initials'` | Inhalt des Avatars |
| `initials` | `string` | `''` | nur bei `icon="initials"` |
| `color` | `AvatarColor` (`'avatar1'`…`'avatar6'`) | `'avatar1'` | Figma-Avatarfarbe, nur bei `icon="initials"` |
| `size` | `number` | `24` | Kantenlänge in px |
| `className` | `string` | – | zusätzliche Klasse |

## StatusIndicator

`components/StatusIndicator/StatusIndicator.tsx`

Bildet die Figma-Komponente „Status" (node 34:671) 1:1 nach: vier aus Figma exportierte SVGs (`src/assets/icons/state=*.svg`, per `vite-plugin-svgr` als React-Komponenten importiert), je mit eigenem Icon (Check/Clock-Icon/reine Fläche/X). `processing` ist kein Figma-„Status"-Zustand, sondern der „assistant"-Zustand von StatusLight/TaskStatus (Tickets) – reine Farbfläche ohne Icon.

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `status` | `StatusTone` (`'online' \| 'absent' \| 'busy' \| 'offline' \| 'processing'`) | – | Zustand |
| `size` | `number` | `12` | Kantenlänge in px (fix, unabhängig vom Avatar) |
| `className` | `string` | – | zusätzliche Klasse |

## UserWithStatus

`components/UserWithStatus/UserWithStatus.tsx`

Kombination aus `Avatar` + `StatusIndicator`, entspricht Figmas eigenem „UserWithStatus"-Baustein (node 45:7075): Flex-Row, Avatar zieht per negativem rechtem Margin unter den (immer 12px großen) Status-Punkt statt absoluter Positionierung.

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `avatarSize` | `number` | – | Kantenlänge des Avatars in px |
| `initials` | `string` | – | siehe `Avatar` |
| `avatarColor` | `AvatarColor` | – | siehe `Avatar` |
| `isLumi` | `boolean` | – | rendert Lumi-Avatar statt Initialen |
| `presence` | `StatusTone` | – | blendet `StatusIndicator` ein; ohne Angabe kein Punkt |
| `className` | `string` | – | zusätzliche Klasse |

## ChatListItem

`components/ChatListItem/ChatListItem.tsx`

Eine Zeile in der Chat-Kontakt-/Kanalliste: Avatar+Status, Name, Zeit, Vorschautext, ungelesen-Badge.

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `name` | `string` | – | Anzeigename |
| `preview` | `string` | – | letzte Nachricht als Vorschau |
| `time` | `string` | – | optional, z.B. „9:34" |
| `initials` | `string` | – | siehe `Avatar` |
| `avatarColor` | `AvatarColor` | `'avatar1'` | siehe `Avatar` |
| `isLumi` | `boolean` | `false` | siehe `Avatar` |
| `presence` | `StatusTone` | – | siehe `StatusIndicator` |
| `unread` | `boolean` | `false` | zeigt Ungelesen-Badge |
| `active` | `boolean` | `false` | hervorgehobener/ausgewählter Zustand |
| `onClick` | `() => void` | – | Klick-Handler |

## MessageBox

`components/MessageBox/MessageBox.tsx`

Eine einzelne Nachricht im Chatverlauf. `from="out"` = eigene Nachricht (rechtsbündig, Akzentfarbe, kein Avatar); `from="in"` = Gegenüber (linksbündig, mit Avatar).

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `message` | `string` | – | Nachrichtentext |
| `from` | `'in' \| 'out'` | `'in'` | Richtung |
| `senderName` | `string` | – | Name über der Nachricht (nur `from="in"`) |
| `showSender` | `boolean` | `true` | Name/Avatar anzeigen (`false` bei Folgenachrichten derselben Person, hält aber die Avatar-Spaltenbreite frei) |
| `avatarColor` | `AvatarColor` | `'avatar1'` | siehe `Avatar` |
| `initials` | `string` | – | siehe `Avatar` |
| `isLumi` | `boolean` | `false` | siehe `Avatar` |
| `presence` | `StatusTone` | – | siehe `StatusIndicator` |

## Tree

`components/Tree/Tree.tsx`

Rekursive, einklappbare Baumnavigation für den Knowledge Hub (z.B. HR → Abwesenheit → Urlaub). Ausgewählter Knoten wird in Akzentfarbe hervorgehoben.

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `nodes` | `TreeNode[]` (`{ id: string; label: string; kind: 'folder' \| 'file'; children?: TreeNode[] }`) | – | Baumstruktur (Wurzelebene). `kind` explizit statt aus `children` abgeleitet, da manche Ordner (noch) keine Kinder haben |
| `selectedId` | `string` | – | id des aktuell ausgewählten Knotens |
| `onSelect` | `(id: string) => void` | – | Callback bei Klick auf einen Knoten |

## PreviewBlock

`components/PreviewBlock/PreviewBlock.tsx`

Artikel-Vorschau im Knowledge Hub. `variant="default"` = Listenzeile (Landing/gefiltert), `variant="card"` = zentrierte Kachel (Detailseite, verwandte Artikel).

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `headline` | `string` | – | Artikeltitel |
| `path` | `string` | – | Breadcrumb, z.B. „HR · Abwesenheit · Urlaub" |
| `content` | `string` | – | Textauszug |
| `variant` | `'default' \| 'card'` | `'default'` | Darstellungsform |
| `onClick` | `() => void` | – | Klick-Handler |

## Filter

`components/Filter/Filter.tsx`

Filter-Chip (z.B. Tickets-Status-Filter). `importance="high"` hebt den Chip mit Fehlerfarbe hervor (dringend/ungelöst).

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `label` | `string` | – | Beschriftung |
| `active` | `boolean` | `false` | ausgewählter Zustand |
| `importance` | `'normal' \| 'high'` | `'normal'` | visuelle Dringlichkeit |
| `onClick` | `() => void` | – | Klick-Handler |

## PushButton

`components/PushButton/PushButton.tsx`

Primärer Aktions-Button in Akzentfarbe (z.B. „Neue Besprechung", „Ticket erstellen"). Hover/Press werden per CSS aus `--color-accent` + Overlay-Tönung gemischt (siehe `colors.css`), nicht als eigene Zustands-Prop.

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `label` | `string` | – | Beschriftung |
| `showIcon` | `boolean` | `true` | Plus-Icon ein-/ausblenden |
| `type` | `'button' \| 'submit'` | `'button'` | HTML-Button-Typ |
| `onClick` | `() => void` | – | Klick-Handler |

## TaskStatus

`components/TaskStatus/TaskStatus.tsx`

Farb-Punkt + Label für Ticket-/Aufgaben-Status (Figma „TaskStatus"/„StatusLight", node 45:6653/44:6598) – eigenständig von `StatusIndicator` (Präsenz), da andere Zustände/Farben (kräftige Variante: `--color-success/warning/danger` + `--color-assistant-soft`).

| Prop | Typ | Default | Beschreibung |
|---|---|---|---|
| `state` | `'open' \| 'processing' \| 'done' \| 'error'` | – | Zustand (Label + Farbe fest zugeordnet: Offen/in Bearbeitung/Erledigt/Support kontaktieren) |
| `className` | `string` | – | zusätzliche Klasse |
