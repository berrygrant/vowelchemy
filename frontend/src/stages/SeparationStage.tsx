import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Ctx, GroupingColumns, SeparationResult, VowelInfo } from '../types'
import { Button, Card, Field, LogBox, MultiSelect, Notice } from '../components/ui'
import { DataTable } from '../components/DataTable'
import { PlotlyChart } from '../components/PlotlyChart'

const EXCLUDE = ['vowel_label', 'vowel_canon', 'speaker', 'vowel']
const DIMS: Record<string, string[] | null> = {
  'F1 × F2': null,
  'F1 only': ['F1_norm'],
  'F2 only': ['F2_norm'],
}

function downloadText(text: string, filename: string) {
  const blob = new Blob([text], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function SeparationStage({ ctx }: { ctx: Ctx }) {
  const loaded = ctx.status?.data.loaded
  const phonjsdOk = ctx.status?.tools.phonjsd.available
  const [vowels, setVowels] = useState<VowelInfo[]>([])
  const [grouping, setGrouping] = useState<GroupingColumns | null>(null)
  const [selVowels, setSelVowels] = useState<string[]>([])
  const [groupBy, setGroupBy] = useState('')
  const [dimsOpt, setDimsOpt] = useState('F1 × F2')
  const [engine, setEngine] = useState('builtin')
  const [withCI, setWithCI] = useState(false)
  const [withP, setWithP] = useState(false)
  const [result, setResult] = useState<SeparationResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!loaded) return
    ;(async () => {
      try {
        const [v, g] = await Promise.all([api.get('/api/vowels'), api.get('/api/grouping-columns')])
        setVowels(v)
        setGrouping(g)
        setSelVowels((cur) => (cur.length ? cur : (v as VowelInfo[]).slice(0, 4).map((x) => x.vowel)))
      } catch (e) {
        setError((e as Error).message)
      }
    })()
  }, [loaded])

  const compute = async () => {
    setBusy(true)
    setError('')
    try {
      const res = (await api.post('/api/separation', {
        vowels: selVowels,
        group_by: groupBy || null,
        dims: DIMS[dimsOpt],
        engine,
        bootstrap: withCI ? 200 : 0,
        permutations: withP ? 500 : 0,
        dark: ctx.dark,
      })) as SeparationResult
      setResult(res)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!loaded) {
    return (
      <div className="stage">
        <h1>6 · Separation metrics (phonJSD)</h1>
        <Notice kind="info">Build a dataset in stage 4 first.</Notice>
      </div>
    )
  }

  const demoCols = (grouping?.columns ?? []).filter((c) => !EXCLUDE.includes(c))
  const pj = result?.phonjsd

  return (
    <div className="stage">
      <h1>6 · Separation metrics (phonJSD)</h1>
      <p className="muted">
        Jensen-Shannon Divergence measures how distinguishable two vowels are in normalized formant
        space: <b>1 = fully separated, 0 = merged</b>. Pillai and Bhattacharyya overlap are shown
        alongside for triangulation.
      </p>

      <Card>
        <Field label="Vowels to compare (none = all)">
          <MultiSelect
            options={vowels.map((v) => ({ value: v.vowel, label: v.keyword ?? v.vowel }))}
            selected={selVowels}
            onChange={setSelVowels}
          />
        </Field>
        <div className="grid-3">
          <Field label="Compute within each level of">
            <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
              <option value="">— whole dataset —</option>
              {demoCols.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </Field>
          <Field label="Space">
            <select value={dimsOpt} onChange={(e) => setDimsOpt(e.target.value)}>
              {Object.keys(DIMS).map((k) => (
                <option key={k}>{k}</option>
              ))}
            </select>
          </Field>
          <Field label="Engine" hint={phonjsdOk ? undefined : 'install R + phonJSD for the canonical engine'}>
            <select value={engine} onChange={(e) => setEngine(e.target.value)}>
              <option value="builtin">Built-in (Python)</option>
              {phonjsdOk && <option value="phonjsd">phonJSD (R)</option>}
            </select>
          </Field>
        </div>
        <div className="stat-toggles">
          <label className="checkbox">
            <input type="checkbox" checked={withCI} onChange={(e) => setWithCI(e.target.checked)} />
            bootstrap JSD confidence intervals
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={withP} onChange={(e) => setWithP(e.target.checked)} />
            Pillai permutation p-value
          </label>
          <span className="muted small">(slower)</span>
        </div>
        <Button primary onClick={compute} busy={busy}>
          Compute separation
        </Button>
        {(withCI || withP) && busy && <p className="muted small">Resampling… this can take a bit.</p>}
        {error && <Notice kind="error">{error}</Notice>}
      </Card>

      {pj && pj.error && <Notice kind="warn">{pj.error}</Notice>}
      {pj && pj.table && (
        <Card title="phonJSD results (canonical)">
          <div className="row-between">
            <span className="muted small">from compare_overlap_metrics()</span>
            {result?.phonjsd?.table && (
              <Button onClick={() => downloadText(toCsv(pj.table!), 'vowelchemy_phonjsd.csv')}>
                ⬇️ Download
              </Button>
            )}
          </div>
          <DataTable table={pj.table} />
          <LogBox text={pj.log ?? ''} />
        </Card>
      )}

      {result?.builtin && (
        <Card title={pj?.table ? 'Built-in metrics' : 'Results'}>
          <div className="row-between">
            <span className="muted small">JSD 1 = separated · 0 = merged</span>
            {result.full_csv && (
              <Button onClick={() => downloadText(result.full_csv!, 'vowelchemy_separation.csv')}>
                ⬇️ Download CSV
              </Button>
            )}
          </div>
          <DataTable table={result.builtin} />
        </Card>
      )}

      {result?.figure_bar && (
        <Card>
          <PlotlyChart figure={result.figure_bar} />
        </Card>
      )}
      {result?.figure_matrix && (
        <Card>
          <PlotlyChart figure={result.figure_matrix} height={460} />
        </Card>
      )}
    </div>
  )
}

// Reconstruct CSV text from a table payload (for the phonJSD download).
function toCsv(table: { columns: string[]; records: Record<string, unknown>[] }): string {
  const head = table.columns.join(',')
  const rows = table.records.map((r) =>
    table.columns.map((c) => JSON.stringify(r[c] ?? '')).join(','),
  )
  return [head, ...rows].join('\n')
}
