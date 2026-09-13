"""
SQLAlchemy 컬럼 타입 헬퍼 (2단계 Day 5).

native PostgreSQL ENUM 을 피하고 VARCHAR + Python Enum 으로 저장한다.
이유:
- Alembic autogenerate 가 ENUM ALTER 에 취약하다
- 값 추가 시 migration 이 단순하다 (VARCHAR length / CHECK 만)
- API·시드·테스트가 Python Enum 만 import 하면 된다
"""

from sqlalchemy import Enum


def str_enum(enum_cls: type, length: int = 32) -> Enum:
    """
    `native_enum=False` 로 VARCHAR 에 enum.value 문자열을 저장한다.

    values_callable 로 member.name 이 아닌 **value** 를 DB 값으로 쓴다.
    (예: SensorType.TEMPERATURE → "temperature")
    """
    return Enum(
        enum_cls,
        values_callable=lambda members: [item.value for item in members],
        native_enum=False,
        length=length,
    )
