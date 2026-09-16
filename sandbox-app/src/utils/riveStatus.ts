import type { StatusValue } from '../api/client'

/**
 * AvatarData/AvatarMachine/Lumi/status - EINE Quelle für beide Rive-Dateien,
 * die dieses Mapping brauchen (lumiwithsparkle.riv im StatusDot,
 * lumiwithsparklesmall.riv im LumiPanel-Topbar-Avatar), statt es zweimal zu
 * pflegen (siehe Bericht an die Nutzerin, Schritt 5).
 */
export const STATUS_TO_RIVE_NUMBER: Record<StatusValue, number> = {
  idle: 0,
  working: 1,
  suggestion: 2,
  waiting: 3,
  result: 4,
  error: 5,
}
