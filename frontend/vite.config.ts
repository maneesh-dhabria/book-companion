import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        // `bookcompanion serve --dev` exports BC_API_PORT so Vite proxies to
        // the port the backend actually bound (auto-bumped if 8000 was busy).
        // Standalone `npm run dev` falls back to 8000.
        target: `http://localhost:${process.env.BC_API_PORT ?? '8000'}`,
        changeOrigin: true,
      },
    },
  },
})
