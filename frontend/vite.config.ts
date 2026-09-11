import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [vue()],
    server: {
      port: 5173,
      proxy: {
        '/api': apiProxyTarget,
        '/health': apiProxyTarget,
      },
    },
  }
})
