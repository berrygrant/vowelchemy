import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Ctx, GroupingColumns, SeparationResult, VowelInfo } from '../types'
import { Button, Card, Field, LogBox, MultiSelect, Notice } from '../components/ui'
import { DataTable } from '../components/DataTable'
import { PlotlyChart } from '../components/PlotlyChart'
import { groupableColumns, saveText, toCsv } from '../lib'
import { useBusy } from '../hooks/useBusy'

const DIMS: Record<string, string[] | null> = {
  'F1 × F2': null,
  'F1 only': ['F1_norm'],
  'F2 only': ['F2_norm'],
}

// Bandwidth selectors per engine. The built-in engine ports phontrast's
// `scott.diag` exactly; the R engine defaults to phontrast's `Hpi` plug-in.
const BANDWIDTHS: Record<string, { value: string; label: string }[]> = {
  builtin: [
    { value: 'scott.diag', label: 'Scott, diagonal (phontrast option)' },
    { value: 'scott', label: 'Scott, full covariance' },
  ],
  phontrast: [
    { value: 'Hpi', label: 'Hpi plug-in (phontrast default)' },
    { value: 'Hpi.diag', label: 'Hpi, diagonal' },
    { value: 'Hscv', label: 'Smoothed cross-validation' },
    { value: 'scott.diag', label: 'Scott, diagonal' },
  ],
}

const PLOT_METRICS: { value: string; label: string }[] = [
  { value: 'jsd', label: 'JSD' },
  { value: 'js_distance', label: '√JSD (Jensen–Shannon distance)' },
  { value: 'pillai', label: 'Pillai' },
  { value: 'pillai_eq', label: 'Pillai, balanced-design equivalent' },
  { value: 'bhatt_affinity', label: 'Bhattacharyya affinity' },
  { value: 'percent_overlap', label: 'Overlap (proportion)' },
]

