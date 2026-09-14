import type { AvatarColor } from '../../components/Avatar/Avatar'

export type TabId = 'ankuendigungen' | 'verzeichnis' | 'neu-im-team' | 'ueber-uns'

export const TABS: { id: TabId; label: string }[] = [
  { id: 'ankuendigungen', label: 'Ankündigungen' },
  { id: 'verzeichnis', label: 'Mitarbeitendenverzeichnis' },
  { id: 'neu-im-team', label: 'Neu im Team' },
  { id: 'ueber-uns', label: 'Über uns' },
]

export type Announcement = {
  id: string
  title: string
  author: string
  date: string
  body: string
  isNew?: boolean
}

/* 1:1 aus docs/Intranet_Inhalte.md übernommen (deckt sich mit Figma, node 69:9822). */
export const announcements: Announcement[] = [
  {
    id: 'sommerfest',
    title: 'Save the Date: Sommerfest am 15. September',
    author: 'Anna Schmidt',
    date: 'vor 2 Tagen',
    isNew: true,
    body: `Dieses Jahr feiern wir wieder gemeinsam – diesmal mit Live-Musik und Grill auf der Dachterrasse. Los geht's ab 16 Uhr, für Essen und Getränke ist gesorgt. Bringt gerne auch eure Partner:innen oder Kinder mit, das Fest ist bewusst für die ganze Familie gedacht.

Eine kurze Anmeldung hilft uns bei der Planung – ihr bekommt dazu in den nächsten Tagen ein Ticket im HR-Bereich, über das ihr euch anmelden könnt.

Wir freuen uns auf einen entspannten Nachmittag mit euch!`,
  },
  {
    id: 'wartungsfenster',
    title: 'IT-Wartungsfenster am kommenden Wochenende',
    author: 'Max Vogel',
    date: 'vor 4 Tagen',
    body: `Am Samstag zwischen 8 und 12 Uhr führen wir geplante Wartungsarbeiten an unseren internen Systemen durch. In dieser Zeit können VPN, interne Tools und das Ticket-System eingeschränkt erreichbar sein.

Was ihr tun solltet:
– Wichtige Arbeiten möglichst vor Freitagabend abschließen
– Laufende Downloads/Uploads rechtzeitig fertigstellen
– Bei dringenden Problemen während des Fensters: kurze Geduld, wir sind im Anschluss sofort wieder erreichbar

Bei Fragen meldet euch gerne direkt bei mir im Chat.`,
  },
  {
    id: 'kaffeemaschine',
    title: 'Neue Kaffeemaschine im 3. Stock',
    author: 'Tom Bauer',
    date: 'vor 6 Tagen',
    body: `Ab sofort steht euch im 3. Stock eine neue Kaffeemaschine zur Verfügung – inklusive Hafermilch-Option und deutlich weniger Wartezeit in der Schlange morgens. Ein großes Dankeschön an alle, die die alte Maschine so tapfer am Laufen gehalten haben.

Kurze Einweisung gibt's bei mir, falls die neuen Knöpfe am Anfang verwirren – ich hab am ersten Tag auch dreimal den falschen Knopf gedrückt.`,
  },
]

export type DirectoryEntry = {
  id: string
  name: string
  role: string
  initials?: string
  avatarColor?: AvatarColor
  isLumi?: boolean
}

/*
 * 1:1 aus docs/Fiktive_Firma_und_Kollegen.md. Tom Bauers Eintrag zeigt
 * weiterhin die veraltete Rolle "Marketing" statt "Vertrieb, Buddy" - das
 * "Angaben nicht aktuell? Melden"-Override dafür ist entfernt (nicht im
 * Studienskript vorgesehen, siehe Bericht an die Nutzerin), die veraltete
 * Rolle selbst bleibt unangetastet stehen (kein inhaltlicher Fehler, nur
 * der Melde-Mechanismus dafür ist weg).
 */
export const directory: DirectoryEntry[] = [
  { id: 'max', name: 'Max Vogel', role: 'IT Support', initials: 'MV', avatarColor: 'avatar6' },
  { id: 'anna', name: 'Anna Schmidt', role: 'HR Business Partnerin', initials: 'AS', avatarColor: 'avatar4' },
  { id: 'laura', name: 'Laura Seifert', role: 'Controlling', initials: 'LS', avatarColor: 'avatar2' },
  { id: 'tom', name: 'Tom Bauer', role: 'Marketing', initials: 'TB', avatarColor: 'avatar1' },
  { id: 'lars', name: 'Lars Becker', role: 'Marketing', initials: 'LB', avatarColor: 'avatar5' },
  { id: 'lumi', name: 'Lumi', role: 'Onboarding-Assistent', isLumi: true },
]

export const company = {
  name: 'Nordlicht Software GmbH',
  description:
    'Nordlicht Software entwickelt Planungstools, mit denen mittelständische Unternehmen ihre Projekte und Teams einfacher organisieren. Wir sind ca. 140 Kolleg:innen, verteilt auf Produktentwicklung, Vertrieb, Customer Success und die üblichen Querschnittsfunktionen.',
  facts: [
    { label: 'Branche', value: 'B2B-Software (Projekt- und Ressourcenplanung für mittelständische Unternehmen)' },
    { label: 'Größe', value: 'ca. 140 Mitarbeitende' },
    { label: 'Standort', value: 'Hamburg, hybrides Arbeiten üblich' },
  ],
}
