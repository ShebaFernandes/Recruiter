import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
} from 'react'

function joinClasses(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ')
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'role'
  size?: 'small' | 'medium' | 'large'
  fullWidth?: boolean
}

export function Button({
  variant = 'primary',
  size = 'medium',
  fullWidth = false,
  className,
  ...props
}: ButtonProps) {
  return <button
    className={joinClasses(
      'ui-button',
      `ui-button--${variant}`,
      `ui-button--${size}`,
      fullWidth && 'ui-button--full',
      className,
    )}
    {...props}
  />
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={joinClasses('ui-card', className)} {...props} />
}

type ChipProps = ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean }

export function Chip({ selected, className, ...props }: ChipProps) {
  return <button
    className={joinClasses('ui-chip', selected === true && 'is-selected', className)}
    aria-pressed={selected}
    {...props}
  />
}

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  icon?: ReactNode
  tone?: 'violet' | 'neutral' | 'success'
}

export function Badge({ icon, tone = 'violet', className, children, ...props }: BadgeProps) {
  return <span className={joinClasses('ui-badge', `ui-badge--${tone}`, className)} {...props}>
    {icon}{children}
  </span>
}

type FormFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  hint?: string
}

export function FormField({ label, hint, className, id, name, ...props }: FormFieldProps) {
  const fieldId = id || name
  const labelId = fieldId ? `${fieldId}-label` : undefined
  const hintId = hint && fieldId ? `${fieldId}-hint` : undefined
  return <label className={joinClasses('ui-form-field', className)} htmlFor={fieldId}>
    <span className="ui-form-field__label" id={labelId}>{label}</span>
    <input
      id={fieldId}
      name={name}
      className="ui-form-field__input"
      aria-labelledby={labelId}
      aria-describedby={hintId}
      {...props}
    />
    {hint && <small id={hintId}>{hint}</small>}
  </label>
}
