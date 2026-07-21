// plotly.js-dist-min ships no type declarations; we use it through a thin
// wrapper (PlotlyChart) and only need a handful of functions.
declare module 'plotly.js-dist-min' {
  const Plotly: {
    react: (el: HTMLElement, data: unknown[], layout?: unknown, config?: unknown) => Promise<unknown>
    newPlot: (el: HTMLElement, data: unknown[], layout?: unknown, config?: unknown) => Promise<unknown>
    purge: (el: HTMLElement) => void
    downloadImage: (
      el: HTMLElement,
      opts: { format: 'png' | 'svg' | 'jpeg' | 'webp'; width?: number; height?: number; scale?: number; filename?: string },
    ) => Promise<string>
    Plots: { resize: (el: HTMLElement) => void }
  }
  export default Plotly
}
