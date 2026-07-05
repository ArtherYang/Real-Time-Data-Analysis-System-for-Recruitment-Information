"""
Flask 应用工厂
==============
创建并配置 Flask 应用实例，注册蓝图、CORS、错误处理器、Prometheus 指标。

作者: 杨昱晨 (AI生成，待人工审查)
日期: 2026-07-02
"""

import redis as redis_lib
from flask import Flask, jsonify
from flask_cors import CORS

from app.metrics import setup_metrics, update_db_connection_count, update_redis_status
from app.utils.errors import register_error_handlers


def create_app(config_name: str = "default") -> Flask:
    """
    Flask 应用工厂函数

    Args:
        config_name: 配置名称 (default / testing / production) 或配置类实例

    Returns:
        配置完成的 Flask 应用实例
    """
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False  # 支持中文 JSON 输出
    app.config["SECRET_KEY"] = "rdas-dev-secret-key-2026"

    # ---- 应用配置 ----
    _load_config(app, config_name)

    # ---- 数据库初始化（引擎 + 建表） ----
    from app.database import init_db, create_tables, _engine
    if _engine is None:
        from app.config import BaseConfig, TestingConfig
        import os as _os

        # SQLite 文件存储（与 seed 脚本使用同一路径）
        class _SQLiteFileConfig(TestingConfig):
            @property
            def SQLALCHEMY_DATABASE_URI(self) -> str:
                db_path = _os.path.join(
                    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                    "rdas.db"
                )
                return f"sqlite:///{db_path}"

        db_config = config_name if isinstance(config_name, BaseConfig) else None
        try:
            if db_config is not None:
                init_db(db_config)
            else:
                from app.config import get_config
                init_db(get_config(config_name))
            create_tables()
        except Exception as e:
            app.logger.warning(f"数据库初始化失败 ({e})，回退到 SQLite")
            init_db(_SQLiteFileConfig())
            create_tables()

    # ---- CORS 跨域支持 ----
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ---- 全局错误处理器（统一 JSON 响应格式）----
    register_error_handlers(app)

    # ---- Prometheus 指标中间件 ----
    setup_metrics(app)

    # ---- 先导入子模块注册路由，再注册蓝图 ----
    from app.api import analysis  # noqa: F401 — 触发路由注册
    from app.api import export    # noqa: F401 — 触发路由注册
    from app.api import api_bp
    app.register_blueprint(api_bp)

    # ---- 健康检查端点（存活探针） ----
    @app.route("/health")
    def health_check():
        """存活探针：验证服务进程是否运行中。"""
        return jsonify({"status": "ok", "service": "RDAS API", "version": "0.1.0"})

    # ---- 就绪探针 ----
    @app.route("/ready")
    def readiness_check():
        """就绪探针：验证 DB 和 Redis 是否可达，服务就绪才接收流量。"""
        checks = {"database": False, "redis": False}

        # 检查数据库连接
        try:
            from app.database import get_engine
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(conn.default_schema_name)
            checks["database"] = True
            update_db_connection_count(1)
        except Exception as e:
            checks["database"] = str(e)
            update_db_connection_count(0)

        # 检查 Redis 连接
        try:
            from app.config import default_config as cfg
            r = redis_lib.Redis(
                host=cfg.REDIS_HOST,
                port=cfg.REDIS_PORT,
                db=cfg.REDIS_DB,
                password=cfg.REDIS_PASSWORD or None,
                socket_connect_timeout=3,
            )
            r.ping()
            checks["redis"] = True
            update_redis_status(True)
        except Exception as e:
            checks["redis"] = str(e)
            update_redis_status(False)

        all_ready = all(v is True for v in checks.values())
        status_code = 200 if all_ready else 503

        return jsonify({"ready": all_ready, "checks": checks}), status_code

    return app


def _load_config(app: Flask, config_name):
    """从 config 模块加载配置到 Flask app.config。

    Args:
        app: Flask 应用实例
        config_name: 配置名称字符串（'development'/'testing'/'production'）
                     或配置类实例（如 TestingConfig()）
    """
    from app.config import get_config, BaseConfig

    # 支持直接传入配置类实例
    if isinstance(config_name, BaseConfig):
        config = config_name
    else:
        config = get_config(config_name)

    for key in dir(config):
        if key.isupper():
            app.config[key] = getattr(config, key)


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
