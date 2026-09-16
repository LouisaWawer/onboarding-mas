import { useEffect, useRef, useState } from 'react'
import { Sparkle } from '@phosphor-icons/react'
import { useRive, useViewModel, useViewModelInstance, useViewModelInstanceBoolean, useViewModelInstanceNumber } from '@rive-app/react-canvas'
import LumiPanel from '../LumiPanel/LumiPanel'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { useOverallStatus } from '../../state/AgentState'
import { STATUS_TO_RIVE_NUMBER } from '../../utils/riveStatus'
import './StatusDot.css'

/**
 * Peripherer Statuspunkt (Figma: FloatingLumi, 64px) - App-Level-Overlay
 * über dem Screen-Router (siehe App.tsx), kein eigenes Betriebssystem-
 * Fenster. Steuerung ausschließlich über das ViewModel AvatarData, State
 * Machine AvatarMachine, Instanz "Lumi" (siehe Bericht an die Nutzerin).
 *
 * API-Wahl: verwendet die dedizierten View-Model-Hooks
 * (useViewModel/useViewModelInstance/useViewModelInstanceNumber/-Boolean)
 * aus der tatsächlich installierten @rive-app/react-canvas-Version (gegen
 * node_modules/@rive-app/react-canvas/dist/types/index.d.ts geprüft) -
 * NICHT den imperativen Weg (rive.viewModelByName()...) wie im älteren
 * SparkleIndicator, der das seinerzeit ungeprüft ließ. Beide Wege dürften
 * funktionieren, dies hier ist der von der installierten Version aktiv
 * dokumentierte.
 *
 * panelOpen: Rive setzt es laut Bericht an die Nutzerin selbst über einen
 * eigenen Listener auf true, sobald der Punkt angeklickt wird - dafür wird
 * hier NICHT aktiv geschrieben, sondern nur reaktiv GELESEN
 * (riveBoolean.value) und in lokalen React-State übernommen. Zusätzlich
 * ein eigener onClick als Sicherheitsnetz (setzt denselben React-State) -
 * schadet nicht, falls sich herausstellt, dass der interne Rive-Listener
 * aus irgendeinem Grund nicht feuert. Der umgekehrte Weg (React->Rive) läuft
 * über GENAU EINEN Effekt, der jede Änderung von panelOpen spiegelt (siehe
 * unten) - unabhängig davon, WODURCH das Panel geschlossen wurde
 * (Minimieren, Klick daneben, Wechsel in den Chat).
 *
 * isHovered: bewusst NICHT angefasst - bleibt vollständig bei Rive (siehe
 * Bericht an die Nutzerin). UNGEPRÜFT, ob der interne Hover-Listener dafür
 * tatsächlich greift (in dieser Umgebung kein Browser-Zugriff zum
 * Ausprobieren) - bitte beim Testen kurz prüfen, ob ein Hover-Effekt
 * sichtbar ist.
 */
