/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'
import pkg from './package.json' with { type: 'json' }

export default defineConfig(({ mode }) => {
  // Fixed so it matches the access service's CORS origin; fail instead of drifting to the next free port.
  const port = Number(loadEnv(mode, '.', 'FRONTEND_').FRONTEND_PORT ?? 5174)
  return {
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
