import { useState } from 'react'
import { api } from '../api'
import type { Ctx, ScanResult } from '../types'
import { Button, Card, Field, Metric, Notice } from '../components/ui'

export function CorpusStage({ ctx }: { ctx: Ctx }) {
  const [audioDir, setAudioDir] = useState('')
  const [transcriptDir, setTranscriptDir] = useState('')
  const [alignedDir, setAlignedDir] = useState('')
  const [speakersPath, setSpeakersPath] = useState('')
  const [scan, setScan] = useState<ScanResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const doScan = async () => {
    setBusy(true)
    setError('')
    try {
      const res = (await api.post('/api/corpus/scan', {
        audio_dir: audioDir,
        transcript_dir: transcriptDir || null,
        aligned_dir: alignedDir || null,
        speakers_path: speakersPath || null,
      })) as ScanResult
      setScan(res)
      await ctx.refresh()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const loadCsv = async (path: string) => {
    setBusy(true)
    setError('')
    try {
      await api.post('/api/voweldata/load', { csv_path: path })
      await ctx.refresh()
      ctx.go('dataset')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const s = scan?.summary
  return (
    <div className="stage">
      <h1>1 · Locate the corpus</h1>
      <p className="muted">
        Point Vowelchemy at your recordings and transcripts. They can live in the same folder,
        separate folders, or per-speaker sub-folders — and the paths may be on a mounted remote
        filesystem (just give the mounted path).
      </p>

      <Card>
        <div className="grid-2">
          <Field label="Audio folder (.wav)">
            <input value={audioDir} onChange={(e) => setAudioDir(e.target.value)} placeholder="/data/corpus/audio" />
          </Field>
          <Field label="Transcript folder" hint="leave blank if same as audio">
            <input value={transcriptDir} onChange={(e) => setTranscriptDir(e.target.value)} placeholder="/data/corpus/texts" />
          </Field>
          <Field label="Aligned TextGrid folder" hint="optional">
            <input value={alignedDir} onChange={(e) => setAlignedDir(e.target.value)} />
          </Field>
          <Field label="Speaker demographics CSV" hint="optional">
            <input value={speakersPath} onChange={(e) => setSpeakersPath(e.target.value)} placeholder="/data/corpus/speakers.csv" />
          </Field>
        </div>
        <Button primary onClick={doScan} busy={busy} disabled={!audioDir}>
          🔍 Scan corpus
        </Button>
        {error && <Notice kind="error">{error}</Notice>}
      </Card>

      {s && (
        <Card title="What we found">
          <div className="metrics">
            <Metric label="Recordings" value={s.recordings} />
            <Metric label="Paired" value={s.paired} />
            <Metric label="Aligned" value={s.aligned} />
            <Metric label="Speakers" value={s.speakers} />
          </div>
          {s.needs_alignment > 0 ? (
            <Notice kind="info">
              {s.needs_alignment} recording(s) still need force-alignment → go to <b>stage 2</b>.
            </Notice>
          ) : scan!.fully_aligned ? (
            <Notice kind="success">Recordings are already force-aligned → skip to <b>stage 3</b>.</Notice>
          ) : null}
          {scan!.warnings.length > 0 && (
            <details className="details">
              <summary>{scan!.warnings.length} warning(s)</summary>
              <ul>
                {scan!.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </details>
          )}
          {scan!.items.length > 0 && (
            <details className="details">
              <summary>Recording list ({scan!.items.length})</summary>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>stem</th>
                      <th>speaker</th>
                      <th>audio</th>
                      <th>transcript</th>
                      <th>aligned</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scan!.items.slice(0, 200).map((it) => (
                      <tr key={it.stem + it.speaker}>
                        <td>{it.stem}</td>
                        <td>{it.speaker}</td>
                        <td>{it.audio ?? '—'}</td>
                        <td>{it.transcript ?? '—'}</td>
                        <td>{it.aligned ? '✓' : ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </Card>
      )}

      {scan && scan.existing_vowel_csvs.length > 0 && (
        <Card title="Existing extracted-vowel files" subtitle="Skip straight to analysis by loading one.">
          {scan.existing_vowel_csvs.map((p) => (
            <div key={p} className="row-between">
              <code className="path">{p}</code>
              <Button onClick={() => loadCsv(p)} busy={busy}>
                Load
              </Button>
            </div>
          ))}
        </Card>
      )}
    </div>
  )
}
