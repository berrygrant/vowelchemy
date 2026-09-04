import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Ctx, ToolsPayload } from '../types'
import { useBusy } from '../hooks/useBusy'
import { useJob } from '../hooks/useJob'
import { FolderPicker } from './FolderPicker'
import { LogBox, Notice } from './ui'

const MAMBA_CMD = 'mamba create -n aligner -c conda-forge montreal-forced-aligner'

// Aligning and extracting need two outside programs. MFA is conda/mamba-only
// (its Kaldi bindings aren't on PyPI), so the app borrows it from an existing
// environment; new-fave is a pip package, so the app can install it directly.
export function ToolsPanel({ ctx, onClose }: { ctx: Ctx; onClose: () => void }) {
  const [data, setData] = useState<ToolsPayload | null>(null)
  const [picking, setPicking] = useState(false)
  const [copied, setCopied] = useState(false)
  const { busy, error, setError, run } = useBusy()
  const install = useJob(undefined, () => {
    void refresh()
    void ctx.refresh()
  })

  const refresh = async () => {
    setData(await api.get('/api/tools/environments'))
  }

  useEffect(() => {
    void run(refresh)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const choose = (path: string | null) =>
    run(async () => {
      setData(await api.post('/api/tools/environment', { path }))
      await ctx.refresh()
    })

  const startInstall = () => install.start('/api/tools/install', { tool: 'newfave' })

  const copyCmd = () => {
    navigator.clipboard?.writeText(MAMBA_CMD).then(
      () => {
        setCopied(true)
        window.setTimeout(() => setCopied(false), 1800)
      },
      () => setError('Could not copy — select the command and copy it manually.'),
    )
  }

  const mfa = data?.tools.mfa
  const nf = data?.tools.newfave
  const canInstallNewfave = data?.install?.newfave?.possible

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-label="Set up tools">
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <b>Set up tools</b>
          <button className="btn btn-small" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="browser">
          <p className="muted small">
            Stages 1 and 4–6 work without these. You only need them to align and measure raw
            audio yourself — if your lab gave you an extracted vowel CSV, you can close this and
            load it in stage 3.
          </p>

          <div className="tool-status">
            <div>
              {mfa?.available ? '🟢' : '⚪'} <b>MFA</b> (aligner) —{' '}
              {mfa?.available ? mfa.version ?? 'ready' : 'not found'}
            </div>
            <div>
              {nf?.available ? '🟢' : '⚪'} <b>new-fave</b> (formant measurement) —{' '}
              {nf?.available ? nf.version ?? 'ready' : 'not found'}
            </div>
          </div>

          {error && <Notice kind="error">{error}</Notice>}

          {/* 1 · borrow an environment */}
          <div className="tools-section">
            <div className="glossary-term">Use an environment you already have</div>
            <div className="muted small">
              Pick a conda/mamba environment containing the tools; Vowelchemy runs them straight
              from there, so you never have to activate it.
            </div>
          </div>

          {data?.selected && (
            <div className="tool-selected">
              Using <code>{data.selected}</code>{' '}
              {!data.selected_locked && (
                <button className="btn btn-small" onClick={() => choose(null)} disabled={busy}>
                  Stop using
                </button>
              )}
              {data.selected_locked && (
                <span className="muted small">(set by VOWELCHEMY_TOOL_ENV)</span>
              )}
            </div>
          )}

          {busy && !data && <div className="muted small">Looking for environments…</div>}

          {data?.environments?.length ? (
            data.environments.map((env) => (
              <div key={env.path} className="env-row">
                <div>
                  <div>
                    <b>{env.name}</b>{' '}
                    <span className="muted small">
                      {env.tools.map((t) => (t === 'mfa' ? 'MFA' : 'new-fave')).join(' + ')}
                      {env.source === 'app' ? ' · this app' : ''}
                    </span>
                  </div>
                  <div className="muted small mono">{env.path}</div>
                </div>
                <button
                  className="btn btn-small"
                  onClick={() => choose(env.path)}
                  disabled={busy || data.selected === env.path}
                >
                  {data.selected === env.path ? 'In use' : 'Use this'}
                </button>
              </div>
            ))
          ) : (
            !busy && (
              <div className="muted small">
                No environment with MFA or new-fave found automatically.
              </div>
            )
          )}

          <div className="row">
            <button className="btn btn-small" onClick={() => setPicking(true)} disabled={busy}>
              📁 Choose a folder…
            </button>
            <button className="btn btn-small" onClick={() => void run(refresh)} disabled={busy}>
              ↻ Scan again
            </button>
          </div>

          {/* 2 · install new-fave */}
          <div className="tools-section">
            <div className="glossary-term">Install new-fave here</div>
            <div className="muted small">
              new-fave is a normal Python package, so Vowelchemy can install it into its own
              environment (a few minutes; needs internet).
            </div>
          </div>
          {nf?.available ? (
            <div className="muted small">Already installed — nothing to do.</div>
          ) : canInstallNewfave ? (
            <button className="btn" onClick={startInstall} disabled={busy || install.running}>
              {install.running ? <span className="spinner" /> : '⬇️ '} Install new-fave
            </button>
          ) : (
            <div className="muted small">{data?.install?.newfave?.reason}</div>
          )}
          {install.job && (
            <>
              <div className="muted small">
                {install.running
                  ? install.job.phase ?? 'installing…'
                  : install.job.status === 'done'
                    ? '✓ finished — the status above refreshes automatically'
                    : ''}
              </div>
              <LogBox text={install.job.log ?? ''} />
            </>
          )}
          {install.job?.status === 'error' && <Notice kind="error">{install.job.error}</Notice>}
          {install.error && <Notice kind="error">{install.error}</Notice>}

          {/* 3 · MFA has to come from conda */}
          <div className="tools-section">
            <div className="glossary-term">Install MFA (needs conda or mamba)</div>
            <div className="muted small">
              MFA can't be installed with pip — the Kaldi engine it uses is published only through
              conda-forge. Run this once in a terminal, then come back and pick the new
              <code> aligner</code> environment above.
            </div>
          </div>
          <LogBox text={MAMBA_CMD} />
          <div className="row">
            <button className="btn btn-small" onClick={copyCmd}>
              {copied ? '✓ Copied' : '📋 Copy command'}
            </button>
          </div>
          <div className="muted small">
            Afterwards, download the English models with{' '}
            <code>mfa model download acoustic english_us_arpa</code> and{' '}
            <code>mfa model download dictionary english_us_arpa</code> (or let stage 2 do it).
          </div>

          {data?.app && (
            <div className="muted small app-info">
              Running Vowelchemy {data.app.version} · Python {data.app.python}
              <br />
              <span className="mono">{data.app.location}</span>
            </div>
          )}
        </div>
      </div>

      {picking && (
        <FolderPicker
          title="Pick a conda/mamba environment folder"
          startPath={data?.selected ?? undefined}
          onPick={(p) => {
            setPicking(false)
            void choose(p)
          }}
          onClose={() => setPicking(false)}
        />
      )}
    </div>
  )
}
