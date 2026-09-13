# simulator

가상 센서 생성·실내 환경 상태전이·액추에이터 효과를 담당하는 worker.

## Day 8~11

| 모듈 | 역할 |
|---|---|
| `backend/app/domain/simulation/clock.py` | SimulationClock |
| `weather.py` | API/REPLAY/SYNTHETIC 외기 |
| `environment.py` | 온·습·CO₂·배지·PPFD 참값 전이 |
| `sensors.py` | offset/noise/delay 측정 (참값 불변) |
| `config/environment_model.toml` | 계수 |
| `simulator/app/runner.py` | start → step loop → stop |

## API (Day 11)

```text
POST /api/simulations/{id}/start|pause|resume|stop
POST /api/simulations/{id}/step   body: {steps, dt_seconds, persist_readings}
```

## 실행

```bash
# DB migrate + seed 후
cd backend
uv run python ../simulator/app/runner.py --steps 60 --dt-seconds 60
```

60×60s = 1시간 가상 시계열 + readings batch.

## 원칙

- 센서 noise 는 `farm_states` 를 바꾸지 않는다.
- 동일 seed + 동일 입력이면 참값·측정 궤적이 같다.
- API 와 worker 는 같은 `services.simulation` 계약을 쓴다.
