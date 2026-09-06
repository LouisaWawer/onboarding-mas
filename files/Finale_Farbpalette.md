# Finale Farbpalette

**Quelle der Wahrheit: Figma-Variablen** (Stand: aktualisiert nach Figma-Export). Diese Datei wurde entsprechend angepasst.

## Neutraltöne

⚠️ Aktualisiert nach Figma-Stand (neutrales Grau statt der ursprünglich geplanten grünlichen Nordlicht-Tönung):

| Rolle | Hex | Figma-Variable |
|---|---|---|
| Seite (bg) | `#F5F5F5` | `color/bg` |
| Rahmen (frame) | `#D9D9D9` | `color/border` |
| Text primär (text) | `#23301F` | `color/text` |
| Weiß (window) | `#FFFFFF` | `color/window` |

## Statusfarben

⚠️ Verifiziert direkt an den tatsächlich genutzten Komponenten (TaskStatus, StatusLight) – **ein** Wertepaar, keine zweite "Indikator"-Variante (Vermutung: dunklere Werte an anderer Stelle waren eine Dokumentations-Swatch, nicht real gebunden):

| Rolle | Hex |
|---|---|
| Erfolg (success) | `#009951` |
| Warnung (warning) | `#e5a000` |
| Fehler (error) | `#c00f0c` |
| Assistent-Status | `#5b6aec` bei **50% Deckkraft** (`#5b6aec80`) |

## Akzent-Zustände: keine festen Hex-Werte, sondern Overlay-Logik

Anders als ursprünglich dokumentiert: Figma hat **keine eigenen Variablen** für Hover/Press/Active/Selected. Stattdessen werden diese Zustände live aus `color/accent` plus einer Weiß-/Schwarz-Überlagerung gemischt (verifiziert an PushButton, Filter, Tree). Entsprechend als `--overlay-*`-Tokens abzubilden, nicht als fixe Hex-Werte:

| Rolle | Hex |
|---|---|
| Akzent (Basis) | `#6B76D6` |

## Weitere real gebundene Tokens (zusätzlich zur ursprünglichen Planung)

Von Claude Code in den Frames gefunden, nicht Teil der ursprünglichen Nordlicht-Planung, aber real genutzt:

- `color/overlay`, `color/overlaywhite` – für die Hover/Press-Überlagerungen (siehe oben)
- `color/faded` – abgeschwächte/deaktivierte Zustände
- Material-Transluzenz-Tokens – bei den Kalender-Terminen im Einsatz
- Eine kleine UI-Kit-Grauskala – vermutlich aus einer importierten Bibliothekskomponente (macOS-Fenstersteuerung o.ä.), nicht Nordlicht-eigen – muss nicht in unser Farbsystem übernommen werden

## Avatarfarben (aktualisiert – Zuordnung zum aktuellen Cast)

| Person | Hex | Figma-Name |
|---|---|---|
| Max Vogel (IT) | `#AE549C` | avatar6 |
| Anna Schmidt (HR) | `#561780` | avatar4 |
| Laura Seifert (Controlling) | `#A98CC4` | avatar2 |
| Tom Bauer (Vertrieb, Buddy) | `#854595` | avatar1 |
| Lars Becker (Marketing) | `#4A1C85` | avatar-5 |
| – (unbenutzt, Reserve) | `#702083` | avatar3 |
| Lumi (Assistent) | `#5B6AEC` | color/assistant |

---

## Als CSS-Variablen (direkt für React/Tauri nutzbar)

```css
:root {
  /* Neutraltöne */
  --color-bg-page: #F5F5F5;
  --color-border: #D9D9D9;
  --color-text-primary: #23301F;
  --color-window: #FFFFFF;

  /* Statusfarben (verifiziert, ein Wertepaar) */
  --color-success: #009951;
  --color-warning: #e5a000;
  --color-danger: #c00f0c;

  /* Akzent (Basis; Hover/Press/Active über Overlay, siehe oben) */
  --color-accent: #6B76D6;

  /* Assistent */
  --color-avatar-assistent: #5b6aec;
  --color-avatar-assistent-50: #5b6aec80;

  /* Avatarfarben */
  --color-avatar-max: #AE549C;
  --color-avatar-anna: #561780;
  --color-avatar-laura: #A98CC4;
  --color-avatar-tom: #854595;
  --color-avatar-lars: #4A1C85;
}
```

## Offene Punkte

- **Overlay-Werte** (`color/overlay`, `color/overlaywhite`): exakte Hex-/Alpha-Werte noch zu übernehmen, sobald Claude Code sie beim Bau der Komponenten (Schritt 2) direkt einliest.
- **avatar3 (`#702083`)**: aktuell unbenutzt, Reserve für eine mögliche sechste Person.
- **UI-Kit-Grauskala**: vermutlich aus importierter Bibliothek (macOS-Fenstersteuerung), nicht Nordlicht-eigenes Farbsystem – bei Bedarf gesondert dokumentieren, falls sie doch im UI sichtbar wird.