export default function StatusDot() {
  const prefersReducedMotion = usePrefersReducedMotion()
  const overallStatus = useOverallStatus()
  const [panelOpen, setPanelOpen] = useState(false)
  const [bindingError, setBindingError] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // REST-Punkt (siehe Bericht an die Nutzerin): bei prefers-reduced-motion
  // wird die .riv-Datei gar nicht erst geladen (useRive akzeptiert null),
  // statt sie zu laden und die Bewegung nur per CSS zu kaschieren.
  const { rive, RiveComponent } = useRive(
    prefersReducedMotion
      ? null
      : {
          src: '/lumiwithsparkle.riv',
          stateMachines: 'AvatarMachine',
          autoplay: true,
          onLoadError: (err) => {
            console.error('[status-dot] lumiwithsparkle.riv konnte nicht geladen werden', err)
            setLoadError(true)
          },
        },
  )

  const viewModel = useViewModel(rive, { name: 'AvatarData' })
  const instance = useViewModelInstance(viewModel, { name: 'Lumi', rive })

  const { setValue: setStatus } = useViewModelInstanceNumber('status', instance)
  const { value: rivePanelOpen, setValue: setRivePanelOpen } = useViewModelInstanceBoolean('panelOpen', instance)

  useEffect(() => {
    if (!rive || !viewModel || !instance) return
    setBindingError(false)
  }, [rive, viewModel, instance])

  // Debug-Ausgabe (siehe Bericht an die Nutzerin) - deckt alle drei
  // möglichen Fehlerstellen in EINER Zeile ab: prefersReducedMotion (würde
  // die Datei-Anforderung im Network-Tab erklären), riveLoaded/
  // viewModelFound/instanceFound (Bindung), overallStatus/numericStatus
  // (Rangfolge + tatsächlich gesetzter Zahlenwert). Temporär, wieder
  // entfernen, sobald geklärt ist, wo es hängt.
  useEffect(() => {
    console.log('[status-dot][debug]', {
      prefersReducedMotion,
      riveLoaded: Boolean(rive),
      viewModelFound: Boolean(viewModel),
      instanceFound: Boolean(instance),
      overallStatus,
      numericStatus: STATUS_TO_RIVE_NUMBER[overallStatus],
    })
  }, [prefersReducedMotion, rive, viewModel, instance, overallStatus])

  // Zweite Debug-Ausgabe (siehe Bericht an die Nutzerin): statt gegen
  // "AvatarData" zu prüfen, listet das auf, was lumiwithsparkle.riv
  // TATSÄCHLICH an ViewModels enthält - über die imperative Rive-Klasse
  // (rive.viewModelCount/viewModelByIndex, siehe node_modules/@rive-app/
  // canvas/rive.d.ts), nicht über die Namens-Annahme in useViewModel()
  // oben. Ändert nichts an der eigentlichen Bindung, nur zusätzliche
  // Sichtbarkeit.
  useEffect(() => {
    if (!rive) return
    const found: { name: string; instanceNames: string[]; properties: unknown }[] = []
    for (let i = 0; i < rive.viewModelCount; i++) {
      const vm = rive.viewModelByIndex(i)
      if (!vm) continue
      found.push({ name: vm.name, instanceNames: vm.instanceNames, properties: vm.properties })
    }
    console.log('[status-dot][debug] ViewModels in lumiwithsparkle.riv:', found)
    console.log('[status-dot][debug] defaultViewModel():', rive.defaultViewModel()?.name ?? null)
  }, [rive])

  useEffect(() => {
    if (!instance) return
    try {
      setStatus(STATUS_TO_RIVE_NUMBER[overallStatus])
    } catch (err) {
      console.error('[status-dot] status-Property konnte nicht gesetzt werden', err)
      setBindingError(true)
    }
  }, [instance, overallStatus, setStatus])

  // Rive -> React: der interne Klick-Listener von lumiwithsparkle.riv setzt
  // panelOpen selbst auf true (siehe Moduldocstring) - hier nur übernommen.
  useEffect(() => {
    if (rivePanelOpen) setPanelOpen(true)
  }, [rivePanelOpen])

  // React -> Rive: EIN Effekt für JEDE Änderung von panelOpen, unabhängig
  // vom Auslöser (siehe Moduldocstring - "schreib den Wert nicht in jedem
  // Handler einzeln").
  //
  // Vorbereitet, aber unerreichbar (siehe docs/Setup_Dokumentation.md,
  // gleiches Format wie die anderen Einträge dieser Art): der Trigger
  // (und damit sein Canvas) wird jetzt per CSS ausgeblendet, GENAU in dem
  // Moment, in dem panelOpen true wird (siehe .status-dot__trigger--hidden
  // unten sowie StatusDot.css) - eine etwaige Reaktion dieses ViewModel-
  // Werts innerhalb von lumiwithsparkle.riv wäre also nie sichtbar. Bewusst
  // nicht entfernt, nur kommentiert: falls das Öffnen des Panels
  // gestalterisch später ausformuliert wird (aktuell nicht der Fall, siehe
  // Bericht an die Nutzerin), ist die Zuleitung bereits da.
  useEffect(() => {
    if (!instance) return
    setRivePanelOpen(panelOpen)
  }, [instance, panelOpen, setRivePanelOpen])

  // Klick außerhalb (Punkt + Panel) schließt - eine der drei im Auftrag
  // genannten Schließen-Wege.
  useEffect(() => {
    if (!panelOpen) return
    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setPanelOpen(false)
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [panelOpen])

  const showFallback = prefersReducedMotion || !rive || bindingError || loadError

  return (
    <div className="status-dot" ref={containerRef}>
      {/* Ausgeblendet, solange das Panel offen ist (siehe Bericht an die
          Nutzerin, Schritt 5, Punkt 1) - hartes Ausblenden per CSS-Klasse,
          KEIN unmount: der Canvas/die Rive-Instanz bleibt bestehen, nur
          unsichtbar (display:none), damit kein erneutes Laden/Binden beim
          nächsten Schließen nötig ist. panelOpen deckt alle drei
          Schließwege gleichermaßen ab (Minimieren-Icon, Klick daneben, "im
          Chat öffnen" - siehe LumiPanel/handlePointerDown oben), weil sie
          alle auf denselben React-State zurückschreiben. */}
      <button
        type="button"
        className={panelOpen ? 'status-dot__trigger status-dot__trigger--hidden' : 'status-dot__trigger'}
        onClick={() => setPanelOpen(true)}
        aria-label="Lumi öffnen"
        aria-expanded={panelOpen}
      >
        {!prefersReducedMotion && <RiveComponent />}
        {showFallback && (
          <div className="status-dot__fallback" aria-hidden="true">
            <Sparkle size={28} color="var(--color-overlay)" weight="fill" />
          </div>
        )}
      </button>

      {/* LumiPanel entscheidet selbst, WAS beim "zum Chat wechseln"-Icon
          passiert (navigateTo('chat')) - hier nur EIN Schließen-Callback,
          für Minimieren UND für "danach schließen" nach dem Wechsel. */}
      {panelOpen && <LumiPanel onClose={() => setPanelOpen(false)} />}
    </div>
  )
}
