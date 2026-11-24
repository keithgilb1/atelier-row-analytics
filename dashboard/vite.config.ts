import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// base: './' makes the build work from any folder or subpath (GitHub Pages, a file share, Vercel).
export default defineConfig({
  plugins: [react()],
  base: './',
  build: { chunkSizeWarningLimit: 900 },
})
