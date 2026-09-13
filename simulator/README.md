# simulator

가상 센서 생성·실내 환경 상태전이·액추에이터 효과를 담당하는 worker.

## 현재 (3단계 Day 8)

순수 도메인 계약은 API 패키지와 공유한다.

- `backend/app/domain/simulation/clock.py` — SimulationClock
- `backend/app/domain/simulation/weather.py` — API/REPLAY/SYNTHETIC adapter
- `backend/app/domain/simulation/state.py` — InitialEnvironmentState

이후 Day 9~11 에서 이 디렉터리에 runner·상태전이·센서 noise 를 붙인다.

## 원칙

- API 와 책임을 분리한다 (별도 프로세스/컨테이너).
- 기능 시뮬레이션과 대량 부하 생성은 분리한다.
- 동일 seed + 동일 입력이면 결과가 같아야 한다.
