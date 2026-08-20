import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Ctx, GroupingColumns, NormMethod, TablePayload, VowelInfo } from '../types'
import { Button, Card, Field, MultiSelect, Notice } from '../components/ui'
import { DataTable } from '../components/DataTable'
import { useBusy } from '../hooks/useBusy'

const SCHEMA_FIELDS = ['speaker', 'vowel', 'f1', 'f2', 'f3', 'duration', 'word', 'stress']
const NONE = '— none —'

export function DatasetStage({ ctx }: { ctx: Ctx }) {
  const loaded = ctx.status?.data.loaded
  const [columns, setColumns] = useState<string[]>([])
  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [missing, setMissing] = useState<string[]>([])
  const [methods, setMethods] = useState<NormMethod[]>([])
  const [normMethod, setNormMethod] = useState('lobanov')
  const [normUnits, setNormUnits] = useState('')
  const [vowels, setVowels] = useState<VowelInfo[]>([])
  const [grouping, setGrouping] = useState<GroupingColumns | null>(null)
  const [selectedVowels, setSelectedVowels] = useState<string[]>([])
  const [filterCols, setFilterCols] = useState<string[]>([])
  const [filterValues, setFilterValues] = useState<Record<string, string[]>>({})
  const [removeOutliers, setRemoveOutliers] = useState(false)
  const [outlierSd, setOutlierSd] = useState(2.5)
  const [normParams, setNormParams] = useState<{ g_value?: number; corner_high?: string; corner_low?: string }>({})
  const [table, setTable] = useState<TablePayload | null>(null)
  const { busy, error, setError, run } = useBusy()

  const load = useCallback(async () => {
    setError('')
    try {
      const [schemaRes, methodsRes, vowelsRes, groupRes] = await Promise.all([
        api.get('/api/schema'),
        api.get('/api/normalization/methods'),
        api.get('/api/vowels'),
        api.get('/api/grouping-columns'),
      ])
      setColumns(schemaRes.columns)
      setOverrides(schemaRes.schema)
      setMissing(schemaRes.missing_required)
      setMethods(methodsRes)
      setVowels(vowelsRes)
      setGrouping(groupRes)
      setNormMethod(ctx.status?.data.norm_method ?? 'lobanov')
    } catch (e) {
      setError((e as Error).message)
    }
  }, [ctx.status?.data.norm_method, setError])

  useEffect(() => {
    if (loaded) load()
  }, [loaded, load])

  const build = useCallback(
    (vowelsSel = selectedVowels, filtCols = filterCols, filtVals = filterValues) =>
      run(async () => {
        const filters: Record<string, string[]> = {}
        for (const c of filtCols) filters[c] = filtVals[c] ?? grouping?.values[c] ?? []
        const res = (await api.post('/api/dataset', {
          selected_vowels: vowelsSel,
          filters,
          remove_outliers: removeOutliers,
          outlier_sd: outlierSd,
        })) as TablePayload
        setTable(res)
      }),
    [selectedVowels, filterCols, filterValues, grouping, removeOutliers, outlierSd, run],
  )

  // Auto-preview once options are available.
  useEffect(() => {
    if (loaded && grouping && !table) build([], [], {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, grouping])

  const applySchema = () =>
    run(async () => {
      const clean: Record<string, string> = {}
      for (const [k, v] of Object.entries(overrides)) if (v && v !== NONE) clean[k] = v
      const res = await api.post('/api/schema', { overrides: clean })
      setMissing(res.missing_required)
      await ctx.refresh()
      await load()
    })

  const applyNorm = (method: string, params: typeof normParams = normParams) => {
    setNormMethod(method)
    setNormParams(params)
    return run(async () => {
      const res = await api.post('/api/normalization', { method, ...params })
      setNormUnits(res.units)
      await ctx.refresh()
      await build()
    })
  }

  const uploadTable = (endpoint: string) => (file: File) =>
    run(async () => {
      await api.upload(endpoint, file)
      await ctx.refresh()
      await load()
      await build()
    })
  const uploadDemographics = uploadTable('/api/demographics/upload')
  const uploadVowelMap = uploadTable('/api/vowelmap/upload')

  const downloadCsv = () =>
    run(() => api.download('/api/dataset/csv', 'vowelchemy_dataset.csv'))

  if (!loaded) {
    return (
      <div className="stage">
        <h1>4 · Build &amp; download the dataset</h1>
        <Notice kind="info">
          Load or extract vowel data first (stages 1–3), or click <b>Load demo dataset</b> in the
          sidebar.
        </Notice>
      </div>
    )
  }

  const method = methods.find((m) => m.key === normMethod)

  return (
    <div className="stage">
      <h1>4 · Build &amp; download the dataset</h1>
      {error && <Notice kind="error">{error}</Notice>}

      <details className="details card">
        <summary>Column mapping (auto-detected — edit if needed)</summary>
        <div className="grid-3">
          {SCHEMA_FIELDS.map((f) => (
            <Field label={f} key={f}>
              <select
                value={overrides[f] ?? NONE}
                onChange={(e) => setOverrides({ ...overrides, [f]: e.target.value })}
              >
                <option>{NONE}</option>
                {columns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </Field>
          ))}
        </div>
        <Button onClick={applySchema} busy={busy}>
          Apply mapping
        </Button>
        {missing.length > 0 && (
          <Notice kind="error">
            Couldn't auto-find a column for: <b>{missing.join(', ')}</b>. Pick the matching column
            above — e.g. point <code>f1</code> at your first-formant column (often <code>F1</code> or{' '}
            <code>F1_50</code>).
          </Notice>
        )}
      </details>

      <Card title="Prepare">
        <div className="grid-2">
          <Field label="Normalization method" hint={method?.description}>
            <select value={normMethod} onChange={(e) => applyNorm(e.target.value, {})}>
              {methods.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </select>
          </Field>
          {ctx.status && ctx.status.data.n_speakers === 0 && (
            <Field label="Speaker demographics CSV" hint="Sex, Age Group, …">
              <input
                type="file"
                accept=".csv,.tsv"
                onChange={(e) => e.target.files?.[0] && uploadDemographics(e.target.files[0])}
              />
            </Field>
          )}
        </div>

        {normMethod === 'watt_fabricius' && (
          <div className="grid-2">
            <Field label="High corner vowel (FLEECE)">
              <input
                value={normParams.corner_high ?? 'IY'}
                onChange={(e) => applyNorm(normMethod, { ...normParams, corner_high: e.target.value })}
              />
            </Field>
            <Field label="Low corner vowel (TRAP)">
              <input
                value={normParams.corner_low ?? 'AE'}
                onChange={(e) => applyNorm(normMethod, { ...normParams, corner_low: e.target.value })}
              />
            </Field>
          </div>
        )}
        {normMethod === 'labov_anae' && (
          <Field label="Grand mean G" hint="log-mean scaling constant (Telsur = 6.896874)">
            <input
              type="number"
              step="0.0001"
              value={normParams.g_value ?? 6.896874}
              onChange={(e) => applyNorm(normMethod, { ...normParams, g_value: Number(e.target.value) })}
            />
          </Field>
        )}
        {normUnits && <p className="muted small">Units: {normUnits}</p>}

        <div className="grid-2">
          <Field label="Outlier removal" hint="then click Apply & preview">
            <label className="checkbox">
              <input type="checkbox" checked={removeOutliers} onChange={(e) => setRemoveOutliers(e.target.checked)} />
              drop tokens far from their speaker×vowel mean
            </label>
          </Field>
          {removeOutliers && (
            <Field label="Threshold (SD)">
              <input type="number" step="0.5" min={1} value={outlierSd} onChange={(e) => setOutlierSd(Number(e.target.value))} />
            </Field>
          )}
        </div>
        <Field label="Custom vowel-label map (optional)" hint="CSV with columns: code,label — for IPA / non-English coding">
          <input type="file" accept=".csv,.tsv" onChange={(e) => e.target.files?.[0] && uploadVowelMap(e.target.files[0])} />
        </Field>
      </Card>

      <Card title="Choose vowels & filters">
        <Field label="Vowels to keep (none selected = all)">
          <MultiSelect
            options={vowels.map((v) => ({ value: v.vowel, label: `${v.keyword ?? v.vowel} · ${v.n}` }))}
            selected={selectedVowels}
            onChange={setSelectedVowels}
          />
        </Field>
        {grouping && (
          <Field label="Filter by columns">
            <MultiSelect
              options={grouping.columns.map((c) => ({ value: c, label: c }))}
              selected={filterCols}
              onChange={setFilterCols}
            />
          </Field>
        )}
        {filterCols.map((col) => (
          <Field label={`Keep ${col}`} key={col}>
            <MultiSelect
              options={(grouping?.values[col] ?? []).map((v) => ({ value: v, label: v }))}
              selected={filterValues[col] ?? grouping?.values[col] ?? []}
              onChange={(vals) => setFilterValues({ ...filterValues, [col]: vals })}
            />
          </Field>
        ))}
        <Button primary onClick={() => build()} busy={busy}>
          Apply &amp; preview
        </Button>
      </Card>

      {table && (
        <Card title="Result">
          <div className="row-between">
            <p className="muted">
              <b>{table.n_total.toLocaleString()}</b> tokens × {table.columns.length} columns
            </p>
            <Button primary onClick={downloadCsv}>
              ⬇️ Download CSV
            </Button>
          </div>
          {table.norm_notes && table.norm_notes.length > 0 && (
            <details className="details">
              <summary>Normalization notes</summary>
              <ul>
                {table.norm_notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </details>
          )}
          <DataTable table={table} />
        </Card>
      )}
    </div>
  )
}
