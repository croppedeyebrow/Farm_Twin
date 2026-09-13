"""
도메인 enum 정의 (2단계 Day 4~6).

역할
----
DB 컬럼, API JSON, 시뮬레이터 설정이 **같은 문자열 값**을 쓰도록
한곳에서 고정한다. `StrEnum` 이라 `.value` 와 직렬화 결과가 일치한다.

저장 방식
---------
PostgreSQL native ENUM 타입은 쓰지 않는다.
`app.db.models.types.str_enum` 이 VARCHAR(+ Python Enum) 로 매핑하고,
필요 시 CHECK 제약으로 값 집합을 보강한다.
(migration / 환경 간 호환이 단순해진다.)

추가 시점
---------
- Day 4: SensorType, ActuatorType, Unit, Reading*, WeatherMode, ActuatorMode
- Day 5: SimulationStatus
- Day 6: Control*, FaultType, RuleComparator
"""

from enum import StrEnum


class SensorType(StrEnum):
    """
    가상 센서 종류.

    기획 문서의 실내 측정 항목과 1:1.
    `units.SENSOR_DEFAULT_UNIT` / `SENSOR_VALUE_RANGE` 키로도 사용한다.
    """

    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO2 = "co2"
    SUBSTRATE_MOISTURE = "substrate_moisture"
    PPFD = "ppfd"  # Photosynthetic Photon Flux Density


class ActuatorType(StrEnum):
    """
    가상 액추에이터 종류.

    ControlRule.target_actuator_type / ControlCommand 대상 설비와 대응한다.
    """

    HVAC = "hvac"  # 냉난방기
    VENTILATION_FAN = "ventilation_fan"
    DEHUMIDIFIER = "dehumidifier"
    IRRIGATION_PUMP = "irrigation_pump"
    LED = "led"


class Unit(StrEnum):
    """
    측정·상태 값의 물리 단위 (정규화 후 저장 단위).

    원본 단위가 달라도 파이프라인에서 여기 값으로 맞춘 뒤 저장한다.
    """

    CELSIUS = "C"
    PERCENT = "%"
    PPM = "ppm"
    MICROMOLE_PER_M2_S = "umol/m2/s"  # PPFD
    RATIO = "ratio"  # 0~1 출력 비율 (액추에이터 duty 등)
    ON_OFF = "on_off"  # 0/1


class ReadingQuality(StrEnum):
    """
    센서 측정 품질 태그.

    데이터엔지니어링 설계 5절. 원시값 삭제가 아니라 품질로 표시한다.
    """

    GOOD = "good"
    SUSPECT = "suspect"
    BAD = "bad"
    MISSING = "missing"
    STALE = "stale"


class ReadingSource(StrEnum):
    """
    측정값 출처.

    기능 시뮬(SIMULATED/REPLAY)과 대량 부하 생성(LOAD_GENERATOR)을
    같은 테이블에 넣더라도 출처로 구분한다.
    """

    SIMULATED = "simulated"
    REPLAY = "replay"
    LOAD_GENERATOR = "load_generator"


class WeatherMode(StrEnum):
    """
    외기 입력 모드 (3단계 Day 8 WeatherAdapter 와 동일 계약).

    - API: 외부 기상 API
    - REPLAY: 저장 시계열 재생
    - SYNTHETIC: 수식 합성
    """

    API = "API"
    REPLAY = "REPLAY"
    SYNTHETIC = "SYNTHETIC"


class ActuatorMode(StrEnum):
    """액추에이터 운전 모드. actuators.mode / 명령 desired_mode 에 사용."""

    OFF = "off"
    ON = "on"
    AUTO = "auto"


class SimulationStatus(StrEnum):
    """SimulationRun 수명주기 (Day 5). 4단계 제어 루프에서 전이한다."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"


class ControlCommandStatus(StrEnum):
    """
    제어 명령 수명주기.

    명령(목표)과 이벤트(적용 결과)를 한 테이블에 합치지 않는다.
    """

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ControlEventType(StrEnum):
    """ControlEvent 에 기록하는 적용 결과 종류."""

    APPLIED = "applied"
    STOPPED = "stopped"
    FAILED = "failed"
    REJECTED = "rejected"


class FaultType(StrEnum):
    """
    센서 고장 주입 유형.

    6단계 정규화 파이프라인과 동일 계약.
    원시 sensor_readings 는 덮어쓰지 않고, 생성 경로에서 적용한다.
    """

    SPIKE = "spike"
    STUCK = "stuck"
    DROPOUT = "dropout"


class RuleComparator(StrEnum):
    """ControlRule 조건 비교 연산자 (metric 값 vs threshold)."""

    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
