import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// `base: './'` makes built asset paths relative so FastAPI can serve the SPA
// from the app root. In dev, /api is proxied to the uvicorn backend.
export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    // Build INTO the Python package so the UI ships inside the wheel and
    // `pip install vowelchemy && vowelchemy app` serves it from anywhere.
    outDir: '../src/vowelchemy/webui',
    emptyOutDir: true,
    chunkSizeWarningLimit: 4000,
  },
})
