"""
数据模型层
==========
SQLAlchemy ORM 模型定义，对应 MySQL 数据库中的核心业务表。

主要实体：
- Job：岗位信息（核心业务表，19个字段）
- User：用户信息（注册登录、角色管理）
- AnalysisCache：分析结果缓存（高频查询缓存）
- CrawlLog：采集日志（数据采集任务追踪）
- Company：公司信息
- UserProfile：用户扩展信息（1:1 users）
- UserPreference：用户求职意向（1:1 users）
- Resume：用户简历
- ResumeTemplate：简历模板
"""

from .job import Job
from .user import User
from .analysis import AnalysisCache
from .crawl_log import CrawlLog
from .company import Company
from .user_profile import UserProfile
from .user_preference import UserPreference
from .resume import Resume, ResumeTemplate

__all__ = [
    "Job", "User", "AnalysisCache", "CrawlLog", "Company",
    "UserProfile", "UserPreference", "Resume", "ResumeTemplate",
]
