import type { ReactNode } from 'react'

export function Card({ title, subtitle, children }: { title?: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="card">
      {title && <h3 className="card-title">{title}</h3>}
      {subtitle && <p className="muted">{subtitle}</p>}
      {children}
    </section>
  )
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="muted small">{hint}</span>}
    </label>
  )
}

export function Button({
  children,
  onClick,
  primary,
  disabled,
  busy,
}: {
  children: ReactNode
  onClick?: () => void
  primary?: boolean
  disabled?: boolean
  busy?: boolean
}) {
  return (
    <button className={`btn ${primary ? 'btn-primary' : ''}`} onClick={onClick} disabled={disabled || busy}>
      {busy ? <span className="spinner" /> : null}
      {children}
    </button>
  )
}

export function Notice({ kind = 'info', children }: { kind?: 'info' | 'success' | 'warn' | 'error'; children: ReactNode }) {
  return <div className={`notice notice-${kind}`}>{children}</div>
}

export function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="metric">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  )
}

export function LogBox({ text }: { text: string }) {
  if (!text) return null
  return <pre className="logbox">{text}</pre>
}

export function MultiSelect({
  options,
  selected,
  onChange,
}: {
  options: { value: string; label: string }[]
  selected: string[]
  onChange: (values: string[]) => void
}) {
  const toggle = (v: string) => {
    onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v])
  }
  return (
    <div className="chips">
      {options.map((o) => (
        <button
          key={o.value}
          className={`chip ${selected.includes(o.value) ? 'chip-on' : ''}`}
          onClick={() => toggle(o.value)}
          type="button"
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
