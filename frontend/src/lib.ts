// Small shared utilities used across stages.

import type { GroupingColumns, TablePayload } from './types'

// Columns that identify the vowel/speaker rather than a sociodemographic
// factor — excluded when offering "group by" choices in Visualize/Separation.
export const NON_GROUPING_COLUMNS = ['vowel_label', 'vowel_canon', 'speaker', 'vowel']

export function groupableColumns(grouping: GroupingColumns | null): string[] {
  return (grouping?.columns ?? []).filter((c) => !NON_GROUPING_COLUMNS.includes(c))
}

// Trigger a browser download of an in-memory blob.
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function saveText(text: string, filename: string, type = 'text/csv'): void {
  saveBlob(new Blob([text], { type }), filename)
}

// RFC-4180 CSV serialization of a table payload (proper quote doubling —
// JSON.stringify escaping is NOT valid CSV).
export function toCsv(table: Pick<TablePayload, 'columns' | 'records'>): string {
  const cell = (v: unknown): string => {
    if (v === null || v === undefined) return ''
    const s = String(v)
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const head = table.columns.map(cell).join(',')
  const rows = table.records.map((r) => table.columns.map((c) => cell(r[c])).join(','))
  return [head, ...rows].join('\n')
}
