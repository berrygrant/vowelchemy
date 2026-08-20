import { useState } from 'react'
import type { Ctx } from '../types'
import { Button, Card, Field, LogBox, Notice } from '../components/ui'
import { ProgressBar } from '../components/ProgressBar'
import { PathInput } from '../components/PathInput'
import { useJob } from '../hooks/useJob'

export function AlignStage({ ctx }: { ctx: Ctx }) {
  const mfa = ctx.status?.tools.mfa
  const [acoustic, setAcoustic] = useState('english_us_arpa')
  const [dictionary, setDictionary] = useState('english_us_arpa')
  const [numJobs, setNumJobs] = useState(3)
  const [outputDir, setOutputDir] = useState('')
  const [downloadModels, setDownloadModels] = useState(false)
  const { job, error, start, running } = useJob('vowelchemy-job-align', () => ctx.refresh())

  const run = () =>
    start('/api/align', {
      acoustic_model: acoustic,
      dictionary,
      num_jobs: numJobs,
      output_dir: outputDir || null,
      download_models: downloadModels,
    })

  const result = job?.result as { ok?: boolean; n_textgrids?: number } | null | undefined

  return (
    <div className="stage">
      <h1>2 · Force-align with MFA</h1>
      <p className="muted">
        If recordings lack a phone tier, force-align them with the Montreal Forced Aligner.
        Vowelchemy stages the corpus (even across separate folders) and runs <code>mfa align</code>,
        showing live progress.
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
              <PathInput value={outputDir} onChange={setOutputDir} />
            </Field>
          </div>
          <label className="checkbox">
            <input type="checkbox" checked={downloadModels} onChange={(e) => setDownloadModels(e.target.checked)} />
            Download the acoustic model + dictionary first
          </label>
          <Button primary onClick={run} busy={running}>
            ▶️ Run alignment
          </Button>

          {running && <ProgressBar percent={job!.percent} phase={job!.phase} />}
          {error && <Notice kind="error">{error}</Notice>}
          {job?.status === 'done' &&
            (result?.ok ? (
              <Notice kind="success">
                Alignment complete — {result.n_textgrids} TextGrids. Continue to <b>stage 3</b>.
              </Notice>
            ) : (
              <Notice kind="error">MFA did not produce TextGrids. See the log.</Notice>
            ))}
          {job?.status === 'error' && <Notice kind="error">{job.error}</Notice>}
          <LogBox text={job?.log ?? ''} />
        </Card>
      )}
    </div>
  )
}
