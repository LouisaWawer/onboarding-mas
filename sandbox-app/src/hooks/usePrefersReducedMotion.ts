import { useEffect, useState } from 'react'

/**
 * Für alle Rive-Komponenten gebraucht (siehe SparkleIndicator jetzt,
 * der periphere Punkt in Schritt 5 später) - deshalb als eigener,
 * wiederverwendbarer Hook statt in einer einzelnen Komponente versteckt.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )

  useEffect(() => {
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches)
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [])

  return reduced
}
