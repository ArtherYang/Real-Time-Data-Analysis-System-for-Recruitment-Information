"""
职言 - 后端应用
====================================
负责数据采集、处理、分析、API服务。

模块结构：
- api/      : Web接口层，对外提供RESTful API
- crawler/  : 爬虫模块，负责多平台数据采集
- processor/: 数据处理模块，负责清洗、转换、NLP处理
- models/   : 数据模型层，负责数据库ORM定义
- utils/    : 工具函数（响应格式化、错误处理）
"""

__version__ = "0.2.0"
__author__ = "杨昱晨"

import redis as redis_lib
from flask import Flask, jsonify
from flask_cors import CORS

from .config import BaseConfig, DevelopmentConfig, get_config
from .database import init_db, create_tables


def create_app(config: BaseConfig = None) -> Flask:
    """
    Flask 应用工厂函数。

    按照应用工厂模式创建和配置 Flask 实例：
    1. 加载配置
    2. 初始化数据库连接
    3. 注册 CORS 跨域支持
    4. 注册 API 蓝图
    5. 注册错误处理器
    6. 注册健康检查端点

    Args:
        config: 应用配置对象，None时使用默认开发配置。

    Returns:
        配置完成的 Flask 应用实例。
    """
    if config is None:
        config = get_config()

    app = Flask(__name__)
    app.config.from_object(config)

    # JSON 中文支持
    app.config["JSON_AS_ASCII"] = False

    # CORS 跨域支持
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Prometheus 指标中间件
    try:
        from .metrics import setup_metrics
        setup_metrics(app)
    except ImportError:
        pass

    # 初始化数据库（检测 MySQL 是否可用，不可用则直接走 SQLite）
    db_uri = config.SQLALCHEMY_DATABASE_URI
    if "mysql" in db_uri:
        import socket
        # 快速检测 MySQL 端口是否可达
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        mysql_ok = sock.connect_ex((config.DB_HOST, config.DB_PORT)) == 0
        sock.close()
        if not mysql_ok:
            app.logger.warning(f"MySQL {config.DB_HOST}:{config.DB_PORT} 不可达，使用 SQLite 文件存储")
            from .config import TestingConfig
            import os as _os

            class _FileDB(TestingConfig):
                @property
                def SQLALCHEMY_DATABASE_URI(self) -> str:
                    db_path = _os.path.join(
                        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                        "rdas.db"
                    )
                    return f"sqlite:///{db_path}"
            config = _FileDB()

    init_db(config)

    # 注册 API 蓝图
    from .api import api_bp
    app.register_blueprint(api_bp)

    # 注册统一错误处理器
    from .utils.errors import register_error_handlers
    register_error_handlers(app)

    # 自动建表（checkfirst=True，表已存在则跳过）
    with app.app_context():
        try:
            create_tables()
        except Exception as e:
            app.logger.warning(f"建表警告: {e}")

    # ---- 健康检查端点（存活探针） ----
    @app.route("/health")
    def health_check():
        """存活探针：验证服务进程是否运行中。"""
        return jsonify({"status": "ok", "service": "职言 API", "version": __version__})

    # ---- 就绪探针 ----
    @app.route("/ready")
    def readiness_check():
        """就绪探针：验证 DB 和 Redis 是否可达。"""
        checks = {"database": False, "redis": False}

        # 检查数据库连接
        try:
            from .database import get_engine
            from sqlalchemy import text
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = True
        except Exception as e:
            checks["database"] = str(e)

        # 检查 Redis 连接
        try:
            r = redis_lib.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                password=config.REDIS_PASSWORD or None,
                socket_connect_timeout=3,
            )
            r.ping()
            checks["redis"] = True
        except Exception as e:
            checks["redis"] = str(e)

        all_ready = all(v is True for v in checks.values())
        status_code = 200 if all_ready else 503
        return jsonify({"ready": all_ready, "checks": checks}), status_code

    return app
