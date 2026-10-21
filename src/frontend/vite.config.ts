/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'
import pkg from './package.json' with { type: 'json' }

export default defineConfig(({ mode }) => {
  // Fixed so it matches the access service's CORS origin; fail instead of drifting to the next free port.
  const port = Number(loadEnv(mode, '.', 'FRONTEND_').FRONTEND_PORT ?? 5174)
  // GitHub Pages serves the app under the repository path; `vite build --mode pages` (task frontend:build:pages).
  const pages = mode === 'pages'
  if (pages && !loadEnv(mode, '.', 'VITE_').VITE_ACCESS_URL) {
    throw new Error('VITE_ACCESS_URL must be set for the Pages build')
  }
  return {
    base: pages ? '/yield-lens/' : '/',
    plugins: [react()],
    define: { __APP_VERSION__: JSON.stringify(pkg.version) },
    server: { port, strictPort: true },
    build: {
      // Lazy chunks (the charts) must not match the entry's `index-*.js` in the bundle budget.
      rollupOptions: { output: { chunkFileNames: 'assets/chunk-[hash].js' } },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      exclude: ['**/node_modules/**', '**/dist/**', 'e2e/**'],
    },
  }
})
