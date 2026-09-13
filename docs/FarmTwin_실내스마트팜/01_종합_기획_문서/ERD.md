# ERD — 2단계 도메인 기준선

Alembic revision `c18bc480b9e7_domain_baseline_day7` 과 일치한다.

```mermaid
erDiagram
    sites ||--o{ farms : has
    farms ||--o{ rooms : has
    rooms ||--o{ racks : has
    rooms ||--o{ sensors : has
    rooms ||--o{ actuators : has
    racks ||--o{ sensors : mounts
    farms ||--o{ simulation_runs : runs
    rooms ||--o{ simulation_runs : runs
    rooms ||--o| farm_states : current_true_state
    simulation_runs ||--o{ weather_snapshots : outdoor
    simulation_runs ||--o{ sensor_readings : measures
    sensors ||--o{ sensor_readings : produces
    rooms ||--o{ control_rules : governs
    simulation_runs ||--o{ control_commands : issues
    actuators ||--o{ control_commands : targets
    control_rules ||--o{ control_commands : may_trigger
    control_commands ||--o{ control_events : results
    simulation_runs ||--o{ fault_injections : injects
    sensors ||--o{ fault_injections : affects

    sites {
        uuid id PK
        string name
        geography location
    }
    farms {
        uuid id PK
        uuid site_id FK
        string code
        string name
    }
    rooms {
        uuid id PK
        uuid farm_id FK
        string code
        string name
    }
    racks {
        uuid id PK
        uuid room_id FK
        string code
        float position_x
    }
    sensors {
        uuid id PK
        uuid room_id FK
        uuid rack_id FK
        string sensor_type
        string unit
    }
    actuators {
        uuid id PK
        uuid room_id FK
        string actuator_type
        float output_ratio
    }
    farm_states {
        uuid id PK
        uuid room_id FK
        int version
        float temperature_c
        float simulation_time
    }
    sensor_readings {
        uuid id PK
        uuid sensor_id FK
        uuid simulation_run_id FK
        int sequence
        float value
        float simulation_time
    }
    simulation_runs {
        uuid id PK
        uuid farm_id FK
        uuid room_id FK
        string status
        int random_seed
    }
    weather_snapshots {
        uuid id PK
        uuid simulation_run_id FK
        int sequence
        float outdoor_temperature_c
    }
    control_rules {
        uuid id PK
        uuid room_id FK
        int version
        float start_threshold
        float stop_threshold
    }
    control_commands {
        uuid id PK
        uuid actuator_id FK
        string idempotency_key UK
        string status
    }
    control_events {
        uuid id PK
        uuid command_id FK
        string event_type
    }
    fault_injections {
        uuid id PK
        uuid sensor_id FK
        string fault_type
        bool active
    }
```

## 참값 · 측정값 · 명령 · 결과

| 구분 | 테이블 | 역할 |
|---|---|---|
| 참값 | `farm_states` | 환경 모델이 계산한 내부 상태 |
| 측정값 | `sensor_readings` | 가상 센서 관측 (append-only) |
| 명령 | `control_commands` | 액추에이터 목표 |
| 결과 | `control_events` | 적용·정지·실패 이력 |
