import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Ctx, GroupingColumns, NormMethod, TablePayload, VowelInfo } from '../types'
import { Button, Card, Field, MultiSelect, Notice } from '../components/ui'
import { DataTable } from '../components/DataTable'

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
  const [table, setTable] = useState<TablePayload | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

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
  }, [ctx.status?.data.norm_method])

  useEffect(() => {
    if (loaded) load()
  }, [loaded, load])

  const build = useCallback(
    async (vowelsSel = selectedVowels, filtCols = filterCols, filtVals = filterValues) => {
      setBusy(true)
      setError('')
      try {
        const filters: Record<string, string[]> = {}
        for (const c of filtCols) filters[c] = filtVals[c] ?? grouping?.values[c] ?? []
        const res = (await api.post('/api/dataset', {
          selected_vowels: vowelsSel,
          filters,
        })) as TablePayload
        setTable(res)
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setBusy(false)
      }
    },
    [selectedVowels, filterCols, filterValues, grouping],
  )

  // Auto-preview once options are available.
  useEffect(() => {
    if (loaded && grouping && !table) build([], [], {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, grouping])

  const applySchema = async () => {
    setBusy(true)
    try {
      const clean: Record<string, string> = {}
      for (const [k, v] of Object.entries(overrides)) if (v && v !== NONE) clean[k] = v
      const res = await api.post('/api/schema', { overrides: clean })
      setMissing(res.missing_required)
      await ctx.refresh()
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const changeNorm = async (method: string) => {
    setNormMethod(method)
    setBusy(true)
    try {
      const res = await api.post('/api/normalization', { method })
      setNormUnits(res.units)
      await ctx.refresh()
      await build()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const uploadDemographics = async (file: File) => {
    setBusy(true)
    try {
      await api.upload('/api/demographics/upload', file)
      await ctx.refresh()
      await load()
      await build()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

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
        {missing.length > 0 && <Notice kind="error">Required columns not mapped: {missing.join(', ')}</Notice>}
      </details>

      <Card title="Prepare">
        <div className="grid-2">
          <Field label="Normalization method" hint={method?.description}>
            <select value={normMethod} onChange={(e) => changeNorm(e.target.value)}>
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
        {normUnits && <p className="muted small">Units: {normUnits}</p>}
      </Card>

      <Card title="Choose vowels & filters">
        <Field label="Vowels to keep (none selected = all)">
          <MultiSelect
            options={vowels.map((v) => ({ value: v.vowel, label: `${v.label}  (n=${v.n})` }))}
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
            <Button primary onClick={() => api.download('/api/dataset/csv', 'vowelchemy_dataset.csv')}>
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
