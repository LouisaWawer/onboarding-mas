export const WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']
export const HOURS = [8, 9, 10, 11, 12, 13, 14, 15, 16]

export type Appointment = {
  id: string
  /** 0 = Montag … 4 = Freitag */
  day: number
  hour: number
  title: string
  location: string
}

/* 1:1 aus Figma übernommen (Kalender-Screen, node 6:77): einzelner
 * Termin "Welcome Meeting" am Montag 09:00 in der Eingangshalle. */
export const initialAppointments: Appointment[] = [
  { id: 'welcome-meeting', day: 0, hour: 9, title: 'Welcome Meeting', location: 'Eingangshalle' },
]
