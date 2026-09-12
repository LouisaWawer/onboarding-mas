# Code-Übersicht

Gegen den tatsächlichen Code-Stand verifiziert (siehe Verifikationsdatum unten) - kein Ausgangspunkt/Entwurf mehr, sondern direkt aus `sandbox-app/src/components/` und `sandbox-app/src/screens/` abgelesen. Bei neuen Komponenten/Screens bitte hier ergänzen (Prompt-Vorschlag am Ende dieser Datei).

## Komponenten (`src/components/`)

| Komponente | Zweck | Wichtigste Props/Varianten | Verwendungsort |
|---|---|---|---|
| `Topbar` | App-weite Kopfzeile (Fensterknöpfe, Suche, Mehr-Menü, eigener "DU"-Avatar) | keine Props | einmal in `App.tsx` |
| `Sidebar` | Hauptnavigation, 5 Bereiche | `active`, `onNavigate`, `badges` | einmal in `App.tsx` |
| `SidebarIcon` | einzelnes Sidebar-Icon | `app` (`intranet\|chat\|hub\|tickets\|calendar`), `state` (`default\|hover\|active`), `hasBadge` | nur in `Sidebar.tsx` |
| `Avatar` | rundes Profilbild, Initialen oder Lumi-Sparkle | `icon` (`initials\|lumi`), `initials`, `color` (`avatar1`-`avatar6`\|`accent`), `size` | in `UserWithStatus`; direkt in `Intranet.tsx` (Verzeichnis) |
| `StatusIndicator` | Präsenzpunkt | `status` (`online\|absent\|busy\|offline\|processing`), `size` | nur in `UserWithStatus.tsx` |
| `UserWithStatus` | Avatar + StatusIndicator kombiniert (Flex + `-6px`-Margin, kein `position:absolute`) | `avatarSize`, `isLumi`, `presence` | `ChatListItem`, `MessageBox`, `Topbar`, `Chat.tsx` (Header) |
| `ChatListItem` | Zeile in der Chat-Kontaktliste | `unread`, `active`, `presence` (leer bei Kanälen) | nur in `Chat.tsx` |
| `MessageBox` | eine Chat-Nachricht | `from` (`in\|out`), `showSender` (versteckt bei Folgenachrichten derselben Person) | nur in `Chat.tsx` |
| `Tree` | rekursive Baumnavigation | `nodes: TreeNode[]` (`kind: 'folder'\|'file'` explizit gesetzt), `selectedId`, `onSelect` | nur in `KnowledgeHub.tsx` |
| `PreviewBlock` | Artikel-Vorschau | `variant` (`default` = Listenzeile, `card` = zentrierte Kachel) | nur in `KnowledgeHub.tsx` |
| `Filter` | Filter-Chip | `active`, `importance` (`normal\|high`) | nur in `KnowledgeHub.tsx` |
| `PushButton` | primärer Aktions-Button | `showIcon` (Plus-Icon), `type` | nur in `Kalender.tsx` ("Neue Besprechung") |
| `TaskStatus` | Status-Punkt+Label für Tickets | `state` (`open\|processing\|done\|error`, Label+Farbe fest zugeordnet) | nur in `Tickets.tsx` |

Barrel-Export aller obigen Komponenten (+ ihrer Prop-/Typ-Exports) in `src/components/index.ts`.

## Screens (`src/screens/`)

| Screen | Zweck | Eigener State/Props | Nutzt Kontext |
|---|---|---|---|
| `Chat/Chat.tsx` | Konversationsliste (Assistent/Kanäle/DMs, ein-/ausklappbare Sektionen) + Nachrichtenverlauf + Composer (Formulierungsvorschlag-Button ist reiner Platzhalter-Button, keine Funktion) | `activeId`, `collapsed`, `draft` | `useChatState`, `useReportBadge('chat', ...)` |
| `Tickets/Tickets.tsx` | Ticket-Tabelle, kein Formular (neue Anfragen laufen laut Szenario-Design über Lumi im Chat) | `tickets`, `selectedId` | `useReportBadge('tickets', ...)` |
| `Kalender/Kalender.tsx` | Wochenansicht Mo-Fr, echte Date-Arithmetik NUR für die Wochennavigation (Termine selbst sind nicht datumsverankert, nur über `day`/`hour` platziert, siehe `Setup_Dokumentation.md` Abschnitt 3); "Neue Besprechung" schickt Anfrage an Lumi statt ein Formular zu öffnen | `weekStart`, `appointments` | `useSendToLumi` |
| `KnowledgeHub/KnowledgeHub.tsx` | Baumnavigation + Landing/gefilterte Ansicht/Detailansicht; Sidebar-Klick auf "Knowledge Hub" resettet immer auf Landing | `view`, `selectedTreeId`, `activeArticleId`, `readIds`; Prop `resetToken` | `useReportBadge('hub', ...)` |
| `Intranet/Intranet.tsx` | Tabs Ankündigungen/Verzeichnis/Neu im Team/Über uns; nur Ankündigungen-Tab hat Figma-Vorlage, Rest aus `Fiktive_Firma_und_Kollegen.md` bzw. ehrlicher Minimalzustand | `activeTab` | `useReportBadge('intranet', ...)`, `useSendToLumi` |

Jeder Screen hat eine gleichnamige `<Screen>.css`-Datei; vier der fünf haben zusätzlich eine `<screen>Data.ts` mit den Mock-Inhalten (`chatData.ts`, `ticketsData.ts`, `kalenderData.ts`, `knowledgeHubData.ts`, `intranetData.ts`).