export function SeparationStage({ ctx }: { ctx: Ctx }) {
  const loaded = ctx.status?.data.loaded
  const phontrastOk = ctx.status?.tools.phontrast.available
  const phontrastHint = ctx.status?.tools.phontrast.hint
  const [vowels, setVowels] = useState<VowelInfo[]>([])
  const [grouping, setGrouping] = useState<GroupingColumns | null>(null)
  const [selVowels, setSelVowels] = useState<string[]>([])
  const [groupBy, setGroupBy] = useState('')
  const [dimsOpt, setDimsOpt] = useState('F1 × F2')
  const [engine, setEngine] = useState('builtin')
  const [density, setDensity] = useState('kde')
  const [bw, setBw] = useState('scott.diag')
  const [minTokens, setMinTokens] = useState(20)
  const [withCI, setWithCI] = useState(false)
  const [nBoot, setNBoot] = useState(200)
  const [withP, setWithP] = useState(false)
  const [plotMetric, setPlotMetric] = useState('jsd')
  const [result, setResult] = useState<SeparationResult | null>(null)
  const { busy, error, setError, run } = useBusy()

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
  }, [loaded, setError])

  const chooseEngine = (next: string) => {
    setEngine(next)
    setBw(BANDWIDTHS[next][0].value)
  }

  const compute = (metric = plotMetric) =>
    run(async () => {
      const res = (await api.post('/api/separation', {
        vowels: selVowels,
        group_by: groupBy || null,
        dims: DIMS[dimsOpt],
        engine,
        density,
        bw,
        min_tokens: minTokens,
        bootstrap: withCI ? nBoot : 0,
        permutations: withP ? 500 : 0,
        plot_metric: metric,
        dark: ctx.dark,
      })) as SeparationResult
      setResult(res)
    })

  // Re-plot when the chart metric changes and a quick (non-resampled) result exists.
  const chooseMetric = (metric: string) => {
    setPlotMetric(metric)
    if (result && !busy && !withCI && !withP) void compute(metric)
  }

  if (!loaded) {
    return (
      <div className="stage">
        <h1>6 · Separation metrics (phontrast)</h1>
        <Notice kind="info">Build a dataset in stage 4 first.</Notice>
      </div>
    )
  }

  const demoCols = groupableColumns(grouping)
  const pt = result?.phontrast
  const slow = withCI || withP || engine === 'phontrast'

  return (
    <div className="stage">
      <h1>6 · Separation metrics (phontrast)</h1>
      <p className="muted">
        <b>JSD</b> (Jensen–Shannon divergence) says how distinguishable two vowels are in normalized
        formant space: <b>1 = fully separated, 0 = merged</b>; <b>√JSD</b> is its metric form. The
        <b> Pillai</b> score comes with a p-value, its <b>balanced-design equivalent</b> (
        <code>pillai_eq</code>, which removes the effect of unequal token counts) and the
        sample-size threshold below which merged vowels would land 95% of the time (
        <code>pillai_null_p95</code>). Bhattacharyya affinity, overlap and Mahalanobis distance
        round out the table. Same estimators and column names as phontrast 2.4.1.
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
          <Field
            label="Engine"
            hint={phontrastOk ? undefined : phontrastHint || 'install R + phontrast for the canonical engine'}
          >
            <select value={engine} onChange={(e) => chooseEngine(e.target.value)}>
              <option value="builtin">Built-in (Python port of phontrast)</option>
              {phontrastOk && <option value="phontrast">phontrast (R)</option>}
            </select>
          </Field>
          <Field label="Density" hint="KDE assumes no shape; mvnorm fits one Gaussian per vowel">
            <select value={density} onChange={(e) => setDensity(e.target.value)}>
              <option value="kde">Kernel density (KDE)</option>
              <option value="mvnorm">Gaussian (mvnorm)</option>
            </select>
          </Field>
          <Field label="KDE bandwidth">
            <select value={bw} onChange={(e) => setBw(e.target.value)} disabled={density !== 'kde'}>
              {BANDWIDTHS[engine].map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Minimum tokens per pair" hint="phontrast's min_tokens (both vowels together)">
            <input
              type="number"
              min={4}
              step={1}
              value={minTokens}
              onChange={(e) => setMinTokens(Math.max(4, Number(e.target.value) || 4))}
            />
          </Field>
        </div>
        <div className="stat-toggles">
          <label className="checkbox">
            <input type="checkbox" checked={withCI} onChange={(e) => setWithCI(e.target.checked)} />
            bootstrap CIs for every metric
          </label>
          {withCI && (
            <select
              value={nBoot}
              onChange={(e) => setNBoot(Number(e.target.value))}
              aria-label="bootstrap replicates"
              style={{ width: 'auto' }}
            >
              {[100, 200, 500, 1000].map((n) => (
                <option key={n} value={n}>
                  {n} replicates
                </option>
              ))}
            </select>
          )}
          <label className="checkbox">
            <input type="checkbox" checked={withP} onChange={(e) => setWithP(e.target.checked)} />
            Pillai permutation p-value
          </label>
          <span className="muted small">(slower)</span>
        </div>
        <div className="grid-3">
          <Field label="Chart metric">
            <select value={plotMetric} onChange={(e) => chooseMetric(e.target.value)}>
              {PLOT_METRICS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Button primary onClick={() => compute()} busy={busy}>
          Compute separation
        </Button>
        {slow && busy && <p className="muted small">Resampling… this can take a bit.</p>}
        {error && <Notice kind="error">{error}</Notice>}
      </Card>

      {pt && pt.error && <Notice kind="warn">{pt.error}</Notice>}
      {pt && pt.table && (
        <Card title="phontrast results (canonical)">
          <div className="row-between">
            <span className="muted small">
              from phontrast() + pillai_overlap(proportion_standardized = TRUE), one row per vowel pair
            </span>
            <Button onClick={() => saveText(toCsv(pt.table!), 'vowelchemy_phontrast.csv')}>
              ⬇️ Download
            </Button>
          </div>
          <DataTable table={pt.table} />
          {pt.notes && pt.notes.length > 0 && (
            <Notice kind="info">{pt.notes.join(' ')}</Notice>
          )}
          <LogBox text={pt.log ?? ''} />
        </Card>
      )}
      {pt && !pt.table && !pt.error && (
        <Card title="phontrast results (canonical)">
          <Notice kind="warn">phontrast produced no table — see the log below.</Notice>
          {pt.notes && pt.notes.length > 0 && <Notice kind="info">{pt.notes.join(' ')}</Notice>}
          <LogBox text={pt.log ?? ''} />
        </Card>
      )}

      {result?.builtin && (
        <Card title={pt?.table ? 'Built-in metrics' : 'Results'}>
          <div className="row-between">
            <span className="muted small">
              jsd / js_distance / pillai / pillai_eq: 1 = separated · 0 = merged — bhatt_affinity /
              percent_overlap: 1 = identical · 0 = disjoint
            </span>
            {result.full_csv && (
              <Button onClick={() => saveText(result.full_csv!, 'vowelchemy_separation.csv')}>
                ⬇️ Download CSV (all columns)
              </Button>
            )}
          </div>
          <DataTable table={result.builtin} />
          <p className="muted small">
            A blank <code>pillai_eq</code> means the bias-corrected separation came out negative — a
            near-merger signal in itself. <code>pillai_null_p95</code> is Stanley &amp; Sneller's e/m
            guide: a Pillai at or below it is consistent with merger at this N. The verdict column is a
            house heuristic, not a published threshold — see the glossary.
          </p>
        </Card>
      )}

      {result?.figure_bar && (
        <Card>
          <PlotlyChart figure={result.figure_bar} exportName="vowelchemy_separation" />
        </Card>
      )}
      {result?.figure_matrix && (
        <Card>
          <PlotlyChart figure={result.figure_matrix} height={460} exportName="vowelchemy_separation_matrix" />
        </Card>
      )}
    </div>
  )
}
