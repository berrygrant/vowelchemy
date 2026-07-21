import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import type { PlotlyFigure } from '../types'

// Renders a server-produced Plotly figure. All chart logic lives in the Python
// `visualization` module; this just draws the JSON it returns.
export function PlotlyChart({ figure, height = 500 }: { figure: PlotlyFigure | null; height?: number }) {
  const ref = useRef<HTMLDivElement>(null)

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

  if (!figure) return null
  return <div ref={ref} style={{ width: '100%' }} />
}
