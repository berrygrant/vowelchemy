import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Ctx, ToolsPayload } from '../types'
import { useBusy } from '../hooks/useBusy'
import { useJob } from '../hooks/useJob'
import { FolderPicker } from './FolderPicker'
import { LogBox, Notice, Portal } from './ui'

const MAMBA_CMD = 'mamba create -n aligner -c conda-forge montreal-forced-aligner'
const R_INSTALL_CMD = 'install.packages("phontrast")'

// Aligning and extracting need two outside programs. MFA is conda/mamba-only
// (its Kaldi bindings aren't on PyPI), so the app borrows it from an existing
// environment; new-fave is a pip package, so the app can install it — into
// itself, or into the environment you picked when it can't install into itself
// (the packaged app has no pip of its own). phontrast is an R package: the app
// finds R in the usual places (or where you point it) and can install the
// package into that R.
export function ToolsPanel({ ctx, onClose }: { ctx: Ctx; onClose: () => void }) {
  const [data, setData] = useState<ToolsPayload | null>(null)
  const [picking, setPicking] = useState(false)
  const [pickingR, setPickingR] = useState(false)
  const [copied, setCopied] = useState('')
  const [flash, setFlash] = useState('')
  const { busy, error, setError, run } = useBusy()

  const load = async (refresh = false) => {
    setData(await api.get(`/api/tools/environments${refresh ? '?refresh=true' : ''}`))
  }

  const install = useJob(undefined, (job) => {
    const ok = (job.result as { ok?: boolean } | null)?.ok
    setFlash(ok ? 'new-fave installed.' : '')
    void load(true)
    void ctx.refresh()
  })
  const installR = useJob(undefined, (job) => {
    const ok = (job.result as { ok?: boolean } | null)?.ok
    setFlash(ok ? 'phontrast installed — the R engine is ready in stage 6.' : '')
    void load(true)
    void ctx.refresh()
  })

  useEffect(() => {
    void run(() => load())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const choose = (path: string | null) =>
    run(async () => {
      setFlash('')
      const next: ToolsPayload = await api.post('/api/tools/environment', { path })
      setData(next)
      await ctx.refresh()
      setFlash(
        path
          ? next.tools.mfa.available || next.tools.newfave.available
            ? `Using ${path.split('/').pop()} — ${[
                next.tools.mfa.available ? 'MFA' : '',
                next.tools.newfave.available ? 'new-fave' : '',
              ]
                .filter(Boolean)
                .join(' and ')} ready.`
            : `Using ${path}.`
          : 'Stopped using that environment.',
      )
    })

  const chooseR = (path: string | null) =>
    run(async () => {
      setFlash('')
      const next: ToolsPayload = await api.post('/api/tools/rscript', { path })
      setData(next)
      await ctx.refresh()
      const pt = next.tools.phontrast
      setFlash(
        path
          ? pt.available
            ? `Using R ${pt.r_version} — phontrast ${pt.version} ready.`
            : `Using R ${pt.r_version ?? ''} at ${pt.path} — phontrast is not installed there yet.`
          : 'Back to finding R automatically.',
      )
    })

  const startInstall = () => {
    setFlash('')
    return install.start('/api/tools/install', { tool: 'newfave' })
  }
  const startInstallR = () => {
    setFlash('')
    return installR.start('/api/tools/install', { tool: 'phontrast' })
  }

  const copy = (text: string) => {
    navigator.clipboard?.writeText(text).then(
      () => {
        setCopied(text)
        window.setTimeout(() => setCopied(''), 1800)
      },
      () => setError('Could not copy — select the command and copy it manually.'),
    )
  }

  const mfa = data?.tools.mfa
  const nf = data?.tools.newfave
  const pt = data?.tools.phontrast
  const nfInstall = data?.install?.newfave
  const ptInstall = data?.install?.phontrast
  const envs = data?.environments ?? []
  const rInfo = data?.r
  const rCandidates = rInfo?.candidates ?? []

  const phontrastLine = !pt
    ? '…'
    : pt.available
      ? `${pt.version} · R ${pt.r_version}`
      : pt.probing
        ? 'looking for R…'
        : pt.path
          ? `R ${pt.r_version} found, phontrast ${pt.version ? 'too old' : 'not installed'}`
          : 'R not found'

  return (
    <Portal>
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
              Stages 1 and 4–6 work without these. You only need MFA and new-fave to align and
              measure raw audio yourself — if your lab gave you an extracted vowel CSV, close this
              and load it in stage 3. phontrast is optional: stage 6 has a built-in port of it.
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
              <div>
                {pt?.available ? '🟢' : '⚪'} <b>phontrast</b> (R separation engine, optional) —{' '}
                {phontrastLine}
              </div>
            </div>

            {error && <Notice kind="error">{error}</Notice>}
            {flash && <Notice kind="success">{flash}</Notice>}

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
                <span>
                  Using <code>{data.selected}</code>
                </span>
                {data.selected_locked ? (
                  <span className="muted small">(set by VOWELCHEMY_TOOL_ENV)</span>
                ) : (
                  <button className="btn btn-small" onClick={() => choose(null)} disabled={busy}>
                    Stop using
                  </button>
                )}
              </div>
            )}

            {busy && !data && <div className="muted small">Looking for environments…</div>}

            {envs.length > 0
              ? envs.map((env) => {
                  const inUse = data?.selected === env.path
                  return (
                    <div key={env.path} className={`env-row${inUse ? ' env-row-active' : ''}`}>
                      <div>
                        <div>
                          {inUse ? '✓ ' : ''}
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
                        disabled={busy || inUse}
                      >
                        {inUse ? 'In use' : 'Use this'}
                      </button>
                    </div>
                  )
                })
              : !busy && (
                  <div className="muted small">
                    No environment with MFA or new-fave found automatically — choose a folder
                    below, or install one with the commands further down.
                  </div>
                )}

            <div className="row">
              <button className="btn btn-small" onClick={() => setPicking(true)} disabled={busy}>
                📁 Choose a folder…
              </button>
              <button className="btn btn-small" onClick={() => void run(() => load(true))} disabled={busy}>
                {busy ? <span className="spinner" /> : '↻ '} Scan again
              </button>
            </div>

            {/* 2 · new-fave, which pip can install */}
            <div className="tools-section">
              <div className="glossary-term">Install new-fave</div>
              <div className="muted small">
                new-fave is a normal Python package (needs Python 3.10+), so Vowelchemy can
                install it for you — a few minutes, and it needs an internet connection.
              </div>
            </div>
            {nf?.available ? (
              <div className="muted small">✓ Already installed — nothing to do.</div>
            ) : (
              <>
                {nfInstall?.possible && (
                  <button className="btn" onClick={startInstall} disabled={busy || install.running}>
                    {install.running ? <span className="spinner" /> : '⬇️ '}
                    {nfInstall.target === 'env'
                      ? ` Install new-fave into ${nfInstall.env_name}`
                      : ' Install new-fave'}
                  </button>
                )}
                {!nfInstall?.possible && nfInstall?.reason && (
                  <Notice kind="warn">{nfInstall.reason}</Notice>
                )}
              </>
            )}
            {install.job && (
              <>
                <div className="muted small">
                  {install.running ? install.job.phase ?? 'installing…' : ''}
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
                MFA can't be installed with pip — the Kaldi engine it uses is published only
                through conda-forge. Run this once in a terminal, then come back, press
                <b> Scan again</b>, and pick the new <code>aligner</code> environment above.
              </div>
            </div>
            <LogBox text={MAMBA_CMD} />
            <div className="row">
              <button className="btn btn-small" onClick={() => copy(MAMBA_CMD)}>
                {copied === MAMBA_CMD ? '✓ Copied' : '📋 Copy command'}
              </button>
            </div>
            <div className="muted small">
              Stage 2 can download the English models for you, or run{' '}
              <code>mfa model download acoustic english_us_arpa</code> and{' '}
              <code>mfa model download dictionary english_us_arpa</code> yourself.
            </div>

            {/* 4 · phontrast lives in R */}
            <div className="tools-section">
              <div className="glossary-term">phontrast (R) — optional</div>
              <div className="muted small">
                Stage 6 already computes phontrast's metrics with a built-in port. Installing the
                R package adds the canonical R engine (and its Hpi bandwidth). Vowelchemy looks
                for R in the usual places — the R installer, Homebrew, R.framework, conda
                environments — even when R isn't on the PATH; if it still can't see yours, point
                it at the folder R is installed in.
              </div>
            </div>

            {rInfo?.selected && (
              <div className="tool-selected">
                <span>
                  Using R at <code>{rInfo.selected}</code>
                </span>
                {rInfo.selected_locked ? (
                  <span className="muted small">(set by VOWELCHEMY_RSCRIPT)</span>
                ) : (
                  <button className="btn btn-small" onClick={() => chooseR(null)} disabled={busy}>
                    Find automatically
                  </button>
                )}
              </div>
            )}

            {pt?.probing && <div className="muted small">Looking for R…</div>}

            {rCandidates.length > 0
              ? rCandidates.map((c) => (
                  <div key={c.path} className={`env-row${c.in_use ? ' env-row-active' : ''}`}>
                    <div>
                      <div>
                        {c.in_use ? '✓ ' : ''}
                        <b>R {c.r_version ?? '?'}</b>{' '}
                        <span className="muted small">
                          {c.package
                            ? `${c.package} ${c.version ?? ''}${c.supported ? '' : ' (too old)'}`
                            : 'phontrast not installed'}
                        </span>
                      </div>
                      <div className="muted small mono">{c.path}</div>
                    </div>
                    <button
                      className="btn btn-small"
                      onClick={() => chooseR(c.path)}
                      disabled={busy || c.in_use}
                    >
                      {c.in_use ? 'In use' : 'Use this R'}
                    </button>
                  </div>
                ))
              : !busy &&
                !pt?.probing && (
                  <div className="muted small">
                    No R installation found. Install R from{' '}
                    <code>https://cloud.r-project.org</code>, then press <b>Scan again</b> — or, if
                    R is already installed somewhere unusual, choose its folder below.
                  </div>
                )}

            <div className="row">
              <button className="btn btn-small" onClick={() => setPickingR(true)} disabled={busy}>
                📁 Choose the R folder…
              </button>
              <button className="btn btn-small" onClick={() => void run(() => load(true))} disabled={busy}>
                {busy ? <span className="spinner" /> : '↻ '} Scan again
              </button>
            </div>

            {pt?.available ? (
              <div className="muted small">✓ phontrast {pt.version} is installed in this R — nothing to do.</div>
            ) : (
              <>
                {ptInstall?.possible && (
                  <button className="btn" onClick={startInstallR} disabled={busy || installR.running}>
                    {installR.running ? <span className="spinner" /> : '⬇️ '}
                    {` ${pt?.version ? 'Update' : 'Install'} phontrast into R ${ptInstall.r_version ?? ''}`}
                  </button>
                )}
                {pt?.path && !ptInstall?.possible && ptInstall?.reason && (
                  <Notice kind="warn">{ptInstall.reason}</Notice>
                )}
                {pt?.path && (
                  <div className="muted small">
                    Or, in that R, run <code>{R_INSTALL_CMD}</code>{' '}
                    <button className="btn btn-small" onClick={() => copy(R_INSTALL_CMD)}>
                      {copied === R_INSTALL_CMD ? '✓ Copied' : '📋 Copy'}
                    </button>
                  </div>
                )}
              </>
            )}
            {installR.job && (
              <>
                <div className="muted small">
                  {installR.running ? installR.job.phase ?? 'installing…' : ''}
                </div>
                <LogBox text={installR.job.log ?? ''} />
              </>
            )}
            {installR.job?.status === 'error' && <Notice kind="error">{installR.job.error}</Notice>}
            {installR.error && <Notice kind="error">{installR.error}</Notice>}

            {data?.app && (
              <div className="muted small app-info">
                Running Vowelchemy {data.app.version} · Python {data.app.python}
                <br />
                <span className="mono">{data.app.location}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Siblings, not children: nested inside the backdrop above, every click in
          a picker also closed this panel. */}
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
      {pickingR && (
        <FolderPicker
          title="Pick the folder R is installed in (or a conda environment with R)"
          startPath={rInfo?.selected ?? undefined}
          onPick={(p) => {
            setPickingR(false)
            void chooseR(p)
          }}
          onClose={() => setPickingR(false)}
        />
      )}
    </Portal>
  )
}
