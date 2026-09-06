# Code-Übersicht (Start – muss mit Claude Code verifiziert/aktualisiert werden)

Diese Datei ist ein **Ausgangspunkt**, kein garantiert aktueller Stand – sie fasst zusammen, welche Komponenten laut Chat-Verlauf bisher gebaut wurden. Bitte mit Claude Code abgleichen und regelmäßig aktualisieren lassen (Prompt-Vorschlag am Ende dieser Datei).

## Bekannte Komponenten (Stand: aus dem Chat-Verlauf rekonstruiert)

| Komponente | Zweck | Bekannte Props/Varianten |
|---|---|---|
| `AppShell` / Sidebar | Seitenleiste mit 5 App-Icons (Chat, Intranet, Knowledge Hub, Tickets, Kalender) | Icon-Zustände: default/active/hover, Badge (hasBadge) |
| `Avatar` | Rundes Profilbild, Initialen oder Lumi-Symbol | `icon`: initials/lumi |
| `Status` | Kleiner Indikator-Punkt (online/absent/busy/offline), je mit eigenem Icon | `state`: online/absent/busy/offline |
| `UserWithStatus` | Avatar + Status kombiniert (Flex + negativer Margin, nicht absolute Positionierung) | kombiniert Avatar + Status |
| `ChatListItem` | Kontaktlisten-Eintrag (Name, letzte Nachricht, Zeit, ungelesen-Punkt) | unread state |
| `MessageText` / `MessageBox` | Chat-Nachrichten-Bubble | vermutlich: eigene/fremde/Lumi-Nachricht |
| `Tree` | Baumstruktur-Navigation im Knowledge Hub | `level`: 1–4, `state`: default/selected |
| `PreviewBlock` | Vorschau-Kachel für Wissensartikel | – |
| `Filter` | Filter-Pill im Knowledge Hub | `importance`: high/normal, Zustände default/active/hover |
| `PushButton` | Standard-Button | Overlay-basierte Hover/Press-Zustände (kein fester Hex-Wert) |
| `TaskStatus` | Status-Badge für Tickets (offen/in Bearbeitung/erledigt) | – |
| Composer-Icons (Sparkle/Smiley/Send) | Aktionen im Chat-Eingabefeld | Modifier-Klassen `--assistant` / `--accent` für Hover/Active-Farben |

## Bekannte Dateien/Struktur

```
sandbox-app/src/
  styles/
    colors.css          Farb-Variablen (siehe Finale_Farbpalette.md)
  components/
    (Komponenten aus obiger Tabelle)
  screens/
    Chat/
      Chat.tsx
      Chat.css
    Tickets/
      Tickets.tsx / Tickets.css
    (weitere Screens vermutlich analog: Kalender, Intranet, KnowledgeHub)
  assets/
    icons/               Sidebar-Icons, Status-Icons (aus Figma exportiert)
```

## Bekannte technische Muster

- **Layout**: Flexbox-Ketten (`.app-shell` → `.app-shell__body` → `.app-shell__screen` → jeweiliger Screen-Wrapper), jede Ebene braucht `display:flex` UND `width:100%`/`flex:1`, sonst bricht die Breitenvererbung
- **Tabellen**: CSS Grid mit `grid-template-columns`, nicht Flexbox+`space-between` (letzteres verursacht Spaltenverschiebung zwischen Header/Datenzeilen)
- **Status-Punkt-Positionierung**: feste Pixelgröße, Position über Flex + negativen Margin, nicht `position:absolute` mit Prozentwerten
- **Icons**: SVGs aus Figma exportiert, über `vite-plugin-svgr` als React-Komponenten importiert (nicht als statische `<img>`-Referenzen), damit Farbe per `currentColor`/CSS steuerbar bleibt

## Prompt, um diese Datei zu aktualisieren

```
Bitte aktualisiere docs/CODE_UEBERSICHT.md: Liste alle tatsächlich 
vorhandenen Komponenten in src/components/ und src/screens/ auf, mit 
kurzer Beschreibung, wichtigsten Props/Varianten und wo sie verwendet 
werden. Halte es als kompakte Tabelle, kein Fließtext. Ergänze außerdem 
kurz alle wichtigen technischen Muster/Konventionen, die sich beim 
Bauen herauskristallisiert haben (Layout-Ansatz, State-Management, 
Namenskonventionen).
```
