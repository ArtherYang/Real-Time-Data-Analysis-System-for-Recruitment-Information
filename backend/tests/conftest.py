"""
pytest 测试夹具
===============
提供测试用的 Flask 应用、数据库会话和示例数据。

使用方式：
    pytest backend/tests/ -v
"""

import sys
import os

# 将 backend 目录加入 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime
from app import create_app
from app.config import TestingConfig
from app import database as db_module


@pytest.fixture(scope="session")
def app():
    """创建测试用的 Flask 应用实例（session级别，所有测试共享）。"""
    flask_app = create_app(TestingConfig())
    flask_app.config.update({"TESTING": True})

    with flask_app.app_context():
        yield flask_app


@pytest.fixture
def client(app):
    """创建 Flask 测试客户端。"""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """
    获取数据库会话 — 每个测试函数使用独立会话，
    测试结束后自动回滚，保证测试隔离。
    """
    # 确保数据库引擎已初始化
    from app.database import init_db, _engine
    if _engine is None:
        init_db(TestingConfig())
    # 创建所有表
    from app.database import create_tables
    create_tables()

    session = db_module.SessionLocal()
    yield session
    session.rollback()
    session.close()


# ======================== 数据处理测试共享 Fixtures ========================

@pytest.fixture
def sample_raw_jobs() -> list:
    """生成 10 条模拟原始岗位数据，覆盖正常和异常场景。"""
    from app.crawler.base import JobRawData

    now = datetime.now().isoformat()
    return [
        # 正常数据
        JobRawData(
            title="Python开发工程师",
            company="字节跳动",
            source="boss_zhipin",
            crawled_at=now,
            salary="15K-25K",
            location="北京",
            district="海淀区",
            experience="3-5年",
            education="本科及以上",
            skills="Python,Django,MySQL",
            platform_job_id="boss_001",
            published_at="2026-06-25",
        ),
        JobRawData(
            title="Java开发工程师",
            company="阿里巴巴",
            source="boss_zhipin",
            crawled_at=now,
            salary="20K-35K",
            location="杭州",
            district="西湖区",
            experience="3-5年",
            education="本科及以上",
            skills="Java,Spring,MySQL",
            platform_job_id="boss_002",
            published_at="2026-06-26",
        ),
        JobRawData(
            title="前端开发",
            company="腾讯科技",
            source="boss_zhipin",
            crawled_at=now,
            salary="薪资面议",
            location="深圳",
            experience="经验不限",
            education="学历不限",
            platform_job_id="boss_003",
            published_at="2026-06-27",
        ),
        # 异常数据：缺少岗位名称
        JobRawData(
            title="",
            company="某公司",
            source="boss_zhipin",
            crawled_at=now,
            salary="10K-15K",
            location="上海",
            platform_job_id="boss_004",
        ),
        # 异常数据：缺少公司名称
        JobRawData(
            title="数据分析师",
            company="",
            source="boss_zhipin",
            crawled_at=now,
            salary="12K-20K",
            location="北京",
            platform_job_id="boss_005",
        ),
        # 正常数据（重复 - 用于测试去重）
        JobRawData(
            title="Python开发工程师",
            company="字节跳动",
            source="boss_zhipin",
            crawled_at=now,
            salary="15K-25K",
            location="北京",
            platform_job_id="boss_001",  # 与第一条相同
        ),
        # 正常数据
        JobRawData(
            title="数据科学家",
            company="华为技术",
            source="boss_zhipin",
            crawled_at=now,
            salary="40K-70K",
            location="深圳",
            experience="5-10年",
            education="硕士及以上",
            skills="Python,TensorFlow,PyTorch",
            platform_job_id="boss_007",
            published_at="2026-06-20",
        ),
        # 异常数据：薪资超出范围
        JobRawData(
            title="测试工程师",
            company="测试公司",
            source="boss_zhipin",
            crawled_at=now,
            salary="500000-999999",
            location="武汉",
            platform_job_id="boss_008",
        ),
        # 标题中包含特殊字符
        JobRawData(
            title="  AI算法工程师（大模型方向）  ",
            company="商汤科技",
            source="boss_zhipin",
            crawled_at=now,
            salary="35K-60K",
            location="北京",
            platform_job_id="boss_009",
        ),
        # 正常数据
        JobRawData(
            title="产品经理",
            company="美团",
            source="boss_zhipin",
            crawled_at=now,
            salary="25K-40K",
            location="北京",
            platform_job_id="boss_010",
        ),
    ]


@pytest.fixture
def sample_clean_data(sample_raw_jobs) -> list:
    """生成清洗后的模拟数据列表。"""
    from app.processor.cleaner import DataCleaner

    cleaner = DataCleaner()
    clean_data, _ = cleaner.clean(sample_raw_jobs)
    return clean_data


@pytest.fixture
def sample_normalized_data(sample_clean_data) -> list:
    """生成标准化后的模拟数据列表。"""
    from app.processor.normalizer import FieldNormalizer

    normalizer = FieldNormalizer()
    return normalizer.normalize(sample_clean_data)
