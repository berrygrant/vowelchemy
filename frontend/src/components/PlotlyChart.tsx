import { useEffect, useRef, useState } from 'react'
import Plotly from 'plotly.js-dist-min'
import type { PlotlyFigure } from '../types'

// Renders a server-produced Plotly figure. All chart logic lives in the Python
// `visualization` module; this just draws the JSON it returns and offers
// publication-quality exports (R8).
export function PlotlyChart({
  figure,
  height = 500,
  exportName = 'vowelchemy_plot',
  showExport = true,
}: {
  figure: PlotlyFigure | null
  height?: number
  exportName?: string
  showExport?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(2)

  useEffect(() => {
    const el = ref.current
    if (!el || !figure) return
    const layout = { ...(figure.layout || {}), autosize: true, height }
    Plotly.react(el, figure.data, layout, {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    })
  }, [figure, height])

  useEffect(() => {
    const el = ref.current
    return () => {
      if (el) Plotly.purge(el)
    }
  }, [])

  const download = (format: 'png' | 'svg') => {
    if (ref.current) {
      Plotly.downloadImage(ref.current, {
        format,
        filename: exportName,
        scale: format === 'png' ? scale : 1,
        width: 1100,
        height: Math.round((height / 500) * 1100),
      })
    }
  }

  if (!figure) return null
  return (
    <div>
      <div ref={ref} style={{ width: '100%' }} />
      {showExport && (
        <div className="export-row">
          <span className="muted small">Export:</span>
          <button className="btn btn-small" onClick={() => download('png')} aria-label="Download PNG">
            PNG
          </button>
          <button className="btn btn-small" onClick={() => download('svg')} aria-label="Download SVG (vector)">
            SVG
          </button>
          <label className="muted small export-scale">
            scale
            <select value={scale} onChange={(e) => setScale(Number(e.target.value))} aria-label="PNG scale">
              <option value={1}>1×</option>
              <option value={2}>2×</option>
              <option value={3}>3×</option>
              <option value={4}>4×</option>
            </select>
          </label>
        </div>
      )}
    </div>
  )
}
