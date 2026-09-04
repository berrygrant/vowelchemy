export interface ToolInfo {
  available: boolean
  version: string | null
  hint: string
  path?: string | null
}

export interface Status {
  tools: { mfa: ToolInfo; newfave: ToolInfo; phontrast: ToolInfo }
  data: {
    loaded: boolean
    n_tokens: number
    n_speakers: number
    norm_method: string
    schema: Record<string, string>
    tracks_loaded?: boolean
    remove_outliers?: boolean
  }
  browse_confined?: boolean
  tool_env?: string | null
  app?: AppInfo
}

export interface AppInfo {
  version: string
  location: string
  python: string
  executable: string
  frozen: boolean
  webui: string | null
}

export interface ToolEnvironment {
  path: string
  name: string
  source: string
  tools: string[]
}

export interface ToolsPayload {
  tools: { mfa: ToolInfo; newfave: ToolInfo }
  selected: string | null
  selected_locked?: boolean
  install: Record<string, { possible: boolean; reason: string }>
  app: AppInfo
  environments?: ToolEnvironment[]
}

export interface TablePayload {
  columns: string[]
  records: Record<string, unknown>[]
  n_total: number
  n_shown: number
  norm_notes?: string[]
}

export interface VowelInfo {
  vowel: string
  label: string
  keyword?: string
  lexset?: string
  n: number
}

export interface GlossaryTerm {
  term: string
  definition: string
}

export interface Project {
  name: string
  has_vowels: boolean
  has_tracks: boolean
  modified: number
}

export interface NormMethod {
  key: string
  label: string
  description: string
  units: string
}

export interface CorpusItem {
  stem: string
  speaker: string
  audio: string | null
  transcript: string | null
  aligned: boolean
}

export interface ScanResult {
  summary: Record<string, number>
  fully_aligned: boolean
  warnings: string[]
  items: CorpusItem[]
  existing_vowel_csvs: string[]
}

export interface GroupingColumns {
  columns: string[]
  values: Record<string, string[]>
  context_columns?: string[]
  norm_formants: string[]
}

export interface SeparationResult {
  builtin: TablePayload | null
  figure_bar: PlotlyFigure | null
  figure_matrix: PlotlyFigure | null
  full_csv?: string
  phontrast: {
    ok?: boolean
    log?: string
    notes?: string[]
    table?: TablePayload | null
    error?: string
  } | null
}

export interface LayoutSuggestion {
  root: string
  audio_dir: string | null
  transcript_dir: string | null
  aligned_dir: string | null
  speakers_csv: string | null
  counts: { wav: number; transcript: number; aligned: number }
  audio_dirs: string[]
  transcript_dirs: string[]
  aligned_dirs: string[]
  vowel_csvs: string[]
}

export interface BrowseEntry {
  name: string
  path: string
  has_wav?: boolean
  has_transcript?: boolean
}

export interface BrowseResult {
  path: string
  parent: string | null
  home: string
  dirs: BrowseEntry[]
  files: { name: string; path: string }[]
}

export interface JobSnapshot {
  id: string
  kind: string
  status: 'running' | 'done' | 'error'
  phase: string | null
  percent: number | null
  log: string
  result: Record<string, unknown> | null
  error: string | null
}

export type PlotlyFigure = { data: unknown[]; layout: Record<string, unknown> }

export type Stage = 'corpus' | 'align' | 'extract' | 'dataset' | 'visualize' | 'separation'

export interface Ctx {
  status: Status | null
  refresh: () => Promise<void>
  dark: boolean
  go: (s: Stage) => void
}
