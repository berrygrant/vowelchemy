import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Ctx } from '../types'
import { Button, Card, Field, LogBox, Notice } from '../components/ui'
import { ProgressBar } from '../components/ProgressBar'
import { PathInput } from '../components/PathInput'
import { useJob } from '../hooks/useJob'

export function ExtractStage({ ctx }: { ctx: Ctx }) {
  const nf = ctx.status?.tools.newfave
  const [alignedDir, setAlignedDir] = useState('')
  const [outputDir, setOutputDir] = useState('')
  const [excludeOverlaps, setExcludeOverlaps] = useState(true)
  const [csvPath, setCsvPath] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [refreshed, setRefreshed] = useState(false)
  const { job, error: jobError, start, running } = useJob()

  const result = job?.result as { ok?: boolean; n_tokens?: number; notes?: string[] } | null | undefined

  useEffect(() => {
    if (job?.status === 'done' && !refreshed) {
      setRefreshed(true)
      ctx.refresh().then(() => {
        if (result?.ok) ctx.go('dataset')
      })
    }
  }, [job?.status, refreshed, ctx, result])

  const run = () => {
    setRefreshed(false)
    start('/api/extract', {
      aligned_dir: alignedDir || null,
      output_dir: outputDir || null,
      exclude_overlaps: excludeOverlaps,
    })
  }

  const loadCsv = async () => {
    setBusy(true)
    setError('')
    try {
      await api.post('/api/voweldata/load', { csv_path: csvPath })
      await ctx.refresh()
      ctx.go('dataset')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const uploadCsv = async (file: File) => {
    setBusy(true)
    setError('')
    try {
      await api.upload('/api/voweldata/upload', file)
      await ctx.refresh()
      ctx.go('dataset')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stage">
      <h1>3 · Extract vowels with new-fave</h1>
      <p className="muted">
        Measure vowel formants from aligned TextGrids + audio, or load an existing measurement CSV
        (from new-fave, FAVE, NORM, or your own script).
      </p>

      <Card title="Load existing vowel data" subtitle="Already have measurements? Skip extraction.">
        <Field label="Vowel CSV on the server">
          <PathInput value={csvPath} onChange={setCsvPath} mode="file" exts="csv,tsv" placeholder="/path/to/vowels.csv" />
        </Field>
        <div className="row-between">
          <Button onClick={loadCsv} disabled={!csvPath} busy={busy}>
            Load path
          </Button>
          <span className="muted small">or upload from your computer:</span>
          <input
            type="file"
            accept=".csv,.tsv"
            onChange={(e) => e.target.files?.[0] && uploadCsv(e.target.files[0])}
          />
        </div>
        {error && <Notice kind="error">{error}</Notice>}
      </Card>

      {!nf?.available ? (
        <Card>
          <Notice kind="warn">new-fave (<code>fave-extract</code>) was not detected.</Notice>
          <pre className="logbox">{nf?.hint}</pre>
        </Card>
      ) : (
        <Card title="Run extraction">
          <p className="muted">
            new-fave detected: <code>{nf.version}</code>
          </p>
          <div className="grid-2">
            <Field label="Aligned TextGrid folder" hint="blank = use the aligned output">
              <PathInput value={alignedDir} onChange={setAlignedDir} />
            </Field>
            <Field label="Output folder for measurements">
              <PathInput value={outputDir} onChange={setOutputDir} />
            </Field>
          </div>
          <label className="checkbox">
            <input type="checkbox" checked={excludeOverlaps} onChange={(e) => setExcludeOverlaps(e.target.checked)} />
            Exclude overlapping speech
          </label>
          <Button primary onClick={run} busy={running}>
            ▶️ Extract vowels
          </Button>

          {running && <ProgressBar percent={job!.percent} phase={job!.phase} />}
          {jobError && <Notice kind="error">{jobError}</Notice>}
          {job?.status === 'done' && result?.ok && (
            <Notice kind="success">Extracted {result.n_tokens} tokens → stage 4.</Notice>
          )}
          {job?.status === 'done' && !result?.ok && (
            <Notice kind="error">Extraction produced no usable data. See the log.</Notice>
          )}
          {(result?.notes ?? []).map((n, i) => (
            <Notice kind="warn" key={i}>
              {n}
            </Notice>
          ))}
          {job?.status === 'error' && <Notice kind="error">{job.error}</Notice>}
          <LogBox text={job?.log ?? ''} />
        </Card>
      )}
    </div>
  )
}
