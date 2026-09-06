import type { TreeNode } from '../../components/Tree/Tree'

/*
 * Baumstruktur 1:1 aus Figma (Linktree, node 54:8018) übernommen. `kind`
 * ist explizit gesetzt statt aus `children` abgeleitet: einige Ordner
 * (z.B. "Dienstreise", "Krankheit", "Vergütung & Benefits") zeigen in
 * Figma ein Ordner-Icon, obwohl in diesem Prototyp (noch) keine Kinder
 * hinterlegt sind.
 */
export const tree: TreeNode[] = [
  { 
    id: 'allgemein', 
    label: 'Allgemein', 
    kind: 'folder',
  children: [
    {
    id: 'onboarding',
    label: 'Onboarding',
    kind: 'folder',
    children: [{ id: 'willkommensguide', label: 'Willkommensguide', kind: 'file' }],
  },
],
  },
  {
    id: 'hr',
    label: 'HR',
    kind: 'folder',
    children: [
      {
        id: 'abwesenheit',
        label: 'Abwesenheit',
        kind: 'folder',
        children: [
          { id: 'dienstreise', label: 'Dienstreise', kind: 'folder' },
          {
            id: 'urlaub',
            label: 'Urlaub',
            kind: 'folder',
            children: [
              { id: 'urlaub-beantragen', label: 'Urlaub beantragen', kind: 'file' },
              { id: 'sonderurlaubsregelung', label: 'Sonderurlaubsregelung', kind: 'file' },
              { id: 'sonderurlaub-beantragen', label: 'Sonderurlaub beantragen', kind: 'file' },
            ],
          },
          { id: 'krankheit', label: 'Krankheit', kind: 'folder' },
        ],
      },
      { id: 'verguetung-benefits', label: 'Vergütung & Benefits', kind: 'folder' },
    ],
  },
  {
    id: 'it',
    label: 'IT',
    kind: 'folder',
    children: [
      {
        id: 'remote-arbeiten',
        label: 'Remote Arbeiten',
        kind: 'folder',
        children: [{ id: 'remote-guidelines', label: 'Remote Guidelines', kind: 'file' }],
      },
      {
        id: 'vpn',
        label: 'VPN',
        kind: 'folder',
        children: [
          { id: 'vpn-zugang-beantragen', label: 'VPN Zugang beantragen', kind: 'file' },
          { id: 'vpn-zugang-einrichten', label: 'VPN Zugang einrichten', kind: 'file' },
        ],
      },
    ],
  },
]

export type Article = {
  id: string
  headline: string
  path: string
  /** Breadcrumb-Anzeige über der Artikel-/Filteransicht, z.B. "HR / Abwesenheit" */
  breadcrumb: string
  /** Kurztext für die Vorschau-Listen (Landing/gefiltert) */
  preview: string
  /** Vollständiger Artikelkörper für die Detailansicht, falls vorhanden */
  body?: string
  meta?: string
  isNew?: boolean
}

/*
 * "Urlaub beantragen" ist der einzige Artikel mit vollständigem Inhalt aus
 * docs/Knowledge_Hub_Inhalte.md. "Sonderurlaubsregelung" und "Sonderurlaub
 * beantragen" sind echte Kurztexte direkt aus Figma (PreviewBlock-Inhalte,
 * node 51:7682) übernommen – dort gibt es keinen längeren Artikelkörper,
 * die Kurzfassung dient hier auch als Detailtext.
 */
export const articles: Record<string, Article> = {
  'urlaub-beantragen': {
    id: 'urlaub-beantragen',
    headline: 'Urlaub beantragen',
    path: 'HR · Abwesenheit · Urlaub',
    breadcrumb: 'HR / Abwesenheit / Urlaub',
    preview: 'Hier erfährst du, wie du deinen Urlaub beantragst.',
    meta: 'Zuletzt aktualisiert vor 3 Tagen von Anna Schmidt (HR)',
    body: `Hier erfährst du, wie du deinen Urlaub beantragst.

So gehst du vor
1. Öffne die Tickets-App und erstelle ein neues Ticket an HR.
2. Trag deinen gewünschten Zeitraum ein (Start- und Enddatum).
3. Deine Teamleitung erhält automatisch eine Benachrichtigung und muss den Antrag genehmigen.
4. Nach der Genehmigung trägt sich dein Urlaub automatisch in deinen Kalender ein.

Du kannst dir die einzelnen Schritte auch von deinem Onboarding-Assistenten Lumi zeigen lassen – frag ihn einfach direkt im Chat.

Fristen
Bis zu 5 Tagen Urlaub: möglichst 1 Woche im Voraus beantragen. Längere Urlaube (mehr als 5 Tage): mindestens 4 Wochen im Voraus, besonders in der Ferienzeit.

Genehmigung
Dein Antrag wird von deiner direkten Teamleitung geprüft. Bei Rückfragen (z.B. bei Terminüberschneidungen im Team) meldet sie sich direkt bei dir. Die Bearbeitung dauert in der Regel 1–2 Werktage.

Resturlaub
Nicht genommener Urlaub kann bis zum 31. März des Folgejahres übertragen werden. Danach verfällt er automatisch – wir empfehlen, das im Blick zu behalten und rechtzeitig zu planen.

Sonderfälle
Für Urlaub aus besonderem Anlass (z.B. Hochzeit, Umzug) gilt eine eigene Regelung – mehr dazu im Artikel Sonderurlaub.`,
  },
  sonderurlaubsregelung: {
    id: 'sonderurlaubsregelung',
    headline: 'Sonderurlaubsregelung',
    path: 'HR · Abwesenheit · Urlaub',
    breadcrumb: 'HR / Abwesenheit / Urlaub',
    preview: 'Für besondere Anlässe wie Hochzeit, Umzug oder Geburt eines Kindes steht dir zusätzlicher, bezahlter Sonderurlaub zu.',
    isNew: true,
  },
  'sonderurlaub-beantragen': {
    id: 'sonderurlaub-beantragen',
    headline: 'Sonderurlaub beantragen',
    path: 'HR · Abwesenheit · Urlaub',
    breadcrumb: 'HR / Abwesenheit / Urlaub',
    preview: 'Reiche dein Ticket an HR mit Anlass und gewünschtem Datum ein – idealerweise mindestens 2 Wochen im Voraus.',
  },
}

export const abwesenheitArticles = ['urlaub-beantragen', 'sonderurlaubsregelung', 'sonderurlaub-beantragen']
