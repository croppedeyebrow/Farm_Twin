/**
 * Vite 설정 (1단계 Day 2).
 *
 * `/api` 프록시는 브라우저가 CORS 없이 백엔드를 호출하게 한다.
 * 요청 경로 `/api/health` → 백엔드 `/health` 로 rewrite 하여
 * Compose Nginx 의 `/api/` strip 규칙과 동일한 호출 형태를 유지한다.
 */
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // `/api/health` → `/health`
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
