import { useState } from 'react'
import { api } from '../api'
import type { Ctx } from '../types'
import { Button, Card, Field, LogBox, Notice } from '../components/ui'

export function ExtractStage({ ctx }: { ctx: Ctx }) {
  const nf = ctx.status?.tools.newfave
  const [alignedDir, setAlignedDir] = useState('')
  const [outputDir, setOutputDir] = useState('')
  const [excludeOverlaps, setExcludeOverlaps] = useState(true)
  const [csvPath, setCsvPath] = useState('')
  const [log, setLog] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notes, setNotes] = useState<string[]>([])

  const run = async () => {
    setBusy(true)
    setError('')
    setNotes([])
    try {
      const res = await api.post('/api/extract', {
        aligned_dir: alignedDir || null,
        output_dir: outputDir || null,
        exclude_overlaps: excludeOverlaps,
      })
      setLog(res.log)
      setNotes(res.notes || [])
      await ctx.refresh()
      if (res.ok) ctx.go('dataset')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
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
        <div className="row-between">
          <input
            className="grow"
            value={csvPath}
            onChange={(e) => setCsvPath(e.target.value)}
            placeholder="/path/to/vowels.csv (on the server)"
          />
          <Button onClick={loadCsv} disabled={!csvPath} busy={busy}>
            Load path
          </Button>
        </div>
        <div className="row-between">
          <span className="muted small">…or upload a CSV from your computer</span>
          <input
            type="file"
            accept=".csv,.tsv"
            onChange={(e) => e.target.files?.[0] && uploadCsv(e.target.files[0])}
          />
        </div>
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
              <input value={alignedDir} onChange={(e) => setAlignedDir(e.target.value)} />
            </Field>
            <Field label="Output folder for measurements">
              <input value={outputDir} onChange={(e) => setOutputDir(e.target.value)} />
            </Field>
          </div>
          <label className="checkbox">
            <input type="checkbox" checked={excludeOverlaps} onChange={(e) => setExcludeOverlaps(e.target.checked)} />
            Exclude overlapping speech
          </label>
          <Button primary onClick={run} busy={busy}>
            ▶️ Extract vowels
          </Button>
          {error && <Notice kind="error">{error}</Notice>}
          {notes.map((n, i) => (
            <Notice kind="warn" key={i}>
              {n}
            </Notice>
          ))}
          <LogBox text={log} />
        </Card>
      )}
    </div>
  )
}
