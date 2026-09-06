import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { codeInspectorPlugin } from 'code-inspector-plugin'
import path from 'path'

import fs from 'fs'

const antigravityCmd = path.join(
  process.env.LOCALAPPDATA || '',
  'Programs/Antigravity IDE/bin/antigravity-ide.cmd'
)
process.env.CODE_EDITOR =
  process.env.CODE_EDITOR ||
  (fs.existsSync(antigravityCmd) ? antigravityCmd : 'antigravity-ide')

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    codeInspectorPlugin({
      bundler: 'vite',
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/echarts/')) {
            return 'charts'
          }
          if (id.includes('/node_modules/zrender/')) return 'renderer'
        },
      },
    },
  },
})
