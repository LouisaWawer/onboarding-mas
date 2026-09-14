/**
 * Kleine Zeit-Formatierungshelfer für den Chat-Verlauf (Datums-Trenner,
 * "vor X Minuten" unter Lumi-Nachrichten) - siehe DisplayMessage.receivedAt
 * in state/AgentState.tsx für die bekannte Ungenauigkeit bei hydrierten
 * Nachrichten.
 */

export function formatRelativeTime(receivedAt: number): string {
  const diffMs = Date.now() - receivedAt
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return 'gerade eben'
  if (diffMin === 1) return 'vor 1 Minute'
  if (diffMin < 60) return `vor ${diffMin} Minuten`
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours === 1) return 'vor 1 Stunde'
  if (diffHours < 24) return `vor ${diffHours} Stunden`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays === 1) return 'vor 1 Tag'
  return `vor ${diffDays} Tagen`
}

/** "Dienstag 22:23" - für den Datums-Trenner am Anfang des Verlaufs. */
export function formatDateDivider(timestamp: number): string {
  const date = new Date(timestamp)
  const weekday = new Intl.DateTimeFormat('de-DE', { weekday: 'long' }).format(date)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${weekday} ${hours}:${minutes}`
}
