"""数据库连接与会话管理。"""

from pathlib import Path
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'workhours.db'}")

if DATABASE_URL.startswith("sqlite"):
    Path(DATABASE_URL.removeprefix("sqlite:///"),).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def get_db():
    """为请求提供一个独立数据库会话，并在请求结束后关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
