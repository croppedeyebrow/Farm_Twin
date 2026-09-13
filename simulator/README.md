# simulator

가상 센서 생성·실내 환경 상태전이·액추에이터 효과를 담당하는 worker.

## 현재

### Day 8~9
- `backend/app/domain/simulation/clock.py` — SimulationClock
- `backend/app/domain/simulation/weather.py` — API/REPLAY/SYNTHETIC adapter
- `backend/app/domain/simulation/environment.py` — 온·습·CO₂ 상태전이

### Day 10
- `environment.py` — 배지수분·PPFD (LED 1차 추적)
- `config/environment_model.toml` — 모델 계수 (튜닝용)
- `config_loader.py` — TOML → EnvironmentModelParams

데모:

```bash
cd backend && uv run python ../simulator/app/demo_clock.py
```

## 이후

- Day 11: 센서 noise·readings 저장·run 제어

## 원칙

- API 와 책임을 분리한다 (별도 프로세스/컨테이너).
- 기능 시뮬레이션과 대량 부하 생성은 분리한다.
- 동일 seed + 동일 입력이면 결과가 같아야 한다.
