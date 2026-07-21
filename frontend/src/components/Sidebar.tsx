import { useState } from 'react'
import { api } from '../api'
import type { Ctx, Stage, Status, ToolInfo } from '../types'
import { SessionPanel } from './SessionPanel'
import { GlossaryDrawer } from './GlossaryDrawer'

const STAGES: { id: Stage; n: number; label: string }[] = [
  { id: 'corpus', n: 1, label: 'Corpus' },
  { id: 'align', n: 2, label: 'Align' },
  { id: 'extract', n: 3, label: 'Extract' },
  { id: 'dataset', n: 4, label: 'Dataset' },
  { id: 'visualize', n: 5, label: 'Visualize' },
  { id: 'separation', n: 6, label: 'Separation' },
]

function ToolRow({ name, info, absentNote }: { name: string; info?: ToolInfo; absentNote?: string }) {
  const ok = info?.available
  return (
    <div className="tool-row" title={info && !ok ? info.hint : undefined}>
      <span className={`dot ${ok ? 'dot-on' : ''}`} />
      <span className="tool-name">{name}</span>
      <span className="tool-ver">{ok ? info?.version ?? 'ready' : absentNote ?? 'not detected'}</span>
    </div>
  )
}

export function Sidebar({
  stage,
  setStage,
  status,
  refresh,
  ctx,
}: {
  stage: Stage
  setStage: (s: Stage) => void
  status: Status | null
  refresh: () => Promise<void>
  ctx: Ctx
}) {
  const [busy, setBusy] = useState(false)
  const [showGlossary, setShowGlossary] = useState(false)

  const loadDemo = async () => {
    setBusy(true)
    try {
      await api.post('/api/demo')
      await refresh()
      setStage('dataset')
    } finally {
      setBusy(false)
    }
  }

  const data = status?.data

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">🧪</span>
        <span>Vowelchemy</span>
      </div>
      <p className="brand-sub">corpus → alignment → vowels → analysis</p>

      <nav className="nav">
        {STAGES.map((s) => (
          <button
            key={s.id}
            className={`nav-item ${stage === s.id ? 'nav-active' : ''}`}
            onClick={() => setStage(s.id)}
          >
            <span className="nav-num">{s.n}</span>
            {s.label}
          </button>
        ))}
      </nav>

      <div className="side-section">
        <div className="side-heading">Tools</div>
        <ToolRow name="MFA" info={status?.tools.mfa} />
        <ToolRow name="new-fave" info={status?.tools.newfave} />
        <ToolRow name="phonJSD" info={status?.tools.phonjsd} absentNote="built-in JSD" />
      </div>

      <div className="side-section">
        <div className="side-heading">Data</div>
        {data?.loaded ? (
          <>
            <div className="data-line">🟢 {data.n_tokens.toLocaleString()} vowel tokens</div>
            {data.n_speakers > 0 && <div className="data-line">🟢 {data.n_speakers} speakers</div>}
            <div className="data-line muted">norm: {data.norm_method}</div>
          </>
        ) : (
          <div className="data-line muted">⚪ no vowel data yet</div>
        )}
      </div>

      <button className="btn btn-demo" onClick={loadDemo} disabled={busy}>
        {busy ? <span className="spinner" /> : '✨ '}
        Load demo dataset
      </button>
      <p className="brand-sub small">
        Demo mode loads a synthetic corpus so you can explore stages 4–6 without MFA/new-fave.
      </p>

      <SessionPanel ctx={ctx} />

      <button className="btn btn-small side-help" onClick={() => setShowGlossary(true)}>
        ❔ Glossary &amp; help
      </button>
      {showGlossary && <GlossaryDrawer onClose={() => setShowGlossary(false)} />}
    </aside>
  )
}
