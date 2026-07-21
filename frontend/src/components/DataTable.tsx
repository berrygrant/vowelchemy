import type { TablePayload } from '../types'

function fmt(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return String(v)
    return Math.abs(v) < 1e-4 || Math.abs(v) >= 1e6 ? v.toExponential(2) : v.toFixed(3)
  }
  return String(v)
}

export function DataTable({ table, maxRows = 200 }: { table: TablePayload; maxRows?: number }) {
  const rows = table.records.slice(0, maxRows)
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {table.columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {table.columns.map((c) => (
                <td key={c}>{fmt(r[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {table.n_total > rows.length && (
        <p className="muted small">
          Showing {rows.length.toLocaleString()} of {table.n_total.toLocaleString()} rows.
        </p>
      )}
    </div>
  )
}
