"""
数据库连接配置
==============
功能：管理 SQLAlchemy 数据库引擎、会话工厂和基类。
      支持 MySQL（生产/开发）和 SQLite（测试）两种后端。
输入：配置对象（Settings / Flask Config）
输出：SQLAlchemy Engine、Session 工厂、Base 基类

使用方式：
    from app.models.database import init_db, get_db, Base
    init_db()
    with get_db() as session:
        session.add(job)
        session.commit()
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import QueuePool
from loguru import logger

from app.config import default_config as config

# ======================== SQLAlchemy 基础设施 ========================

# 声明式基类（所有 ORM 模型继承自此类）
Base = declarative_base()

# 数据库引擎（模块级单例）
_engine = None

# 会话工厂
SessionLocal: sessionmaker = None


def get_engine():
    """获取或创建数据库引擎（延迟初始化）。

    首次调用时根据配置创建引擎，后续调用返回已创建的实例。

    Returns:
        sqlalchemy.Engine: 数据库引擎
    """
    global _engine
    if _engine is None:
        db_url = config.SQLALCHEMY_DATABASE_URI

        # 根据数据库类型调整连接池参数
        if "sqlite" in db_url:
            _engine = create_engine(
                db_url,
                echo=config.DEBUG,
                connect_args={"check_same_thread": False},
            )
        else:
            _engine = create_engine(
                db_url,
                echo=config.DEBUG,
                poolclass=QueuePool,
                pool_size=10,
                pool_recycle=3600,  # 连接回收时间（秒）
                pool_pre_ping=True,  # 连接前检测可用性
            )

        logger.info(f"数据库引擎已创建: {db_url.split('@')[-1]}")
    return _engine


def get_session() -> Session:
    """获取一个新的数据库会话。

    Returns:
        Session: SQLAlchemy 会话对象
    """
    global SessionLocal
    if SessionLocal is None:
        engine = get_engine()
        SessionLocal = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
        )
    return SessionLocal()


def get_db():
    """获取数据库会话的上下文管理器（供 Flask 路由使用）。

    使用示例:
        @app.route("/jobs")
        def list_jobs():
            with get_db() as session:
                jobs = session.query(Job).all()
                return jsonify([j.to_dict() for j in jobs])

    Yields:
        Session: 数据库会话，退出时自动关闭
    """
    db = get_session()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库：创建所有 ORM 模型对应的表。

    使用 Base.metadata.create_all() 创建表结构。
    已存在的表不会重复创建（checkfirst 模式）。

    使用示例:
        from app.models.database import init_db
        init_db()  # 创建所有表
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine, checkfirst=True)
    logger.info("数据库表初始化完成")


def drop_db():
    """删除所有 ORM 模型对应的表（仅测试环境使用）。

    警告：此操作不可逆！生产环境禁止调用。
    """
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    logger.warning("所有数据库表已删除")


def reset_db():
    """重置数据库：先删除所有表，再重新创建（仅测试环境使用）。"""
    drop_db()
    init_db()
    logger.info("数据库已重置")
