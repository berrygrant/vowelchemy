import { useState } from 'react'
import { api } from '../api'
import type { Ctx } from '../types'
import { Button, Card, Field, LogBox, Notice } from '../components/ui'

export function AlignStage({ ctx }: { ctx: Ctx }) {
  const mfa = ctx.status?.tools.mfa
  const [acoustic, setAcoustic] = useState('english_us_arpa')
  const [dictionary, setDictionary] = useState('english_us_arpa')
  const [numJobs, setNumJobs] = useState(3)
  const [outputDir, setOutputDir] = useState('')
  const [downloadModels, setDownloadModels] = useState(false)
  const [log, setLog] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [ok, setOk] = useState<boolean | null>(null)

  const run = async () => {
    setBusy(true)
    setError('')
    setOk(null)
    try {
      const res = await api.post('/api/align', {
        acoustic_model: acoustic,
        dictionary,
        num_jobs: numJobs,
        output_dir: outputDir || null,
        download_models: downloadModels,
      })
      setLog(res.log)
      setOk(res.ok)
      await ctx.refresh()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stage">
      <h1>2 · Force-align with MFA</h1>
      <p className="muted">
        If recordings lack a phone tier, force-align them with the Montreal Forced Aligner.
        Vowelchemy stages the corpus (even across separate folders) and runs <code>mfa align</code>.
      </p>

      {!mfa?.available ? (
        <Card>
          <Notice kind="warn">Montreal Forced Aligner was not detected on this machine.</Notice>
          <pre className="logbox">{mfa?.hint}</pre>
        </Card>
      ) : (
        <Card>
          <p className="muted">
            MFA detected: <code>{mfa.version}</code>
          </p>
          <div className="grid-2">
            <Field label="Acoustic model">
              <input value={acoustic} onChange={(e) => setAcoustic(e.target.value)} />
            </Field>
            <Field label="Dictionary">
              <input value={dictionary} onChange={(e) => setDictionary(e.target.value)} />
            </Field>
            <Field label="Parallel jobs">
              <input
                type="number"
                min={1}
                max={32}
                value={numJobs}
                onChange={(e) => setNumJobs(Number(e.target.value))}
              />
            </Field>
            <Field label="Output folder for TextGrids" hint="blank = alongside the corpus">
              <input value={outputDir} onChange={(e) => setOutputDir(e.target.value)} />
            </Field>
          </div>
          <label className="checkbox">
            <input type="checkbox" checked={downloadModels} onChange={(e) => setDownloadModels(e.target.checked)} />
            Download the acoustic model + dictionary first
          </label>
          <Button primary onClick={run} busy={busy}>
            ▶️ Run alignment
          </Button>
          <p className="muted small">Alignment can take a while for large corpora.</p>
          {error && <Notice kind="error">{error}</Notice>}
          {ok === true && (
            <Notice kind="success">Alignment complete — continue to <b>stage 3</b>.</Notice>
          )}
          {ok === false && <Notice kind="error">MFA did not produce TextGrids. See the log.</Notice>}
          <LogBox text={log} />
        </Card>
      )}
    </div>
  )
}
