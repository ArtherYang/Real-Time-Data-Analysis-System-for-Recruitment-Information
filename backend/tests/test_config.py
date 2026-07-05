"""
应用配置模块测试
================
测试 config.py 中的多环境配置类和配置工厂函数。

覆盖范围：
- BaseConfig / DevelopmentConfig / TestingConfig / ProductionConfig 配置属性
- get_config 配置工厂函数
- 环境变量覆盖
"""

import os
import pytest
from unittest.mock import patch

from app.config import (
    BaseConfig,
    DevelopmentConfig,
    TestingConfig,
    ProductionConfig,
    get_config,
)


class TestBaseConfig:
    """基础配置类测试"""

    def test_default_database_uri(self):
        """默认数据库 URI 格式"""
        config = BaseConfig()
        uri = config.SQLALCHEMY_DATABASE_URI
        assert "mysql+pymysql://" in uri
        assert "charset=utf8mb4" in uri

    def test_default_redis_url(self):
        """默认 Redis URL 格式"""
        config = BaseConfig()
        url = config.REDIS_URL
        assert url.startswith("redis://")
        assert "127.0.0.1" in url

    def test_redis_url_with_password(self):
        """带密码的 Redis URL"""
        config = BaseConfig()
        # 临时覆盖密码
        original = config.REDIS_PASSWORD
        try:
            object.__setattr__(config, 'REDIS_PASSWORD', 'secret123')
            url = config.REDIS_URL
            assert "secret123" in url
        finally:
            object.__setattr__(config, 'REDIS_PASSWORD', original)

    def test_celery_broker_url_matches_redis(self):
        """Celery Broker URL 与 Redis URL 一致"""
        config = BaseConfig()
        assert config.CELERY_BROKER_URL == config.REDIS_URL
        assert config.CELERY_RESULT_BACKEND == config.REDIS_URL

    def test_jwt_config_defaults(self):
        """JWT 默认配置"""
        config = BaseConfig()
        assert len(config.JWT_SECRET_KEY) >= 16
        assert config.JWT_ACCESS_TOKEN_EXPIRES == 86400      # 24小时
        assert config.JWT_REFRESH_TOKEN_EXPIRES == 604800     # 7天

    def test_crawl_config_defaults(self):
        """爬虫默认配置"""
        config = BaseConfig()
        assert config.CRAWL_DELAY_MIN >= 1.0
        assert config.CRAWL_DELAY_MAX >= config.CRAWL_DELAY_MIN
        assert config.CRAWL_MAX_RETRIES == 3
        assert config.CRAWL_MAX_PAGES == 5

    def test_user_agents_not_empty(self):
        """UA 列表非空"""
        config = BaseConfig()
        assert len(config.CRAWL_USER_AGENTS) >= 5
        for ua in config.CRAWL_USER_AGENTS:
            assert isinstance(ua, str)
            assert len(ua) > 20

    def test_login_security_config(self):
        """登录安全配置"""
        config = BaseConfig()
        assert config.MAX_LOGIN_ATTEMPTS == 5
        assert config.ACCOUNT_LOCK_MINUTES == 15

    def test_cache_config(self):
        """缓存配置"""
        config = BaseConfig()
        assert config.CACHE_TTL_SECONDS == 3600

    def test_salary_validation_config(self):
        """薪资验证配置"""
        config = BaseConfig()
        assert config.SALARY_MIN_VALID == 1000
        assert config.SALARY_MAX_VALID == 200000

    def test_pagination_config(self):
        """分页配置"""
        config = BaseConfig()
        assert config.DEFAULT_PAGE_SIZE == 20
        assert config.MAX_PAGE_SIZE == 100


class TestDevelopmentConfig:
    """开发环境配置测试"""

    def test_debug_enabled(self):
        config = DevelopmentConfig()
        assert config.DEBUG is True
        assert config.ENV == "development"

    def test_inherits_base(self):
        """继承 BaseConfig"""
        config = DevelopmentConfig()
        assert isinstance(config, BaseConfig)


class TestTestingConfig:
    """测试环境配置测试"""

    def test_sqlite_memory_database(self):
        """测试环境使用 SQLite 内存数据库"""
        config = TestingConfig()
        uri = config.SQLALCHEMY_DATABASE_URI
        assert "sqlite:///:memory:" in uri

    def test_short_jwt_expiry(self):
        """测试环境 JWT 有效期缩短"""
        config = TestingConfig()
        assert config.JWT_ACCESS_TOKEN_EXPIRES == 60
        assert config.JWT_REFRESH_TOKEN_EXPIRES == 300

    def test_debug_and_testing_flags(self):
        """Debug 和 Testing 标志"""
        config = TestingConfig()
        assert config.DEBUG is True
        assert config.TESTING is True
        assert config.ENV == "testing"


class TestProductionConfig:
    """生产环境配置测试"""

    def test_debug_disabled(self):
        config = ProductionConfig()
        assert config.DEBUG is False
        assert config.ENV == "production"

    def test_log_level(self):
        config = ProductionConfig()
        assert config.LOG_LEVEL == "WARNING"


class TestGetConfig:
    """配置工厂函数测试"""

    def test_get_development_config(self):
        config = get_config("development")
        assert isinstance(config, DevelopmentConfig)
        assert config.DEBUG is True

    def test_get_testing_config(self):
        config = get_config("testing")
        assert isinstance(config, TestingConfig)

    def test_get_production_config(self):
        config = get_config("production")
        assert isinstance(config, ProductionConfig)

    def test_get_unknown_env_defaults(self):
        """未知环境默认使用开发配置"""
        config = get_config("nonexistent")
        assert isinstance(config, DevelopmentConfig)

    def test_get_default_config(self):
        """不传参返回开发配置"""
        config = get_config()
        assert isinstance(config, DevelopmentConfig)