## State-Management (`src/state/`)

| Modul | Zweck |
|---|---|
| `AppNotifications.tsx` | `AppNotificationsProvider` + `useReportBadge(id, hasNew)` - jeder Screen meldet seinen eigenen Badge-Zustand aus echten Daten, die Sidebar liest nur noch daraus (kein manuelles Prop-Setzen von außen) |
| `ChatState.tsx` | `ChatStateProvider` + `useSendToLumi(userText, lumiReply)` - eine gemeinsame Lumi-Konversation über Screen-Grenzen hinweg (z.B. schreibt der Kalender-Screen dort hinein, ohne dass die Nutzer:in im Chat ist); markiert die Lumi-Konversation dabei als ungelesen |

Beide als React Context + Provider, in `App.tsx` um den gesamten `AppContent`-Baum gelegt (`AppNotificationsProvider` außen, `ChatStateProvider` innen).

## Technische Muster/Konventionen

- **Ordnerstruktur**: ein Ordner pro Komponente/Screen (`ComponentName/ComponentName.tsx` + `ComponentName.css`), PascalCase für Ordner/Dateien, deutsche Screen-Namen wo das Szenario deutsch ist (`Kalender`, nicht `Calendar`) aber englische interne IDs (`SidebarApp = 'calendar'`)
- **Layout**: Flexbox-Kette `.app-shell` → `.app-shell__body` → `.app-shell__screen` (`App.css`), jede Ebene braucht `display:flex` + `flex:1`/`min-height:0`, sonst bricht die Höhen-/Breitenvererbung; Tabellen (z.B. `Tickets.css`) nutzen CSS Grid mit `grid-template-columns` statt Flexbox+`space-between`, damit Spaltenbreiten zwischen Header- und Datenzeilen fix identisch bleiben
- **Daten getrennt von Darstellung**: Mock-/Testdaten je Screen in einer eigenen `<screen>Data.ts`-Datei statt inline im Component
- **State-Ort**: lokaler `useState` für rein bereichsinternen Zustand (z.B. `selectedId` in Tickets); React Context (`src/state/`) nur dort, wo mehrere Screens denselben Zustand teilen müssen (Badges, Lumi-Konversation) - kein globaler Store
- **Farben**: ausschließlich CSS-Custom-Properties aus `colors.css` (`var(--color-*)`), keine hartcodierten Hex-Werte in Komponenten
- **Icons**: zwei bewusst unterschiedliche Quellen - `@phosphor-icons/react` für Sidebar/UI-Icons (weight `regular`/`fill` per Zustand, da sich ein Outline→Fill-Wechsel aus den vollflächigen Figma-Exporten nicht per CSS herleiten ließ) vs. echte aus Figma exportierte SVGs für `StatusIndicator` (`state=*.svg`, per `vite-plugin-svgr`/`?react`-Suffix als Komponente importiert)
- **Avatar+Status-Komposition**: `UserWithStatus` kombiniert `Avatar` + `StatusIndicator` per Flex-Row + festem `-6px`-Margin, nicht `position:absolute` - wird von `ChatListItem`, `MessageBox`, `Topbar` und `Chat.tsx` wiederverwendet statt dort einzeln nachgebaut
- **Barrel-Export**: alle öffentlichen Komponenten + Prop-/Typ-Exports zentral über `src/components/index.ts`

## Verifikationsdatum

09.09.2026 - gegen den tatsächlichen Inhalt von `src/components/*.tsx` und `src/screens/**/*.tsx` gelesen (nicht nur aus Chat-Verlauf rekonstruiert wie die Vorversion dieser Datei).

**Stichprobenartig erneut geprüft am 13.09.2026** (im Zuge eines reinen Backend-/Doku-Auftrags, bei dem viel Backend-seitig dazukam, siehe `Setup_Dokumentation.md` Abschnitt 7/8): `Kalender.tsx`/`kalenderData.ts`, `KnowledgeHub.tsx`, `Intranet.tsx` sowie – im Zuge der Kalender-Normalisierung wenige Tage zuvor – `Tickets.tsx`, `Chat.tsx`, `ChatState.tsx` und `AppNotifications.tsx` gelesen, keine Abweichung zur Tabelle oben gefunden. Keine vollständige Neu-Verifikation aller Komponenten – da in der Zwischenzeit an keiner Sandbox-App-Datei geschrieben wurde (nur `backend/` und `docs/`), ist ein Abweichen unwahrscheinlich, aber nicht für jede einzelne Zeile neu belegt – [zu verifizieren] für die nicht erneut gelesenen Komponenten (`Topbar`, `Sidebar`, `SidebarIcon`, `Avatar`, `StatusIndicator`, `UserWithStatus`, `ChatListItem`, `MessageBox`, `Tree`, `PreviewBlock`, `Filter`, `PushButton`, `TaskStatus`).

## Prompt, um diese Datei zu aktualisieren

```
Bitte aktualisiere docs/CODE_UEBERSICHT.md: Liste alle tatsächlich
vorhandenen Komponenten in src/components/ und src/screens/ auf, mit
kurzer Beschreibung, wichtigsten Props/Varianten und wo sie verwendet
werden. Halte es als kompakte Tabelle, kein Fließtext. Ergänze außerdem
kurz alle wichtigen technischen Muster/Konventionen, die sich beim
Bauen herauskristallisiert haben (Layout-Ansatz, State-Management,
Namenskonventionen), und aktualisiere das Verifikationsdatum.
```
