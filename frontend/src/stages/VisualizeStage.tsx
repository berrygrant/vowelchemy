import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Ctx, GroupingColumns, PlotlyFigure, VowelInfo } from '../types'
import { Card, Field, MultiSelect, Notice } from '../components/ui'
import { PlotlyChart } from '../components/PlotlyChart'

type Tab = 'cross' | 'space' | 'ridge' | 'traj'
const EXCLUDE = ['vowel_label', 'vowel_canon', 'speaker', 'vowel']
const CONTEXT = ['pre_seg', 'fol_seg', 'pre_word', 'fol_word', 'stress', 'word']

// Prefer a sociodemographic column (Age Group, Sex, …) over phonetic-context
// columns as the default grouping factor.
function preferredGroup(columns: string[]): string {
  const cands = columns.filter((c) => !EXCLUDE.includes(c))
  const score = (c: string) =>
    /age|group/i.test(c) ? 0 : /sex|gender|dialect|region|class|ethnic/i.test(c) ? 1 : CONTEXT.includes(c) ? 3 : 2
  return [...cands].sort((a, b) => score(a) - score(b))[0] ?? columns[0] ?? ''
}

export function VisualizeStage({ ctx }: { ctx: Ctx }) {
  const loaded = ctx.status?.data.loaded
  const [grouping, setGrouping] = useState<GroupingColumns | null>(null)
  const [vowels, setVowels] = useState<VowelInfo[]>([])
  const [tab, setTab] = useState<Tab>('cross')
  const [figure, setFigure] = useState<PlotlyFigure | null>(null)
  const [error, setError] = useState('')
  const [loadingFig, setLoadingFig] = useState(false)

  // controls
  const [crossFormant, setCrossFormant] = useState('F1_norm')
  const [crossX, setCrossX] = useState('')
  const [crossSplit, setCrossSplit] = useState('vowel_label')
  const [crossKind, setCrossKind] = useState('violin')
  const [crossVowels, setCrossVowels] = useState<string[]>([])
  const [spaceColor, setSpaceColor] = useState('vowel_canon')
  const [spaceTokens, setSpaceTokens] = useState(true)
  const [spaceVowels, setSpaceVowels] = useState<string[]>([])
  const [ridgeValue, setRidgeValue] = useState('F1_norm')
  const [ridgeGroup, setRidgeGroup] = useState('')
  const [spaceMode, setSpaceMode] = useState('scatter')
  const [trajKind, setTrajKind] = useState('space')
  const [trajValue, setTrajValue] = useState('F1_norm')
  const [trajVowels, setTrajVowels] = useState<string[]>([])
  const [tracksPath, setTracksPath] = useState('')
  const [loadingTracks, setLoadingTracks] = useState(false)
  const [trajVowelOpts, setTrajVowelOpts] = useState<{ value: string; label: string }[]>([])
  const tracksLoaded = ctx.status?.data.tracks_loaded

  useEffect(() => {
    if (tracksLoaded) {
      api
        .get('/api/tracks/vowels')
        .then((rows: { vowel: string; keyword: string }[]) =>
          setTrajVowelOpts(rows.map((r) => ({ value: r.vowel, label: r.keyword }))),
        )
        .catch(() => {})
    }
  }, [tracksLoaded])

  const loadDemoTracks = async () => {
    setLoadingTracks(true)
    setError('')
    try {
      await api.post('/api/tracks/demo')
      await ctx.refresh()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoadingTracks(false)
    }
  }

  const loadTracksPath = async () => {
    setLoadingTracks(true)
    setError('')
    try {
      await api.post('/api/tracks/load', { csv_path: tracksPath })
      await ctx.refresh()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoadingTracks(false)
    }
  }

  useEffect(() => {
    if (!loaded) return
    ;(async () => {
      try {
        const [g, v] = await Promise.all([api.get('/api/grouping-columns'), api.get('/api/vowels')])
        setGrouping(g)
        setVowels(v)
        const firstDemo = preferredGroup(g.columns)
        setCrossX((x) => x || firstDemo)
        setRidgeGroup((x) => x || firstDemo)
        setCrossFormant((f) => (g.norm_formants.includes(f) ? f : g.norm_formants[0] ?? f))
        setRidgeValue((f) => (g.norm_formants.includes(f) ? f : g.norm_formants[0] ?? f))
        const pref = (v as VowelInfo[]).map((x) => x.vowel)
        setCrossVowels((cur) => (cur.length ? cur : ['IY', 'EH'].filter((x) => pref.includes(x))))
      } catch (e) {
        setError((e as Error).message)
      }
    })()
  }, [loaded])

  const fetchFigure = useCallback(async () => {
    if (!loaded || !grouping) return
    setLoadingFig(true)
    setError('')
    try {
      let fig: PlotlyFigure
      if (tab === 'cross') {
        fig = await api.post('/api/figure/cross', {
          formant: crossFormant,
          x: crossX,
          split: crossSplit,
          kind: crossKind,
          vowels: crossVowels.length ? crossVowels : null,
          dark: ctx.dark,
        })
      } else if (tab === 'space') {
        fig = await api.post('/api/figure/vowel-space', {
          color: spaceColor,
          show_tokens: spaceTokens,
          mode: spaceMode,
          vowels: spaceVowels.length ? spaceVowels : null,
          dark: ctx.dark,
        })
      } else if (tab === 'ridge') {
        fig = await api.post('/api/figure/ridgeline', {
          value: ridgeValue,
          group: ridgeGroup,
          dark: ctx.dark,
        })
      } else {
        // trajectories
        if (!tracksLoaded) {
          setFigure(null)
          setLoadingFig(false)
          return
        }
        fig = await api.post('/api/figure/trajectory', {
          kind: trajKind,
          value: trajValue,
          vowels: trajVowels.length ? trajVowels : null,
          dark: ctx.dark,
        })
      }
      setFigure(fig)
    } catch (e) {
      setError((e as Error).message)
      setFigure(null)
    } finally {
      setLoadingFig(false)
    }
  }, [
    loaded, grouping, tab, crossFormant, crossX, crossSplit, crossKind, crossVowels,
    spaceColor, spaceTokens, spaceMode, spaceVowels, ridgeValue, ridgeGroup,
    trajKind, trajValue, trajVowels, tracksLoaded, ctx.dark,
  ])

  useEffect(() => {
    if (crossX) fetchFigure()
  }, [fetchFigure, crossX])

  if (!loaded) {
    return (
      <div className="stage">
        <h1>5 · Visualize</h1>
        <Notice kind="info">Build a dataset in stage 4 first.</Notice>
      </div>
    )
  }

  const demoCols = (grouping?.columns ?? []).filter((c) => !EXCLUDE.includes(c))
  const formants = grouping?.norm_formants ?? ['F1_norm', 'F2_norm']
  const vowelOpts = vowels.map((v) => ({ value: v.vowel, label: v.keyword ?? v.vowel }))

  return (
    <div className="stage">
      <h1>5 · Visualize</h1>
      <div className="tabs">
        <button className={tab === 'cross' ? 'tab-on' : ''} onClick={() => setTab('cross')}>
          Cross (distribution)
        </button>
        <button className={tab === 'space' ? 'tab-on' : ''} onClick={() => setTab('space')}>
          Vowel space
        </button>
        <button className={tab === 'ridge' ? 'tab-on' : ''} onClick={() => setTab('ridge')}>
          Ridgeline
        </button>
        <button className={tab === 'traj' ? 'tab-on' : ''} onClick={() => setTab('traj')}>
          Trajectories
        </button>
      </div>

      <Card>
        {tab === 'cross' && (
          <>
            <p className="muted">
              Distribution of a formant across a factor — e.g. BET/BEET F1 by Age Group.
            </p>
            <div className="grid-4">
              <Field label="Formant">
                <select value={crossFormant} onChange={(e) => setCrossFormant(e.target.value)}>
                  {formants.map((f) => (
                    <option key={f}>{f}</option>
                  ))}
                </select>
              </Field>
              <Field label="X axis (group)">
                <select value={crossX} onChange={(e) => setCrossX(e.target.value)}>
                  {demoCols.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </Field>
              <Field label="Split / colour">
                <select value={crossSplit} onChange={(e) => setCrossSplit(e.target.value)}>
                  <option value="vowel_label">vowel</option>
                  {demoCols.filter((c) => c !== crossX).map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Style">
                <select value={crossKind} onChange={(e) => setCrossKind(e.target.value)}>
                  <option value="violin">violin</option>
                  <option value="box">box</option>
                  <option value="strip">strip</option>
                </select>
              </Field>
            </div>
            <Field label="Vowels (none = all)">
              <MultiSelect options={vowelOpts} selected={crossVowels} onChange={setCrossVowels} />
            </Field>
          </>
        )}

        {tab === 'space' && (
          <>
            <p className="muted">F2×F1 vowel space with 2-SD confidence ellipses and centroid labels.</p>
            <div className="grid-3">
              <Field label="Colour by">
                <select value={spaceColor} onChange={(e) => setSpaceColor(e.target.value)}>
                  <option value="vowel_canon">vowel</option>
                  {demoCols.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Mode" hint="contour/ellipse suit very large corpora">
                <select value={spaceMode} onChange={(e) => setSpaceMode(e.target.value)}>
                  <option value="scatter">scatter + ellipse</option>
                  <option value="contour">density contour</option>
                  <option value="ellipse">ellipse only</option>
                </select>
              </Field>
              <Field label="Tokens">
                <label className="checkbox">
                  <input type="checkbox" checked={spaceTokens} onChange={(e) => setSpaceTokens(e.target.checked)} disabled={spaceMode !== 'scatter'} />
                  show individual tokens
                </label>
              </Field>
            </div>
            <Field label="Vowels (none = all)">
              <MultiSelect options={vowelOpts} selected={spaceVowels} onChange={setSpaceVowels} />
            </Field>
          </>
        )}

        {tab === 'ridge' && (
          <>
            <p className="muted">Density curves per group level — reveals modality and shift.</p>
            <div className="grid-2">
              <Field label="Formant">
                <select value={ridgeValue} onChange={(e) => setRidgeValue(e.target.value)}>
                  {formants.map((f) => (
                    <option key={f}>{f}</option>
                  ))}
                </select>
              </Field>
              <Field label="Group">
                <select value={ridgeGroup} onChange={(e) => setRidgeGroup(e.target.value)}>
                  {demoCols.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </Field>
            </div>
          </>
        )}

        {tab === 'traj' && (
          <>
            <p className="muted">
              Mean vowel trajectories from formant <b>tracks</b> — diphthongs (PRICE, MOUTH) move,
              monophthongs stay put.
            </p>
            {!tracksLoaded ? (
              <Notice kind="info">
                No trajectory (tracks) data loaded yet.
                <div className="row-between" style={{ marginTop: 8 }}>
                  <button className="btn btn-small" onClick={loadDemoTracks} disabled={loadingTracks}>
                    ✨ Load demo trajectories
                  </button>
                  <input
                    className="grow"
                    value={tracksPath}
                    onChange={(e) => setTracksPath(e.target.value)}
                    placeholder="…or a tracks CSV path on the server"
                  />
                  <button className="btn btn-small" onClick={loadTracksPath} disabled={!tracksPath || loadingTracks}>
                    Load
                  </button>
                </div>
              </Notice>
            ) : (
              <>
                <div className="grid-2">
                  <Field label="View">
                    <select value={trajKind} onChange={(e) => setTrajKind(e.target.value)}>
                      <option value="space">F2×F1 path</option>
                      <option value="time">formant over time</option>
                    </select>
                  </Field>
                  {trajKind === 'time' && (
                    <Field label="Formant">
                      <select value={trajValue} onChange={(e) => setTrajValue(e.target.value)}>
                        {formants.map((f) => (
                          <option key={f}>{f}</option>
                        ))}
                      </select>
                    </Field>
                  )}
                </div>
                <Field label="Vowels (none = all)">
                  <MultiSelect options={trajVowelOpts} selected={trajVowels} onChange={setTrajVowels} />
                </Field>
              </>
            )}
          </>
        )}
      </Card>

      {error && <Notice kind="error">{error}</Notice>}
      <Card>
        {loadingFig && <p className="muted">Rendering…</p>}
        <PlotlyChart figure={figure} />
      </Card>
    </div>
  )
}
