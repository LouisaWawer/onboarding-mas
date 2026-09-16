import { useEffect, useState } from 'react'
import { Sparkle } from '@phosphor-icons/react'
import { useRive, useViewModel, useViewModelInstance, useViewModelInstanceNumber } from '@rive-app/react-canvas'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { useOverallStatus } from '../../state/AgentState'
import { STATUS_TO_RIVE_NUMBER } from '../../utils/riveStatus'
import './LumiAvatar.css'

type LumiAvatarProps = {
  size?: number
  /**
   * 'small' = lumiwithsparklesmall.riv (Standard - Chat-Kopfzeile,
   * "Agent AI"-Zeile, Intranet-Verzeichnis, Panel-Topbar).
   * 'large' = lumiwithsparkle.riv, dieselbe Datei wie der periphere Punkt
   * (StatusDot), hier aber rein dekorativ im leeren Panel-Zustand (Figma:
   * FloatingLumi, 64px) - NUR "status" wird gesetzt, panelOpen/isHovered
   * bleiben unangetastet (die gehören ausschließlich zu StatusDot, das ist
   * der einzige tatsächliche Auslöser für das Panel).
   */
  variant?: 'small' | 'large'
}

const SRC: Record<NonNullable<LumiAvatarProps['variant']>, string> = {
  small: '/lumiwithsparklesmall.riv',
  large: '/lumiwithsparkle.riv',
}

/**
 * Lumis Avatar über Rive (siehe Bericht an die Nutzerin, Schritt 5,
 * Punkt 1) - EINE Komponente für JEDEN Lumi-Avatar im UI, herausgelöst aus
 * dem ursprünglich inline in LumiPanel.tsx stehenden Code, damit nicht
 * mehrere Kopien derselben Rive-Bindung entstehen.
 *
 * `size` skaliert nur den Container (Rive-Canvas füllt ihn per CSS,
 * bleibt vektoriell scharf).
 */
export default function LumiAvatar({ size = 32, variant = 'small' }: LumiAvatarProps) {
  const prefersReducedMotion = usePrefersReducedMotion()
  const overallStatus = useOverallStatus()
  const [loadError, setLoadError] = useState(false)

  const { rive, RiveComponent } = useRive(
    prefersReducedMotion
      ? null
      : {
          src: SRC[variant],
          stateMachines: 'AvatarMachine',
          autoplay: true,
          onLoadError: (err) => {
            console.error(`[lumi-avatar] ${SRC[variant]} konnte nicht geladen werden`, err)
            setLoadError(true)
          },
        },
  )
  const viewModel = useViewModel(rive, { name: 'AvatarData' })
  const instance = useViewModelInstance(viewModel, { name: 'Lumi', rive })
  const { setValue: setStatus } = useViewModelInstanceNumber('status', instance)

  useEffect(() => {
    if (!instance) return
    setStatus(STATUS_TO_RIVE_NUMBER[overallStatus])
  }, [instance, overallStatus, setStatus])

  const showFallback = prefersReducedMotion || !rive || loadError

  return (
    <div className="lumi-avatar" style={{ width: size, height: size }}>
      {!prefersReducedMotion && <RiveComponent />}
      {showFallback && (
        // Gleiche Optik wie die frühere statische Avatar-Darstellung
        // (Avatar.tsx, icon="lumi") - color/assistant-Kreis + Sparkle.
        <div className="lumi-avatar__fallback" aria-hidden="true">
          <Sparkle size={Math.round(size * 0.6)} color="var(--color-overlay)" weight="fill" />
        </div>
      )}
    </div>
  )
}
