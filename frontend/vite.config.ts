/**
 * Vite 설정 (1단계 Day 2, 5단계 Day 17 `/ws` 프록시).
 *
 * `/api` 프록시: 브라우저가 CORS 없이 REST 호출.
 *   `/api/health` → 백엔드 `/health` (Nginx strip 과 동일)
 *
 * `/ws` 프록시 (Day 17): 관제 WebSocket.
 *   `ws://localhost:5173/ws/farms/{id}` → `ws://127.0.0.1:8000/ws/farms/{id}`
 * Compose 에서는 Nginx 가 `/ws/` Upgrade 를 담당하므로
 * 프로덕션 빌드는 같은 경로 관례만 유지하면 된다.
 */
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

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
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
})
