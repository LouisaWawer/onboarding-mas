import { Plus } from '@phosphor-icons/react'
import './PushButton.css'

type PushButtonProps = {
  label: string
  /** Icon ausblenden, z.B. für reine Text-Buttons ohne "Neu"-Aktion */
  showIcon?: boolean
  type?: 'button' | 'submit'
  /** primary = gefüllt (bisheriges Verhalten, Default), secondary = Outline
      (ConfirmationCard, Figma-Varianten "Anpassen"/"Ablehnen"/"Abbrechen") */
  variant?: 'primary' | 'secondary'
  disabled?: boolean
  title?: string
  onClick?: () => void
}

export default function PushButton({
  label,
  showIcon = true,
  type = 'button',
  variant = 'primary',
  disabled = false,
  title,
  onClick,
}: PushButtonProps) {
  return (
    <button
      type={type}
      className={`push-button push-button--${variant}`}
      disabled={disabled}
      title={title}
      onClick={onClick}
    >
      {showIcon && (
        <Plus size={17.5} color={variant === 'primary' ? 'var(--color-overlay)' : 'var(--color-text)'} weight="bold" />
      )}
      <span>{label}</span>
    </button>
  )
}
