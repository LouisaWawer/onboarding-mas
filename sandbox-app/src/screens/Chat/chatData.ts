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
/*
 * Die frühere 'lumi'-Konversation (feste, gescriptete Antworten) lebt hier
 * nicht mehr - Lumi/der Agent wird ab der Frontend-Anbindung über
 * state/AgentState.tsx aus dem echten Backend gespeist, nicht mehr aus
 * diesem Mock. Diese Datei enthält jetzt nur noch die weiterhin bewusst
 * gescripteten Kolleg:innen-Chats/Kanäle (siehe Szenario_Interaktionsdesign.md
 * §2: "Feste, vorgeschriebene Kolleg:innen-Nachrichten statt vollständiger
 * Multi-User-Simulation").
 */
export const conversations: Conversation[] = [
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
