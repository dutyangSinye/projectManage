import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [vue()],
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            const normalizedId = id.replace(/\\/g, '/')
            if (!normalizedId.includes('node_modules')) return undefined
            if (normalizedId.includes('/node_modules/vue/') || normalizedId.includes('/node_modules/@vue/')) {
              return 'vendor-vue'
            }
            if (normalizedId.includes('/node_modules/zrender/')) {
              return 'vendor-zrender'
            }
            if (normalizedId.includes('/node_modules/echarts/')) {
              return 'vendor-echarts'
            }
            return 'vendor'
          },
        },
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': apiProxyTarget,
        '/health': apiProxyTarget,
      },
    },
  }
})
