# FarmTwin

가상 센서·가상 설비로 실내 재배환경을 만들고, 실시간 관제·규칙 제어·부하테스트로 **폐쇄 제어 루프**를 검증하는 소프트웨어 기반 운영 트윈.

## 범위 (In Scope)

- 가상 센서(온도·습도·CO₂·배지수분·PPFD)와 가상 액추에이터(냉난방·환기·제습·관수·LED)
- FastAPI 기반 상태·명령·이벤트 API와 WebSocket 실시간 관제
- React/Three.js 기반 3D 재배실 관제 UI
- 규칙 엔진 폐쇄 제어 루프와 자동 테스트
- 센서 고장 주입·데이터 품질 경고
- Docker Compose 로컬 기동과 공개 데모 배포
- k6/부하 생성기 기반 부하테스트와 기본 관측성

## 비범위 (Out of Scope)

- 실제 스마트팜 장비·기상센서 연동
- MSA / Kubernetes
- 별도 시계열 DB (MVP는 PostgreSQL)
- 부하테스트를 공개 데모 인스턴스에 직접 실행
- 실제 설비용 안전제어·현장 인증 체계

## Definition of Done (프로젝트)

- [ ] 재현 가능한 환경 시뮬레이션
- [ ] 폐쇄 제어 루프 자동 테스트
- [ ] WebSocket 실시간 관제
- [ ] 센서 고장 주입
- [ ] 부하테스트 리포트
- [ ] 공개 URL
- [ ] README와 아키텍처 문서
- [ ] 2~3분 데모 영상

단계별 DoD는 `docs/FarmTwin_실내스마트팜/02_개발_과정_30일/`를 따른다.  
**1단계 DoD:** 한 명령 기동 · 빈 3D 재배실 · health/DB 연결 · CI 통과

## 런타임 버전 (고정)

| 런타임 | 버전 | 고정 위치 |
|---|---|---|
| Python | **3.12** | `.python-version`, `backend/.python-version`, `.tool-versions` |
| Node.js | **22** | `.nvmrc`, `.node-version`, `.tool-versions`, `frontend/package.json#engines` |
| PostgreSQL / PostGIS | **16 / 3.4** | `compose.yaml` (`postgis/postgis:16-3.4`) |

로컬 Python이 3.12가 아니면 `uv`/`pyenv` 등으로 맞춘다. Node는 `nvm use` 또는 Volta/asdf를 권장한다.

## 저장소 구조

```text
backend/      FastAPI API, SQLAlchemy, Alembic, 테스트
frontend/     React + Vite + TypeScript
simulator/    가상 센서·상태전이 worker (이후 단계)
infra/        Nginx 등 인프라 설정 (이후 단계)
load-tests/   k6·부하 생성기 (이후 단계)
docs/         기획·단계 문서, 브랜치 전략
.github/      CI/CD 워크플로 (이후 단계)
compose.yaml  로컬 Docker Compose
```

## 브랜치 전략

`main` + 단기 `feature/*` / `fix/*` / `chore/*` → PR 병합.  
자세한 규칙은 [docs/브랜치_전략.md](docs/브랜치_전략.md)를 본다.

## 문서

1. [종합 개요](docs/FarmTwin_실내스마트팜/FarmTwin%20실내%20스마트팜%20디지털트윈.md)
2. [종합 기획](docs/FarmTwin_실내스마트팜/01_종합_기획_문서/)
3. [30일 개발 과정](docs/FarmTwin_실내스마트팜/02_개발_과정_30일/)

각 단계 완료 기준을 통과하기 전 다음 단계로 넘어가지 않는다.

## Quick Start

> Day 2~3에서 Compose 전체 기동·Nginx·CI를 붙인 뒤 이 절을 확정한다.

현재(Day 1 기준) 로컬 DB만 Compose로 올릴 수 있다.

```bash
docker compose up -d db
```

API·프론트 통합 기동은 1단계 나머지 작업에서 완성한다.
