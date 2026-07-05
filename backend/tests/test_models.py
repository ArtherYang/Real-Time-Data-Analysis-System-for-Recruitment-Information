"""
模型单元测试
============
测试 SQLAlchemy ORM 模型的创建、字段默认值和序列化方法。
"""

import uuid
import pytest
from datetime import datetime

from app.models.job import Job
from app.models.user import User
from app.models.analysis import AnalysisCache
from app.models.crawl_log import CrawlLog
from app.models.company import Company


class TestJobModel:
    """岗位信息模型测试"""

    def test_create_job_with_required_fields(self, db_session):
        """测试创建包含必填字段的岗位记录。"""
        job = Job(
            job_id=uuid.uuid4().hex,
            title="Python开发工程师",
            company="测试科技有限公司",
            platform="BOSS直聘",
            city="北京",
        )
        db_session.add(job)
        db_session.commit()

        assert job.job_id is not None
        assert job.title == "Python开发工程师"
        assert job.company == "测试科技有限公司"
        assert job.platform == "BOSS直聘"
        assert job.status == "有效"  # 默认值
        assert job.salary_type == "月薪"  # 默认值
        assert job.experience == "不限"  # 默认值
        assert job.education == "不限"  # 默认值

    def test_create_job_with_all_fields(self, db_session):
        """测试创建包含全部字段的岗位记录。"""
        job = Job(
            job_id=uuid.uuid4().hex,
            title="高级Python开发工程师",
            title_raw="【急聘】高级Python开发工程师",
            company="星辰科技有限公司",
            salary_min=20000,
            salary_max=35000,
            salary_type="月薪",
            city="北京",
            district="海淀区",
            experience="3-5年",
            education="本科",
            description="负责后端微服务开发和架构设计",
            skills="Python,FastAPI,PostgreSQL,Docker",
            job_type="全职",
            recruit_number="3",
            industry="互联网",
            job_category="技术",
            company_size="500-2000人",
            company_type="民营",
            welfare="五险一金,年终奖,弹性工作",
            platform="BOSS直聘",
            platform_job_id="bj123456",
            source_url="https://www.example.com/job/123",
            published_at=datetime.utcnow().date(),
            crawled_at=datetime.utcnow(),
            status="有效",
        )
        db_session.add(job)
        db_session.commit()

        result = db_session.query(Job).filter(Job.job_id == job.job_id).first()
        assert result is not None
        assert result.salary_min == 20000
        assert result.salary_max == 35000
        assert result.city == "北京"
        assert result.platform_job_id == "bj123456"

    def test_to_dict_method(self, db_session):
        """测试 to_dict() 序列化方法。"""
        job = Job(
            job_id="test123",
            title="测试岗位",
            company="测试公司",
            platform="智联招聘",
            city="上海",
            salary_min=10000,
            salary_max=20000,
        )
        d = job.to_dict()
        assert d["job_id"] == "test123"
        assert d["title"] == "测试岗位"
        assert d["company"] == "测试公司"
        assert d["salary_min"] == 10000
        assert d["salary_max"] == 20000
        # 确保不存在的字段返回 None（不是异常）
        assert d["description"] is None


class TestUserModel:
    """用户模型测试"""

    def test_create_user(self, db_session):
        """测试创建用户。"""
        user = User(
            user_id=uuid.uuid4().hex,
            email="test@example.com",
            password_hash="hashed_password",
            nickname="测试用户",
        )
        db_session.add(user)
        db_session.commit()

        assert user.nickname == "测试用户"
        assert user.role == "普通用户"  # 默认角色
        assert user.is_active is True
        assert user.login_attempts == 0

    def test_to_dict_excludes_sensitive(self):
        """测试 to_dict() 默认不返回敏感信息。"""
        user = User(
            user_id="u1",
            email="test@example.com",
            password_hash="secret_hash",
            nickname="用户",
        )
        d = user.to_dict()
        assert "password_hash" not in d
        assert d["email"] == "test@example.com"

    def test_to_dict_includes_sensitive_when_asked(self):
        """测试 to_dict(include_sensitive=True) 返回完整信息。"""
        user = User(
            user_id="u1",
            email="admin@example.com",
            password_hash="secret_hash",
            nickname="管理员",
            role="管理员",
            is_active=True,
        )
        d = user.to_dict(include_sensitive=True)
        assert d["password_hash"] == "secret_hash"
        assert d["role"] == "管理员"
        assert d["is_active"] is True

    def test_phone_masking(self):
        """测试手机号脱敏。"""
        user = User(
            user_id="u1",
            phone="13812345678",
            password_hash="hash",
            nickname="用户",
        )
        d = user.to_dict()
        assert d["phone"] == "138****5678"

    def test_is_locked(self):
        """测试账号锁定状态检查。"""
        from datetime import timedelta

        user = User(
            user_id="u1",
            password_hash="hash",
            nickname="用户",
        )
        # 未锁定的情况
        assert user.is_locked() is False

        # 锁定未来15分钟
        user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        assert user.is_locked() is True

        # 锁定时间已过
        user.locked_until = datetime.utcnow() - timedelta(minutes=1)
        assert user.is_locked() is False


class TestCrawlLogModel:
    """采集日志模型测试"""

    def test_create_log(self, db_session):
        """测试创建采集日志。"""
        log = CrawlLog(
            log_id=uuid.uuid4().hex,
            platform="BOSS直聘",
            task_type="全量采集",
            total_count=100,
            success_count=95,
            fail_count=5,
        )
        db_session.add(log)
        db_session.commit()

        assert log.status == "排队中"
        assert log.success_rate == 95.0

    def test_success_rate_zero_total(self):
        """测试总数为0时的成功率。"""
        log = CrawlLog(
            log_id=uuid.uuid4().hex,
            platform="智联招聘",
            task_type="增量更新",
            total_count=0,
            success_count=0,
        )
        assert log.success_rate == 0.0


class TestCompanyModel:
    """公司信息模型测试"""

    def test_create_company(self, db_session):
        """测试创建公司记录。"""
        company = Company(
            name="字节跳动",
            size="10000人以上",
            company_type="民营",
            industry="互联网",
        )
        db_session.add(company)
        db_session.commit()

        saved = db_session.query(Company).first()
        assert saved.name == "字节跳动"
        assert saved.industry == "互联网"
        assert saved.size == "10000人以上"

    def test_company_to_dict(self, db_session):
        """测试 Company to_dict() 序列化。"""
        company = Company(
            name="阿里巴巴",
            size="10000人以上",
            company_type="上市公司",
            industry="互联网",
        )
        result = company.to_dict()
        assert result["name"] == "阿里巴巴"
        assert result["company_type"] == "上市公司"
        assert "company_id" in result
        assert "created_at" in result

    def test_company_unique_name(self, db_session):
        """测试公司名称唯一约束。"""
        c1 = Company(name="测试科技", industry="互联网")
        c2 = Company(name="测试科技", industry="金融")
        db_session.add(c1)
        db_session.commit()

        db_session.add(c2)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()
