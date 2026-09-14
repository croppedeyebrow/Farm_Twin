"""
실시간 WebSocket 패키지 (5단계 Day 16).

=============================================================================
왜 이 패키지가 필요한가
-----------------------------------------------------------------------------
4단계까지는 폐쇄 루프가 **도메인/DB 안**에서만 증명됐다.
5단계는 그 결과를 브라우저 관제 화면이 **1~2초 간격으로** 받아야 한다.

REST polling 만으로는
  - 부하가 커지고
  - 이벤트 순서를 클라이언트가 재구성하기 어렵다.
그래서 farm 단위 WebSocket 스트림 + envelope/sequence 계약을 둔다.

모듈 구성
---------
  envelope.py   — JSON 한 건의 공통 포장·스키마 버전·이벤트 타입
  manager.py    — farm_id → 소켓 집합, sequence 발급, fan-out
  publisher.py  — commit 이후 best-effort 발행 API (services 가 호출)
  routes.py     — `/ws/farms/{farm_id}` 연결 수명

계층 (백엔드 설계)
-----------------
  routers/services  →  (commit)  →  publisher  →  ConnectionManager
  domain/* 는 I/O·WebSocket 을 모른다.

불변조건
--------
DB commit **성공 전** 에 push 하지 않는다.
(시간_컬럼_의미.md / 백엔드 설계 7절)

Day 17 과의 경계
----------------
Day 16: 서버 manager + envelope + commit-then-push
Day 17: REST snapshot(stream_sequence) + 클라 재연결·백오프 + sequence 갭 시 snapshot 복구
        (서버 replay 버퍼 없음 — 누락은 REST 로 latest 재정렬)
"""
