import './TaskStatus.css'

/** Entspricht Figmas "TaskStatus"/"StatusLight" (node 45:6653 / 44:6598). */
export type TaskState = 'open' | 'processing' | 'done' | 'error'

type TaskStatusProps = {
  state: TaskState
  className?: string
}

const LABEL: Record<TaskState, string> = {
  open: 'Offen',
  processing: 'in Bearbeitung',
  done: 'Erledigt',
  error: 'Support kontaktieren',
}

const COLOR: Record<TaskState, string> = {
  open: 'var(--color-warning)',
  processing: 'var(--color-assistant-soft)',
  done: 'var(--color-success)',
  error: 'var(--color-danger)',
}

export default function TaskStatus({ state, className }: TaskStatusProps) {
  return (
    <span className={`task-status ${className ?? ''}`}>
      <span className="task-status__dot" style={{ backgroundColor: COLOR[state] }} />
      <span className="task-status__label">{LABEL[state]}</span>
    </span>
  )
}
