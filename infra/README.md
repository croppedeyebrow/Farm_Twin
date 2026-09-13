# infra

Nginx reverse proxy와 배포용 설정을 둔다.

## 현재 구조

```text
infra/
  nginx/
    nginx.conf   # /, /api/, /ws/ 라우팅
```

로컬 진입점: `http://127.0.0.1:8080` (`compose.yaml`의 `nginx` 서비스)

- `/` → frontend
- `/api/` → FastAPI
- `/ws/` → FastAPI WebSocket
