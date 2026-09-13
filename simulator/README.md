# simulator

가상 센서 생성·실내 환경 상태전이·액추에이터 효과를 담당하는 worker.

## 현재

### Day 8
- `backend/app/domain/simulation/clock.py` — SimulationClock
- `backend/app/domain/simulation/weather.py` — API/REPLAY/SYNTHETIC adapter
- `backend/app/domain/simulation/state.py` — EnvironmentState / ActuatorInputs

### Day 9
- `backend/app/domain/simulation/environment.py` — 온·습도·CO₂ 상태전이
- `backend/app/domain/simulation/params.py` — MVP 계수 (Day 10 설정 파일화 예정)

데모:

```bash
# repo root 기준, backend 의존성 설치된 환경에서
python -m simulator.app.demo_clock
# 또는
cd simulator && python -m app.demo_clock
```

## 이후

- Day 10: 배지수분·PPFD·계수 설정 파일
- Day 11: 센서 noise·readings 저장·run 제어

## 원칙

- API 와 책임을 분리한다 (별도 프로세스/컨테이너).
- 기능 시뮬레이션과 대량 부하 생성은 분리한다.
- 동일 seed + 동일 입력이면 결과가 같아야 한다.
