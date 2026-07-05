"""
数据库连接管理
==============
SQLAlchemy 引擎与 Session 工厂。
提供 init_db() 初始化函数和 get_db() 获取会话的依赖注入接口。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from typing import Generator

from .config import BaseConfig, DevelopmentConfig

# 全局引擎和 Session 工厂（延迟初始化）
_engine = None
_session_factory = None
SessionLocal = None


def init_db(config: BaseConfig = None) -> None:
    """
    初始化数据库引擎和 Session 工厂。

    应在应用启动时调用一次。如果传入的 config 为 None，
    使用 DevelopmentConfig 作为默认值。

    Args:
        config: 应用配置对象，包含数据库连接信息。
    """
    global _engine, _session_factory, SessionLocal

    if config is None:
        config = DevelopmentConfig()

    db_uri = config.SQLALCHEMY_DATABASE_URI

    # SQLite 不支持连接池参数，需区分处理
    if "sqlite" in db_uri:
        _engine = create_engine(
            db_uri,
            echo=config.DEBUG,
            connect_args={"check_same_thread": False},
        )
    else:
        _engine = create_engine(
            db_uri,
            echo=config.DEBUG,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
        )

    _session_factory = sessionmaker(bind=_engine)
    SessionLocal = scoped_session(_session_factory)


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话（生成器，用于 Flask 请求上下文或 FastAPI 依赖注入）。

    使用方式：
        db = next(get_db())
        try:
            ...
        finally:
            db.close()

    Yields:
        SQLAlchemy Session 实例。
    """
    if SessionLocal is None:
        raise RuntimeError(
            "数据库未初始化，请先调用 init_db() 或使用 create_app() 工厂函数"
        )

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_engine():
    """获取数据库引擎实例（用于 DDL 操作等）。"""
    if _engine is None:
        raise RuntimeError("数据库引擎未初始化，请先调用 init_db()")
    return _engine


def create_tables() -> None:
    """根据 ORM 模型创建所有数据库表（用于开发/测试环境快速建表）。"""
    from .models.database import Base

    if _engine is None:
        raise RuntimeError("数据库引擎未初始化，请先调用 init_db()")

    # 导入所有模型以确保它们注册到 Base.metadata
    from .models import (  # noqa: F401
        Job, User, AnalysisCache, CrawlLog, Company,
        UserProfile, UserPreference, Resume, ResumeTemplate,
    )

    # 创建所有声明的表（checkfirst=True 防止重复创建）
    Base.metadata.create_all(_engine, checkfirst=True)
