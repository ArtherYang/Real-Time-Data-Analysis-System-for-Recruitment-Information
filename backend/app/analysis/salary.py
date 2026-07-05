"""
薪资分布服务
============
提供岗位薪资的多维度统计分析，包括：
- 按维度分组的薪资统计（均值、中位数、P25、P75）
- 城市×经验段的交叉薪资分析
- 薪资-经验关系矩阵

中位数和分位数使用 Python 计算以确保 SQLite/MySQL 双兼容。

AI生成，待人工审查。
"""

import numpy as np
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.job import Job
from .cache import AnalysisCacheManager
from .filters import AnalysisFilters


class SalaryDistributionService:
    """
    薪资分布分析服务。
    """

    CACHE_TYPE = "salary_dist"

    def __init__(self, db: Session, cache: AnalysisCacheManager):
        """
        初始化服务。

        Args:
            db: SQLAlchemy 数据库会话。
            cache: 缓存管理器实例。
        """
        self.db = db
        self.cache = cache

    def _compute_salary_stats(self, midpoints: list[float]) -> dict:
        """
        计算薪资统计指标。

        Args:
            midpoints: 薪资中点值列表。

        Returns:
            {mean, median, p25, p75, min, max, count} 字典。
        """
        if not midpoints:
            return {
                "mean": None, "median": None, "p25": None,
                "p75": None, "min": None, "max": None, "count": 0,
            }

        arr = np.array(midpoints)
        return {
            "mean": round(float(np.mean(arr)), 0),
            "median": round(float(np.median(arr)), 0),
            "p25": round(float(np.percentile(arr, 25)), 0),
            "p75": round(float(np.percentile(arr, 75)), 0),
            "min": round(float(np.min(arr)), 0),
            "max": round(float(np.max(arr)), 0),
            "count": len(midpoints),
        }

    def get_salary_stats(
        self,
        filters: AnalysisFilters,
        group_by: str = "job_category",
        top_n: int = 30,
    ) -> list[dict]:
        """
        获取按指定维度分组的薪资统计数据。

        维度可以是 job_category / city / experience / education。
        排除"面议"和空薪资的记录。

        Args:
            filters: 查询筛选参数。
            group_by: 分组维度。
            top_n: 返回前 N 组（按样本量降序）。

        Returns:
            [{group_key, stats: {mean, median, p25, p75, min, max, count}}, ...]。
        """
        valid_groups = {"job_category", "city", "experience", "education"}
        if group_by not in valid_groups:
            group_by = "job_category"

        top_n = min(max(top_n, 1), 100)

        # 查缓存
        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        cache_key = f"stats_{group_by}"
        if cached and cache_key in cached:
            return cached[cache_key][:top_n]

        group_column = getattr(Job, group_by)

        # 基础查询：排除面议和空薪资
        base_query = AnalysisFilters.exclude_negotiable_salary(
            filters.apply_to_query(self.db.query(Job))
        )

        # 获取所有分组
        group_results = (
            base_query.with_entities(
                group_column.label("group_key"),
                func.count(Job.job_id).label("sample_count"),
            )
            .filter(group_column.isnot(None), group_column != "")
            .group_by(group_column)
            .order_by(func.count(Job.job_id).desc())
            .all()
        )

        data = []
        for group_key, sample_count in group_results[:top_n]:
            # 获取该组所有薪资中点值
            midpoints_query = (
                base_query.with_entities(
                    ((Job.salary_min + Job.salary_max) / 2).label("midpoint")
                )
                .filter(group_column == group_key)
                .all()
            )
            midpoints = [float(row[0]) for row in midpoints_query if row[0] is not None]

            stats = self._compute_salary_stats(midpoints)
            data.append({
                "group_key": str(group_key),
                "sample_count": sample_count,
                "stats": stats,
            })

        # 写缓存
        existing = cached or {}
        existing[cache_key] = data
        self.cache.set(self.CACHE_TYPE, params_hash, existing)

        return data

    def get_salary_by_city_and_experience(
        self, filters: AnalysisFilters
    ) -> dict:
        """
        获取城市×经验段的交叉薪资分析。

        Args:
            filters: 查询筛选参数。

        Returns:
            {city_name: {experience_level: {count, mean, median}, ...}, ...}
        """
        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "city_experience" in cached:
            return cached["city_experience"]

        base_query = AnalysisFilters.exclude_negotiable_salary(
            filters.apply_to_query(self.db.query(Job))
        )

        # 获取所有（城市, 经验）组合
        results = (
            base_query.with_entities(
                Job.city,
                Job.experience,
                func.count(Job.job_id).label("count"),
            )
            .filter(Job.city.isnot(None), Job.city != "")
            .group_by(Job.city, Job.experience)
            .order_by(Job.city, Job.experience)
            .all()
        )

        # 构建嵌套字典
        matrix = {}
        for city, exp, count in results:
            city_str = str(city)
            exp_str = str(exp)

            if city_str not in matrix:
                matrix[city_str] = {}

            # 获取该组合的具体薪资中点用于计算统计
            midpoints_query = (
                base_query.with_entities(
                    ((Job.salary_min + Job.salary_max) / 2).label("midpoint")
                )
                .filter(Job.city == city, Job.experience == exp)
                .all()
            )
            midpoints = [float(r[0]) for r in midpoints_query if r[0] is not None]

            mean_salary = round(float(np.mean(midpoints)), 0) if midpoints else None
            median_salary = round(float(np.median(midpoints)), 0) if midpoints else None

            matrix[city_str][exp_str] = {
                "count": count,
                "mean": mean_salary,
                "median": median_salary,
            }

        existing = cached or {}
        existing["city_experience"] = matrix
        self.cache.set(self.CACHE_TYPE, params_hash, existing)

        return matrix

    def get_salary_experience_matrix(
        self, filters: AnalysisFilters
    ) -> dict:
        """
        获取薪资-经验矩阵，用于热力图展示。

        行：经验段，列：岗位大类（或城市）。
        单元格值：中位数薪资。

        Args:
            filters: 查询筛选参数。

        Returns:
            {
                "rows": ["应届生", "1-3年", ...],
                "columns": ["技术", "产品", ...],
                "data": [[median_value, ...], ...]  # 2D 数组
            }
        """
        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "matrix" in cached:
            return cached["matrix"]

        base_query = AnalysisFilters.exclude_negotiable_salary(
            filters.apply_to_query(self.db.query(Job))
        )

        # 经验段（行）
        experience_levels = [
            "应届生", "1-3年", "3-5年", "5-10年", "10年以上", "不限"
        ]

        # 岗位大类（列）
        cat_results = (
            base_query.with_entities(
                Job.job_category,
                func.count(Job.job_id),
            )
            .filter(Job.job_category.isnot(None), Job.job_category != "")
            .group_by(Job.job_category)
            .order_by(func.count(Job.job_id).desc())
            .limit(10)
            .all()
        )
        categories = [r[0] for r in cat_results]

        # 构建矩阵
        matrix_data = []
        for exp in experience_levels:
            row = []
            for cat in categories:
                midpoints_query = (
                    base_query.with_entities(
                        ((Job.salary_min + Job.salary_max) / 2).label("midpoint")
                    )
                    .filter(Job.experience == exp, Job.job_category == cat)
                    .all()
                )
                midpoints = [float(r[0]) for r in midpoints_query if r[0] is not None]
                median_val = round(float(np.median(midpoints)), 0) if midpoints else None
                row.append(median_val)
            matrix_data.append(row)

        result = {
            "rows": experience_levels,
            "columns": categories,
            "data": matrix_data,
        }

        existing = cached or {}
        existing["matrix"] = result
        self.cache.set(self.CACHE_TYPE, params_hash, existing)

        return result
