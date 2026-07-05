"""
应用配置
========
多环境配置类，从环境变量读取敏感信息（数据库连接串等）。

使用方式：
    from config import DevelopmentConfig
    app = create_app(DevelopmentConfig)
"""

import os


class BaseConfig:
    """基础配置 — 所有环境共用"""

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "rdas-dev-secret-key-change-in-production")
    JSON_AS_ASCII = False  # 支持中文 JSON 输出

    # 数据库
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "rdas")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """构建数据库连接 URI。"""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )

    # ======================== Redis 配置 ========================
    REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

    @property
    def REDIS_URL(self) -> str:
        """构造 Redis 连接 URL。"""
        if self.REDIS_PASSWORD:
            return (
                f"redis://:{self.REDIS_PASSWORD}"
                f"@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            )
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ======================== Celery 配置 ========================
    @property
    def CELERY_BROKER_URL(self) -> str:
        """Celery 消息代理 URL（复用 Redis）。"""
        return self.REDIS_URL

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """Celery 结果存储后端（复用 Redis）。"""
        return self.REDIS_URL

    # ======================== 爬虫配置 ========================
    CRAWL_DELAY_MIN = float(os.getenv("CRAWL_DELAY_MIN", "3.0"))
    CRAWL_DELAY_MAX = float(os.getenv("CRAWL_DELAY_MAX", "8.0"))
    CRAWL_MAX_RETRIES = int(os.getenv("CRAWL_MAX_RETRIES", "3"))
    CRAWL_MAX_PAGES = int(os.getenv("CRAWL_MAX_PAGES", "5"))
    CRAWL_USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    ]

    # ======================== 数据处理配置 ========================
    SALARY_MIN_VALID = int(os.getenv("SALARY_MIN_VALID", "1000"))
    SALARY_MAX_VALID = int(os.getenv("SALARY_MAX_VALID", "200000"))
    FUZZY_DEDUP_THRESHOLD = float(os.getenv("FUZZY_DEDUP_THRESHOLD", "0.85"))

    # JWT 认证
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "rdas-jwt-secret-key-must-be-32-bytes-long")
    JWT_ACCESS_TOKEN_EXPIRES = 24 * 3600       # 访问令牌有效期：24小时
    JWT_REFRESH_TOKEN_EXPIRES = 7 * 24 * 3600  # 刷新令牌有效期：7天

    # 分页
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # 登录安全
    MAX_LOGIN_ATTEMPTS = 5          # 最大登录失败次数
    ACCOUNT_LOCK_MINUTES = 15       # 账号锁定时间（分钟）

    # 分析缓存
    CACHE_TTL_SECONDS = 3600        # 缓存有效期：1小时

    # 日志
    LOG_LEVEL = "INFO"
    LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")

    # 环境标识
    ENV = os.getenv("ENV", "development")


class DevelopmentConfig(BaseConfig):
    """开发环境配置"""
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    ENV = "development"


class TestingConfig(BaseConfig):
    """测试环境配置 — 使用内存SQLite避免依赖外部MySQL"""
    DEBUG = True
    TESTING = True
    ENV = "testing"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """测试环境使用 SQLite 内存数据库。"""
        return "sqlite:///:memory:"

    # 测试环境：缩短JWT有效期便于测试
    JWT_ACCESS_TOKEN_EXPIRES = 60
    JWT_REFRESH_TOKEN_EXPIRES = 300


class ProductionConfig(BaseConfig):
    """生产环境配置"""
    DEBUG = False
    LOG_LEVEL = "WARNING"
    ENV = "production"


# 配置字典（存储类，get_config 中实例化）
_config_classes = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(env: str = None) -> BaseConfig:
    """根据环境名称获取配置对象（已实例化的配置实例）。

    Args:
        env: 环境名称（development/testing/production），默认读取 FLASK_ENV

    Returns:
        BaseConfig: 对应环境的配置实例（property 已求值）
    """
    env = env or os.getenv("FLASK_ENV", "development")
    cls = _config_classes.get(env, DevelopmentConfig)
    return cls()


# ======================== 便捷访问 ========================
# 模块级默认配置（非 Flask 上下文使用）
try:
    from dotenv import load_dotenv
    from pathlib import Path

    _ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
except ImportError:
    pass

default_config = get_config()
