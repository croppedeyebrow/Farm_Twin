# infra

Nginx reverse proxy와 배포용 Compose/설정 파일을 둔다.

예정 구조 (1단계 Day 3):

```text
infra/
  nginx/
    nginx.conf   # /, /api, /ws 라우팅
```

공개 진입점은 Nginx만 노출한다. 설계는 `docs/FarmTwin_실내스마트팜/01_종합_기획_문서/04_인프라_네트워크_클라우드_설계.md`를 따른다.
