"""
도메인 enum 정의 (2단계 Day 4).

문자열 Enum 을 사용해 DB/API/JSON 직렬화 값을 동일하게 맞춘다.
PostgreSQL 에는 SQLAlchemy `Enum(..., values_callable=...)` 또는
`native_enum=False` + VARCHAR + CHECK 로 저장한다 (모델에서 결정).
"""

from enum import StrEnum


class SensorType(StrEnum):
    """가상 센서 종류. 기획 문서의 실내 측정 항목과 1:1."""

    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO2 = "co2"
    SUBSTRATE_MOISTURE = "substrate_moisture"
    PPFD = "ppfd"


class ActuatorType(StrEnum):
    """가상 액추에이터 종류. 제어 명령의 대상 설비."""

    HVAC = "hvac"  # 냉난방기
    VENTILATION_FAN = "ventilation_fan"
    DEHUMIDIFIER = "dehumidifier"
    IRRIGATION_PUMP = "irrigation_pump"
    LED = "led"


class Unit(StrEnum):
    """측정·상태 값의 물리 단위 (정규화 후 저장 단위)."""

    CELSIUS = "C"
    PERCENT = "%"
    PPM = "ppm"
    MICROMOLE_PER_M2_S = "umol/m2/s"  # PPFD
    RATIO = "ratio"  # 0~1 출력 비율 (액추에이터 duty 등)
    ON_OFF = "on_off"  # 0/1


class ReadingQuality(StrEnum):
    """센서 측정 품질. 데이터엔지니어링 설계 5절."""

    GOOD = "good"
    SUSPECT = "suspect"
    BAD = "bad"
    MISSING = "missing"
    STALE = "stale"


class ReadingSource(StrEnum):
    """측정값 출처. 기능 시뮬과 부하 생성을 구분한다."""

    SIMULATED = "simulated"
    REPLAY = "replay"
    LOAD_GENERATOR = "load_generator"


class WeatherMode(StrEnum):
    """외기 입력 모드."""

    API = "API"
    REPLAY = "REPLAY"
    SYNTHETIC = "SYNTHETIC"


class ActuatorMode(StrEnum):
    """액추에이터 운전 모드."""

    OFF = "off"
    ON = "on"
    AUTO = "auto"


class SimulationStatus(StrEnum):
    """시뮬레이션 실행 상태 (Day 5 SimulationRun 에서 사용)."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"


class ControlCommandStatus(StrEnum):
    """제어 명령 수명주기. command 와 event 를 합치지 않는다."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ControlEventType(StrEnum):
    """명령에 대한 적용 결과 이벤트."""

    APPLIED = "applied"
    STOPPED = "stopped"
    FAILED = "failed"
    REJECTED = "rejected"


class FaultType(StrEnum):
    """센서 고장 주입 유형 (6단계 파이프라인과 동일 계약)."""

    SPIKE = "spike"
    STUCK = "stuck"
    DROPOUT = "dropout"


class RuleComparator(StrEnum):
    """규칙 조건 비교 연산자."""

    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
