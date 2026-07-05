"""
分析查询过滤器
==============
统一的筛选参数模型，用于所有分析服务方法的参数传递和缓存键生成。

支持维度：
- 地域：city
- 分类：job_category, industry
- 要求：experience, education
- 时间：date_from, date_to
- 来源：platform

AI生成，待人工审查。
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Query

from ..models.job import Job


@dataclass
class AnalysisFilters:
    """
    通用分析过滤参数。

    所有分析服务方法接受此对象作为统一筛选接口。
    仅非 None 的字段参与 SQL 筛选和缓存键生成。
    """

    city: Optional[str] = None
    job_category: Optional[str] = None
    industry: Optional[str] = None
    experience: Optional[str] = None
    education: Optional[str] = None
    platform: Optional[str] = None
    date_from: Optional[str] = None   # ISO 日期字符串，如 "2026-06-01"
    date_to: Optional[str] = None     # ISO 日期字符串，如 "2026-06-30"

    def to_params_hash(self) -> str:
        """
        生成查询参数 SHA-256 哈希值，用于缓存键匹配。

        Returns:
            64 位十六进制哈希字符串。
        """
        params_dict = {
            "city": self.city or "",
            "job_category": self.job_category or "",
            "industry": self.industry or "",
            "experience": self.experience or "",
            "education": self.education or "",
            "platform": self.platform or "",
            "date_from": self.date_from or "",
            "date_to": self.date_to or "",
        }
        raw = json.dumps(params_dict, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def apply_to_query(self, query: Query, model=Job) -> Query:
        """
        将非空筛选条件应用到 SQLAlchemy 查询对象。

        Args:
            query: SQLAlchemy Query 对象。
            model: ORM 模型类（默认 Job）。

        Returns:
            应用筛选条件后的 Query 对象。
        """
        # 只查询有效岗位
        query = query.filter(model.status == "有效")

        if self.city:
            query = query.filter(model.city == self.city)
        if self.job_category:
            query = query.filter(model.job_category == self.job_category)
        if self.industry:
            query = query.filter(model.industry == self.industry)
        if self.experience:
            query = query.filter(model.experience == self.experience)
        if self.education:
            query = query.filter(model.education == self.education)
        if self.platform:
            query = query.filter(model.platform == self.platform)
        if self.date_from:
            query = query.filter(model.published_at >= self.date_from)
        if self.date_to:
            query = query.filter(model.published_at <= self.date_to)

        return query

    @staticmethod
    def exclude_negotiable_salary(query: Query, model=Job) -> Query:
        """
        排除薪资面议的记录。

        Args:
            query: SQLAlchemy Query 对象。
            model: ORM 模型类。

        Returns:
            筛选后的 Query 对象。
        """
        return query.filter(
            model.salary_type != "面议",
            model.salary_min.isnot(None),
            model.salary_max.isnot(None),
        )
