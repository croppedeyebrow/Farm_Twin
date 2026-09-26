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


class CropKind(StrEnum):
    """
    작물 종류.

    목적: 구역 프로필·생육 점수·추정 Brix 기준값을 가르는 키.
    이유: 딸기/포도를 문자열 ad-hoc 비교하면 setpoint 분리가 깨지기 쉽다.
    """

    STRAWBERRY = "strawberry"
    GRAPE = "grape"


class ZoneId(StrEnum):
    """
    Farm 내부 재배 구역 ID.

    목적: strawberry_zone / grape_zone 을 API·도메인·UI가 같은 문자열로 공유.
    이유: 한 룸 안에서도 관수 밸브·병해 규칙을 구역 단위로 분리해야 함.
    """

    STRAWBERRY = "strawberry_zone"
    GRAPE = "grape_zone"


class SensorType(StrEnum):
    """
    가상 센서 종류.

    룸 공통 5종 + 구역 MVP 확장(배지 EC/온도·양액 pH·엽면습윤·유량).
    `units.SENSOR_DEFAULT_UNIT` / `SENSOR_VALUE_RANGE` 키로도 사용한다.

    확장 이유: 온·습·배지수분만으로는 VPD/DLI/병해/양액 폐쇄루프를
    구성할 수 없다 (작물 구역 설계 문서 §1·§5).
    """

    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO2 = "co2"
    SUBSTRATE_MOISTURE = "substrate_moisture"
    PPFD = "ppfd"  # Photosynthetic Photon Flux Density
    # --- crop-zone MVP: 근권·양액·병해·관수 검증 ---
    SUBSTRATE_EC = "substrate_ec"  # 비료 농도 / 염류
    SUBSTRATE_TEMPERATURE = "substrate_temperature"  # 근권 냉난·관수 보정
    NUTRIENT_PH = "nutrient_ph"  # 산·알칼리 도징
    LEAF_WETNESS = "leaf_wetness"  # 누적 분 — Botrytis 등 병해 입력
    IRRIGATION_FLOW = "irrigation_flow"  # L/min — 관수 검증·누수


class ActuatorType(StrEnum):
    """
    가상 액추에이터 종류.

    ControlRule.target_actuator_type / ControlCommand 대상 설비와 대응한다.
    구역 밸브·순환팬·도징·차광·천창은 작물 구역 폐쇄루프 MVP용.
    """

    HVAC = "hvac"  # 냉난방기
    VENTILATION_FAN = "ventilation_fan"
    DEHUMIDIFIER = "dehumidifier"
    IRRIGATION_PUMP = "irrigation_pump"
    LED = "led"
    # --- crop-zone MVP ---
    CIRCULATION_FAN = "circulation_fan"  # 수관·결로 / 병해 완화
    HUMIDIFIER = "humidifier"
    ZONE_VALVE_STRAWBERRY = "zone_valve_strawberry"  # 딸기만 관수
    ZONE_VALVE_GRAPE = "zone_valve_grape"
    DOSING_PUMP = "dosing_pump"  # A/B·산·알칼리 (MVP 단일)
    SHADE_CURTAIN = "shade_curtain"
    VENT_MOTOR = "vent_motor"  # 천창·측창·문 개도


class Unit(StrEnum):
    """
    측정·상태 값의 물리 단위.

    정규화 후 저장 단위는 CELSIUS / PERCENT / PPM / MICROMOLE_PER_M2_S 등.
    FAHRENHEIT 는 ingest 입력용이며 저장 `unit` 으로는 쓰지 않는다.
    EC/pH/분/유량/VPD/DLI 단위는 구역 MVP·파생값용.
    """

    CELSIUS = "C"
    FAHRENHEIT = "F"  # input-only → CELSIUS 로 정규화
    PERCENT = "%"
    PPM = "ppm"
    MICROMOLE_PER_M2_S = "umol/m2/s"  # PPFD
    RATIO = "ratio"  # 0~1 출력 비율 (액추에이터 duty 등)
    ON_OFF = "on_off"  # 0/1
    MS_PER_CM = "mS/cm"  # EC
    PH = "pH"
    MINUTES = "min"
    LITER_PER_MIN = "L/min"
    KPA = "kPa"  # VPD 등 파생값
    MOL_PER_M2_DAY = "mol/m2/d"  # DLI


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
    MANUAL = "manual"  # 운영자 UI 점유 — 자동 규칙 START/STOP 강등용 (Day14 게이트와 정렬)


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
