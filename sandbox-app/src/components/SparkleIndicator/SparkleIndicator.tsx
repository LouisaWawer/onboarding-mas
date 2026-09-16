import { useEffect, useState } from 'react'
import { Sparkle } from '@phosphor-icons/react'
import { useRive } from '@rive-app/react-canvas'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import './SparkleIndicator.css'

type SparkleIndicatorProps = {
  /** sparkle.riv kennt laut Auftrag nur diese zwei Zustände. */
  status: 'idle' | 'working'
}

// AvatarData/AvatarMachine/Lumi/status - siehe Auftrag. sparkle.riv bildet
// nur Idle (0) und Working (1) ab, die übrigen vier Werte (Suggestion/
// Waiting/Result/Error) gehören zum peripheren Punkt (lumiwithsparkle.riv,
// Schritt 5), nicht zu diesem Denk-Indikator.
const STATUS_VALUES: Record<SparkleIndicatorProps['status'], number> = {
  idle: 0,
  working: 1,
}

/**
 * Denk-Indikator im Chat-Verlauf (Figma: "LumiInChatAvatar", 40px),
 * gesteuert über sparkle.riv + die ViewModel-Dateneinbindung AvatarData/
 * Instanz "Lumi"/Eigenschaft "status" (siehe Auftrag).
 *
 * UNGEPRÜFT: die genaue JS-API für Rives View-Model-Datenbindung
 * (viewModelByName/instanceByName/bindViewModelInstance/number(...).value)
 * folgt dem allgemein dokumentierten Muster der aktuellen
 * @rive-app/react-canvas-Version, ist hier aber nicht gegen die
 * tatsächlich installierte Version lauffähig getestet (kein npm install in
 * dieser Umgebung möglich, siehe Bericht an die Nutzerin). Falls die
 * Methodennamen in der installierten Version abweichen, bitte melden -
 * dann prüfen wir das zusammen gegen die echten TypeScript-Typen.
 */
export default function SparkleIndicator({ status }: SparkleIndicatorProps) {
  const prefersReducedMotion = usePrefersReducedMotion()
  const [bindingError, setBindingError] = useState(false)
  const [loadError, setLoadError] = useState(false)
  // Bugfix (siehe Bericht an die Nutzerin, Schritt 5): bei prefers-reduced-
  // motion wurde die .riv-Datei bisher trotzdem geladen, nur die CSS-Klasse
  // .sparkle-indicator--reduced-motion versuchte hinterher die Bewegung zu
  // kaschieren (kann die intern in der Datei hinterlegte Animation nicht
  // abschalten, siehe SparkleIndicator.css). useRive akzeptiert null als
  // ersten Parameter (verifiziert gegen node_modules/@rive-app/react-canvas/
  // dist/types/index.d.ts) - die Datei wird dann gar nicht erst angefragt.
  const { rive, RiveComponent } = useRive(
    prefersReducedMotion
      ? null
      : {
          src: '/sparkle.riv',
          stateMachines: 'AvatarMachine',
          autoplay: true,
          // Rein diagnostisch (siehe Bericht an die Nutzerin) - der
          // eigentliche Bug lag woanders (RiveComponent wurde nie
          // gemountet, siehe unten), aber diese zwei Callbacks bleiben
          // drin, falls künftig die DATEI selbst das Problem ist (falscher
          // Pfad, kaputte .riv), statt wieder stillschweigend im Fallback
          // zu enden.
          onLoad: () => console.log('[sparkle-indicator] sparkle.riv geladen'),
          onLoadError: (err) => {
            console.error('[sparkle-indicator] sparkle.riv konnte nicht geladen werden', err)
            setLoadError(true)
          },
        },
  )

  useEffect(() => {
    if (!rive) return
    try {
      const vm = rive.viewModelByName('AvatarData')
      if (!vm) throw new Error('ViewModel "AvatarData" nicht gefunden')
      const instance = vm.instanceByName('Lumi') ?? vm.defaultInstance()
      if (!instance) throw new Error('ViewModel-Instanz "Lumi" nicht gefunden')
      rive.bindViewModelInstance(instance)
      const statusProp = instance.number('status')
      if (!statusProp) throw new Error('Zahlen-Property "status" nicht gefunden')
      statusProp.value = STATUS_VALUES[status]
    } catch (err) {
      console.error('[sparkle-indicator] ViewModel-Bindung fehlgeschlagen - siehe Moduldocstring', err)
      setBindingError(true)
    }
  }, [rive, status])

  // BUGFIX (siehe Bericht an die Nutzerin): <RiveComponent /> ist nicht nur
  // eine Ansicht eines bereits geladenen Zustands, sondern die Komponente,
  // die den <canvas> mountet, an den Rive überhaupt erst lädt. Die vorige
  // Fassung rendert das Canvas nur, NACHDEM rive schon geladen war - ein
  // Henne-Ei-Deadlock, der sich nie auflöst (kein Canvas im DOM, keine
  // Anfrage nach sparkle.riv, rive bleibt für immer null). Jetzt IMMER
  // gemountet (außer bei reduced motion, dort wird gar nicht erst geladen,
  // siehe oben); der Fallback liegt nur als Overlay darüber, bis geladen ist.
  const showFallback = prefersReducedMotion || !rive || bindingError || loadError

  return (
    <div
      className="sparkle-indicator"
      role={status === 'working' && !showFallback ? 'img' : undefined}
      aria-label={status === 'working' && !showFallback ? 'Lumi denkt nach' : undefined}
      aria-hidden={status === 'idle' || showFallback ? 'true' : undefined}
    >
      {!prefersReducedMotion && <RiveComponent />}
      {showFallback && (
        <div className="sparkle-indicator__fallback" aria-hidden="true">
          <Sparkle size={20} color="var(--color-assistant)" weight="fill" />
        </div>
      )}
    </div>
  )
}
