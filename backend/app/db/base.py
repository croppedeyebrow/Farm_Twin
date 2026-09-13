"""
SQLAlchemy Declarative Base (1단계 Day 2).

2단계부터 Site/Farm/Room/Rack 등 ORM 모델이 이 Base 를 상속한다.
Alembic `env.py` 의 target_metadata 도 이 메타데이터를 본다.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """모든 ORM 모델의 공통 부모. 1단계에서는 모델이 아직 없다."""
