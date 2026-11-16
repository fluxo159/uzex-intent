/// <reference types="vitest" />
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_BACKEND || 'http://127.0.0.1:8000'
  const proxy = { '/api': { target, changeOrigin: true, rewrite: (p: string) => p.replace(/^\/api/, '') } }
  return {
    ...(env.VITE_CACHE_DIR ? { cacheDir: env.VITE_CACHE_DIR } : {}),
    plugins: [react()],
    server: { host: '127.0.0.1', port: 5173, proxy },
    preview: { host: '127.0.0.1', port: 4173, proxy },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      testTimeout: 10000,
      pool: 'threads',
    },
  }
})
