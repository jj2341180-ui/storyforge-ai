import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served by FastAPI under /voice/ (built into frontend/dist/voice).
export default defineConfig({
  base: '/voice/',
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
