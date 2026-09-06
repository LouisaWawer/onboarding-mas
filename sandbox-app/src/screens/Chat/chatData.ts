import type { AvatarColor } from '../../components/Avatar/Avatar'
import type { StatusTone } from '../../components/StatusIndicator/StatusIndicator'

export type ChatMessage = {
  from: 'in' | 'out'
  text: string
}

export type Conversation = {
  id: string
  name: string
  isChannel?: boolean
  isLumi?: boolean
  initials?: string
  avatarColor?: AvatarColor
  presence?: StatusTone
  /** Ungelesene neue Nachricht(en) – steuert Badge in ChatListItem und Sidebar. */
  unread?: boolean
  messages: ChatMessage[]
}

/*
 * Nachrichtentexte sind Beispiel-Dialoge im dokumentierten Ton
 * (freundlich-informell, Duzkultur, siehe docs/Fiktive_Firma_und_Kollegen.md
 * und docs/Knowledge_Hub_Inhalte.md). Der genaue Wortlaut ist laut
 * docs/Szenario_Interaktionsdesign.md ("Offene Punkte") bewusst noch nicht
 * final und soll erst nach der Interviewauswertung feststehen.
 */
export const conversations: Conversation[] = [
  {
    id: 'lumi',
    name: 'Lumi',
    isLumi: true,
    presence: 'online',
    messages: [
      {
        from: 'in',
        text: 'Hallo und herzlich willkommen bei Nordlicht Software! Ich bin Lumi, dein Onboarding-Assistent. Ich helfe dir in den ersten Tagen bei allem Organisatorischen – frag mich einfach, wann immer du nicht weiterweißt.',
      },
      {
        from: 'in',
        text: 'Falls du dich erstmal umschauen möchtest: Im Kanal #allgemein sind schon ein paar Kolleg:innen unterwegs, das ist ein guter Ort, um dich vorzustellen.',
      },
      { from: 'out', text: 'Danke, das klingt gut! Womit fange ich am besten an?' },
      {
        from: 'in',
        text: 'Ich würde mit deinem VPN-Zugang starten, den brauchst du für so gut wie alles. Soll ich das für dich anstoßen?',
      },
    ],
  },
  {
    id: 'max',
    name: 'Max Vogel (IT)',
    initials: 'MV',
    avatarColor: 'avatar6',
    presence: 'online',
    unread: true,
    messages: [
      { from: 'in', text: 'Hi, hier ist Max aus dem IT-Support. Willkommen an Bord!' },
      {
        from: 'in',
        text: 'Falls du Fragen zu deinem VPN-Zugang oder anderen Systemen hast, meld dich einfach hier bei mir.',
      },
    ],
  },
  {
    id: 'anna',
    name: 'Anna Schmidt (HR)',
    initials: 'AS',
    avatarColor: 'avatar4',
    presence: 'online',
    messages: [
      {
        from: 'in',
        text: 'Hallo und herzlich willkommen bei Nordlicht Software! Schön, dass du jetzt Teil des Teams bist.',
      },
      {
        from: 'in',
        text: 'Falls du Fragen zu Urlaub, Verträgen oder generell zum Onboarding hast – ich bin für dich da.',
      },
    ],
  },
  {
    id: 'tom',
    name: 'Tom Bauer (Vertrieb)',
    initials: 'TB',
    avatarColor: 'avatar1',
    presence: 'busy',
    unread: true,
    messages: [
      { from: 'in', text: 'Hey! Ich bin Tom, dein Buddy für die ersten Wochen.' },
      {
        from: 'in',
        text: 'Lust auf einen Kaffee diese Woche? Ich häng dich auch gern in unseren kleinen Gruppenchat mit ein paar Kolleg:innen ein.',
      },
    ],
  },
  {
    id: 'laura',
    name: 'Laura Seifert (Controlling)',
    initials: 'LS',
    avatarColor: 'avatar2',
    presence: 'absent',
    messages: [{ from: 'in', text: 'Willkommen im Team! Man sieht sich sicher mal in der Kaffeeküche.' }],
  },
  {
    id: 'lars',
    name: 'Lars Becker (Marketing)',
    initials: 'LB',
    avatarColor: 'avatar5',
    presence: 'offline',
    messages: [{ from: 'in', text: 'Herzlich willkommen! Falls du mal Fragen zu unseren Kampagnen hast, meld dich gern.' }],
  },
  {
    id: 'allgemein',
    name: '#allgemein',
    isChannel: true,
    messages: [
      { from: 'in', text: 'Laura: Guten Morgen zusammen.' },
      { from: 'in', text: 'Lars: Wer hat Lust auf Kuchen später? Ich bring welchen mit.' },
      { from: 'in', text: 'Tom: Herzlich willkommen an unser neues Teammitglied!' },
    ],
  },
]
