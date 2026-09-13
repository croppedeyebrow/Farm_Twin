"""SQLAlchemy 컬럼 타입 헬퍼."""

from sqlalchemy import Enum


def str_enum(enum_cls: type, length: int = 32) -> Enum:
    """
    PostgreSQL native ENUM 대신 VARCHAR + Python Enum 으로 저장한다.

    migration diff 와 환경 간 호환이 단순해진다.
    """
    return Enum(
        enum_cls,
        values_callable=lambda members: [item.value for item in members],
        native_enum=False,
        length=length,
    )
