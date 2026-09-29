"""
岗位信息 ORM 模型
================
定义 jobs 表的 SQLAlchemy 映射，对应 init.sql 中的核心岗位信息表。

字段来源：综合 BOSS直聘 / 智联招聘 / 前程无忧 三个平台的完整字段集合（19个核心字段）。
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Text, Date, DateTime, Enum, Index
)
from app.models.database import Base


def generate_uuid() -> str:
    """生成32位UUID（去连字符），用作主键。"""
    return uuid.uuid4().hex


class Job(Base):
    """岗位信息模型 — 核心业务实体"""

    __tablename__ = "jobs"

    # ==== 主键 ====
    job_id = Column(String(32), primary_key=True, default=generate_uuid, comment="岗位唯一标识")

    # ==== 岗位核心 ====
    title = Column(String(200), nullable=False, comment="岗位名称（标准化后）")
    title_raw = Column(String(200), nullable=True, comment="岗位名称（原始）")
    company = Column(String(200), nullable=False, comment="公司名称")
    job_type = Column(String(50), nullable=True, comment="工作类型（全职/兼职/实习）")
    recruit_number = Column(String(20), nullable=True, comment="招聘人数")

    # ==== 薪资 ====
    salary_min = Column(Integer, nullable=True, comment="最低月薪（元）")
    salary_max = Column(Integer, nullable=True, comment="最高月薪（元）")
    salary_type = Column(
        Enum("月薪", "年薪", "面议", "时薪", "未识别", "日薪", name="salary_type_enum"),
        nullable=False, default="月薪", comment="薪资类型"
    )

    # ==== 地域 ====
    city = Column(String(50), nullable=False, comment="工作城市（标准化，地级市）")
    district = Column(String(100), nullable=True, comment="区/县")

    # ==== 要求 ====
    experience = Column(
        String(20), nullable=False, default="不限", comment="经验要求"
    )
    education = Column(
        String(20), nullable=False, default="不限", comment="学历要求"
    )

    # ==== 内容 ====
    description = Column(Text, nullable=True, comment="岗位描述原文")
    skills = Column(String(500), nullable=True, comment="技能标签（逗号分隔）")

    # ==== 分类维度 ====
    industry = Column(String(100), nullable=True, comment="所属行业")
    job_category = Column(String(100), nullable=True, comment="岗位大类")

    # ==== 公司信息 ====
    company_size = Column(String(50), nullable=True, comment="公司规模")
    company_type = Column(String(50), nullable=True, comment="公司类型")
    welfare = Column(String(500), nullable=True, comment="福利标签")

    # ==== 来源与溯源 ====
    platform = Column(
        Enum(
            "BOSS直聘", "智联招聘", "前程无忧", "猎聘", "其他",
            "boss_zhipin", "job51", "zhilian", "liepin",
            name="platform_enum",
        ),
        nullable=False, comment="数据来源平台"
    )
    platform_job_id = Column(String(100), nullable=True, comment="平台原始职位ID")
    source_url = Column(String(500), nullable=True, comment="职位详情页原始URL")

    # ==== 时间 ====
    published_at = Column(Date, nullable=True, comment="岗位发布日期（来自平台）")
    crawled_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="系统采集时间")

    # ==== 状态 ====
    status = Column(
        Enum("有效", "已过期", "已删除", name="status_enum"),
        nullable=False, default="有效", comment="数据状态"
    )

    # 索引定义（在 __table_args__ 中声明复合索引）
    __table_args__ = (
        Index("idx_title", "title"),
        Index("idx_company", "company"),
        Index("idx_city", "city"),
        Index("idx_experience", "experience"),
        Index("idx_education", "education"),
        Index("idx_platform", "platform"),
        Index("idx_published_at", "published_at"),
        Index("idx_salary", "salary_min", "salary_max"),
        Index("idx_platform_job", "platform", "platform_job_id"),
        Index("idx_status", "status"),
        Index("idx_job_category", "job_category"),
        Index("idx_city_salary", "city", "salary_min", "salary_max"),
        Index("idx_title_city", "title", "city"),
        # 全文索引（MySQL 5.7.6+ ngram 分词，SQLite 自动跳过）
        Index(
            "ft_title_desc", "title", "description",
            mysql_with_parser="ngram",
            mysql_prefix="FULLTEXT",
        ),
    )

    def to_dict(self) -> dict:
        """将模型实例转换为字典，用于 API 序列化。"""
        return {
            "job_id": self.job_id,
            "title": self.title,
            "title_raw": self.title_raw,
            "company": self.company,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_type": self.salary_type,
            "city": self.city,
            "district": self.district,
            "experience": self.experience,
            "education": self.education,
            "job_type": self.job_type,
            "recruit_number": self.recruit_number,
            "industry": self.industry,
            "job_category": self.job_category,
            "skills": self.skills,
            "company_size": self.company_size,
            "company_type": self.company_type,
            "welfare": self.welfare,
            "description": self.description,
            "platform": self.platform,
            "platform_job_id": self.platform_job_id,
            "source_url": self.source_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "crawled_at": self.crawled_at.isoformat() if self.crawled_at else None,
            "status": self.status,
        }

    @classmethod
    def from_normalized(cls, data: dict) -> "Job":
        """从标准化后的字典创建 Job 实例。

        将 processor.normalizer 输出的标准化字典映射为 ORM 实例，
        用于 pipeline 的最后一步（数据入库）。
        自动处理字符串到日期/日期时间的转换。

        Args:
            data: FieldNormalizer.normalize() 输出的标准化字典

        Returns:
            Job: 可写入数据库的 Job 实例
        """
        from datetime import date as date_type

        # 转换 published_at: str → date
        published_at = data.get("published_at")
        if isinstance(published_at, str):
            try:
                published_at = date_type.fromisoformat(published_at)
            except (ValueError, TypeError):
                published_at = None

        # 转换 crawled_at: str → datetime
        crawled_at = data.get("crawled_at")
        if isinstance(crawled_at, str):
            try:
                crawled_at = datetime.fromisoformat(crawled_at)
            except (ValueError, TypeError):
                crawled_at = datetime.now()

        return cls(
            title=data.get("title", ""),
            title_raw=data.get("title_raw"),
            company=data.get("company", ""),
            salary_min=data.get("salary_min"),
            salary_max=data.get("salary_max"),
            salary_type=data.get("salary_type", "月薪"),
            city=data.get("city", ""),
            district=data.get("district"),
            experience=data.get("experience", "不限"),
            education=data.get("education", "不限"),
            description=data.get("description"),
            skills=data.get("skills"),
            industry=data.get("industry"),
            job_category=data.get("job_category"),
            job_type=data.get("job_type"),
            recruit_number=data.get("recruit_number"),
            company_size=data.get("company_size"),
            company_type=data.get("company_type"),
            welfare=data.get("welfare"),
            platform=data.get("source", ""),
            platform_job_id=data.get("platform_job_id"),
            source_url=data.get("source_url"),
            published_at=published_at,
            crawled_at=crawled_at,
            status=data.get("status", "有效"),
        )

    def __repr__(self) -> str:
        return f"<Job {self.job_id}: {self.title} @ {self.company}>"
