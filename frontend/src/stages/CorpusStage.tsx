import { useState } from 'react'
import { api } from '../api'
import type { Ctx, LayoutSuggestion, ScanResult } from '../types'
import { Button, Card, Field, Metric, Notice } from '../components/ui'
import { PathInput } from '../components/PathInput'

export function CorpusStage({ ctx }: { ctx: Ctx }) {
  const [rootDir, setRootDir] = useState('')
  const [audioDir, setAudioDir] = useState('')
  const [transcriptDir, setTranscriptDir] = useState('')
  const [alignedDir, setAlignedDir] = useState('')
  const [speakersPath, setSpeakersPath] = useState('')
  const [scan, setScan] = useState<ScanResult | null>(null)
  const [detect, setDetect] = useState<LayoutSuggestion | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const autodetect = async () => {
    setBusy(true)
    setError('')
    try {
      const res = (await api.post('/api/corpus/autodetect', { root_dir: rootDir })) as LayoutSuggestion
      setDetect(res)
      if (res.audio_dir) setAudioDir(res.audio_dir)
      if (res.transcript_dir) setTranscriptDir(res.transcript_dir)
      if (res.aligned_dir) setAlignedDir(res.aligned_dir)
      if (res.speakers_csv) setSpeakersPath(res.speakers_csv)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

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
        Point Vowelchemy at your recordings and transcripts. Give a single <b>root folder</b> and
        let it find the sub-folders, or set each path yourself. Paths are on the machine running the
        app (including mounted remote drives), and every field has a <b>Browse…</b> picker.
      </p>

      <Card title="Auto-detect from a root folder">
        <Field label="Root / corpus folder" hint="we'll fuzzy-match the audio, transcript, and aligned sub-folders">
          <PathInput value={rootDir} onChange={setRootDir} placeholder="/data/my_corpus" />
        </Field>
        <Button onClick={autodetect} busy={busy} disabled={!rootDir}>
          🪄 Auto-detect layout
        </Button>
        {detect && (
          <Notice kind={detect.counts.wav > 0 ? 'success' : 'warn'}>
            Found <b>{detect.counts.wav}</b> wav, <b>{detect.counts.transcript}</b> transcript, and{' '}
            <b>{detect.counts.aligned}</b> aligned-TextGrid file(s). Fields below were filled in — adjust
            if needed.
            {detect.vowel_csvs.length > 0 && (
              <> Also spotted {detect.vowel_csvs.length} vowel CSV(s) you can load directly.</>
            )}
          </Notice>
        )}
      </Card>

      <Card title="Corpus paths">
        <div className="grid-2">
          <Field label="Audio folder (.wav)">
            <PathInput value={audioDir} onChange={setAudioDir} placeholder="/data/my_corpus/audio" />
          </Field>
          <Field label="Transcript folder" hint="blank = same as audio">
            <PathInput value={transcriptDir} onChange={setTranscriptDir} />
          </Field>
          <Field label="Aligned TextGrid folder" hint="optional">
            <PathInput value={alignedDir} onChange={setAlignedDir} />
          </Field>
          <Field label="Speaker demographics CSV" hint="optional">
            <PathInput value={speakersPath} onChange={setSpeakersPath} mode="file" exts="csv,tsv" />
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
