import { useState } from 'react'
import { api } from '../api'
import type { Ctx, Stage, ToolInfo } from '../types'
import { useBusy } from '../hooks/useBusy'
import { SessionPanel } from './SessionPanel'
import { GlossaryDrawer } from './GlossaryDrawer'
import { ToolsPanel } from './ToolsPanel'

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

export function Sidebar({ stage, ctx }: { stage: Stage; ctx: Ctx }) {
  const { busy, run } = useBusy()
  const [showGlossary, setShowGlossary] = useState(false)
  const [showTools, setShowTools] = useState(false)
  const status = ctx.status

  const loadDemo = () =>
    run(async () => {
      await api.post('/api/demo')
      await ctx.refresh()
      ctx.go('dataset')
    })

  const data = status?.data

  return (
    <aside className="sidebar">
      <div className="brand">
        <img className="brand-mark" src="/icon.svg" alt="" width={28} height={28} />
        <span>Vowelchemy</span>
      </div>
      <p className="brand-sub">corpus → alignment → vowels → analysis</p>

      <nav className="nav">
        {STAGES.map((s) => (
          <button
            key={s.id}
            className={`nav-item ${stage === s.id ? 'nav-active' : ''}`}
            onClick={() => ctx.go(s.id)}
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
        <ToolRow name="phontrast" info={status?.tools.phontrast} absentNote="built-in JSD" />
        <button className="btn btn-small side-tools" onClick={() => setShowTools(true)}>
          🔧 Set up tools
        </button>
        {status?.tool_env && (
          <div className="muted small mono tool-env-line" title={status.tool_env}>
            env: {status.tool_env.split('/').pop()}
          </div>
        )}
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
      {showTools && <ToolsPanel ctx={ctx} onClose={() => setShowTools(false)} />}
    </aside>
  )
}
