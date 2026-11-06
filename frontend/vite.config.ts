import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Keep responsive variants and logos independently cacheable, out of startup JS.
  build: { assetsInlineLimit: 0 },
  server: {
    port: 5173,
    proxy: { '/api/v1': 'http://127.0.0.1:8010' },
  },
  test: { environment: 'jsdom', include: ['src/**/*.test.{ts,tsx}'] },
})
