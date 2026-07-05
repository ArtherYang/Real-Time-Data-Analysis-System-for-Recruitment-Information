"""
热度排行服务
============
提供岗位需求量排行、热度指数计算、趋势时间序列和环比增长率分析。

功能列表：
- get_category_ranking: 按 job_category 聚合的岗位数量排行
- get_hotness_index: 基于发布量+时效性+薪资水平的热度指数排行
- get_trend_data: 按周/月粒度的需求趋势时间序列
- get_period_growth: 计算周环比和月环比增长率

热度指数公式：
    hotness = ln(1 + count) × recency_factor × salary_factor
    归一化到 0-100 区间。

AI生成，待人工审查。
"""

import math
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.job import Job
from .cache import AnalysisCacheManager
from .filters import AnalysisFilters


class TrendingRankingService:
    """
    岗位热度排行分析服务。

    使用 AnalysisCacheManager 缓存查询结果，避免重复计算。
    """

    CACHE_TYPE = "hot_jobs"

    def __init__(self, db: Session, cache: AnalysisCacheManager):
        """
        初始化服务。

        Args:
            db: SQLAlchemy 数据库会话。
            cache: 缓存管理器实例。
        """
        self.db = db
        self.cache = cache

    def get_category_ranking(
        self, filters: AnalysisFilters, top_n: int = 20
    ) -> list[dict]:
        """
        获取岗位大类排行 — 按 job_category 聚合统计。

        Args:
            filters: 查询筛选参数。
            top_n: 返回前 N 条，默认 20，最大 100。

        Returns:
            [{category, count, percentage}, ...] 列表。
        """
        top_n = min(max(top_n, 1), 100)

        # 查缓存
        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "ranking" in cached:
            return cached["ranking"][:top_n]

        # 计算
        base_query = filters.apply_to_query(self.db.query(Job))
        total = base_query.count()

        results = (
            base_query.with_entities(
                Job.job_category,
                func.count(Job.job_id).label("count"),
            )
            .filter(Job.job_category.isnot(None), Job.job_category != "")
            .group_by(Job.job_category)
            .order_by(func.count(Job.job_id).desc())
            .limit(top_n)
            .all()
        )

        data = [
            {
                "category": row[0],
                "count": row[1],
                "percentage": round(row[1] / total * 100, 1) if total > 0 else 0,
            }
            for row in results
        ]

        # 写缓存
        self.cache.set(self.CACHE_TYPE, params_hash, {"ranking": data})

        return data

    def get_hotness_index(
        self, filters: AnalysisFilters, top_n: int = 20
    ) -> list[dict]:
        """
        计算岗位热度指数排行。

        热度指数综合考虑：
        - 岗位发布数量（取对数平滑）
        - 时效性（7天内 ×1.5, 8-30天 ×1.0, 30天以上 ×0.5）
        - 薪资水平（高于中位数薪资 +0.2 系数）

        Args:
            filters: 查询筛选参数。
            top_n: 返回前 N 条，默认 20。

        Returns:
            [{category, hotness_index, count, recent_count, avg_salary}, ...]。
        """
        top_n = min(max(top_n, 1), 100)
        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "hotness" in cached:
            return cached["hotness"][:top_n]

        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        base_query = filters.apply_to_query(self.db.query(Job))

        # 总计数
        total_results = (
            base_query.with_entities(
                Job.job_category,
                func.count(Job.job_id).label("total_count"),
            )
            .filter(Job.job_category.isnot(None), Job.job_category != "")
            .group_by(Job.job_category)
            .all()
        )

        # 最近 7 天计数
        recent_7_results = (
            base_query.with_entities(
                Job.job_category,
                func.count(Job.job_id).label("recent_count"),
            )
            .filter(
                Job.job_category.isnot(None),
                Job.job_category != "",
                Job.published_at >= week_ago,
            )
            .group_by(Job.job_category)
            .all()
        )
        recent_7_map = {r[0]: r[1] for r in recent_7_results}

        # 最近 30 天计数
        recent_30_results = (
            base_query.with_entities(
                Job.job_category,
                func.count(Job.job_id).label("recent_count"),
            )
            .filter(
                Job.job_category.isnot(None),
                Job.job_category != "",
                Job.published_at >= month_ago,
            )
            .group_by(Job.job_category)
            .all()
        )
        recent_30_map = {r[0]: r[1] for r in recent_30_results}

        # 薪资中位数（用于薪资系数）
        salary_query = AnalysisFilters.exclude_negotiable_salary(base_query)
        salary_results = (
            salary_query.with_entities(
                Job.job_category,
                func.avg((Job.salary_min + Job.salary_max) / 2).label("avg_salary"),
            )
            .filter(Job.job_category.isnot(None), Job.job_category != "")
            .group_by(Job.job_category)
            .all()
        )
        salary_map = {r[0]: float(r[1]) if r[1] else 0 for r in salary_results}

        # 计算中位数薪资（所有类别的中位数）
        all_salaries = [s for s in salary_map.values() if s > 0]
        all_salaries.sort()
        median_salary = all_salaries[len(all_salaries) // 2] if all_salaries else 0

        # 计算热度指数
        hotness_list = []
        for cat, total_count in total_results:
            if total_count == 0:
                continue

            recent_7 = recent_7_map.get(cat, 0)
            recent_30 = recent_30_map.get(cat, 0)

            # 时效因子
            if total_count > 0:
                recent_ratio = recent_7 / total_count if total_count > 0 else 0
                if recent_ratio > 0.3:
                    recency_factor = 1.5
                elif recent_ratio > 0.1:
                    recency_factor = 1.0
                else:
                    recency_factor = 0.5
            else:
                recency_factor = 1.0

            # 薪资因子
            avg_sal = salary_map.get(cat, 0)
            if avg_sal > 0 and median_salary > 0:
                salary_factor = 1.0 + (0.2 if avg_sal >= median_salary else 0.0)
            else:
                salary_factor = 1.0

            # 热度原始分
            raw_score = math.log(1 + total_count) * recency_factor * salary_factor
            hotness_list.append({
                "category": cat,
                "raw_score": raw_score,
                "count": total_count,
                "recent_7_count": recent_7,
                "recent_30_count": recent_30,
                "avg_salary": round(avg_sal, 0) if avg_sal else None,
            })

        # 归一化到 0-100
        if hotness_list:
            max_score = max(h["raw_score"] for h in hotness_list)
            if max_score > 0:
                for h in hotness_list:
                    h["hotness_index"] = round(h["raw_score"] / max_score * 100, 1)
            else:
                for h in hotness_list:
                    h["hotness_index"] = 0.0

        hotness_list.sort(key=lambda x: x["hotness_index"], reverse=True)
        result = hotness_list[:top_n]

        # 移除内部字段 raw_score
        for h in result:
            del h["raw_score"]

        self.cache.set(self.CACHE_TYPE, params_hash, {
            "hotness": result,
        })

        return result

    def get_trend_data(
        self,
        filters: AnalysisFilters,
        category: str = None,
        granularity: str = "weekly",
    ) -> list[dict]:
        """
        获取岗位需求趋势时间序列。

        Args:
            filters: 查询筛选参数。
            category: 指定 job_category 分析（None 则全局）。
            granularity: 粒度 "weekly"（按周）或 "monthly"（按月）。

        Returns:
            [{period, count}, ...] 按时间升序排列。
        """
        granularity = granularity if granularity in ("weekly", "monthly") else "weekly"
        params_hash = filters.to_params_hash()

        base_query = filters.apply_to_query(self.db.query(Job))
        if category:
            base_query = base_query.filter(Job.job_category == category)

        # SQLite/MySQL 兼容的日期截断
        if granularity == "weekly":
            # 按周分组：使用 strftime('%Y-%W', published_at)
            period_expr = func.strftime("%Y-%W", Job.published_at)
        else:
            period_expr = func.strftime("%Y-%m", Job.published_at)

        results = (
            base_query.with_entities(
                period_expr.label("period"),
                func.count(Job.job_id).label("count"),
            )
            .filter(Job.published_at.isnot(None))
            .group_by(period_expr)
            .order_by(period_expr)
            .all()
        )

        data = [
            {"period": row[0], "count": row[1]}
            for row in results
        ]

        # 计算环比增长率
        for i in range(1, len(data)):
            prev_count = data[i - 1]["count"]
            if prev_count > 0:
                data[i]["growth_rate"] = round(
                    (data[i]["count"] - prev_count) / prev_count * 100, 1
                )
            else:
                data[i]["growth_rate"] = None

        return data

    def get_period_growth(self, filters: AnalysisFilters) -> dict:
        """
        计算周环比和月环比增长率。

        Args:
            filters: 查询筛选参数。

        Returns:
            {weekly_growth_pct, monthly_growth_pct, current_week_count,
             prev_week_count, current_month_count, prev_month_count}
        """
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        two_weeks_ago = today - timedelta(days=14)
        month_ago = today - timedelta(days=30)
        two_months_ago = today - timedelta(days=60)

        base_query = filters.apply_to_query(self.db.query(Job))

        # 本周
        current_week = base_query.filter(Job.published_at >= week_ago).count()
        # 上周
        prev_week = base_query.filter(
            Job.published_at >= two_weeks_ago,
            Job.published_at < week_ago,
        ).count()

        # 本月
        current_month = base_query.filter(Job.published_at >= month_ago).count()
        # 上月
        prev_month = base_query.filter(
            Job.published_at >= two_months_ago,
            Job.published_at < month_ago,
        ).count()

        def calc_growth(current: int, previous: int) -> Optional[float]:
            if previous > 0:
                return round((current - previous) / previous * 100, 1)
            return None

        return {
            "weekly_growth_pct": calc_growth(current_week, prev_week),
            "monthly_growth_pct": calc_growth(current_month, prev_month),
            "current_week_count": current_week,
            "prev_week_count": prev_week,
            "current_month_count": current_month,
            "prev_month_count": prev_month,
        }
