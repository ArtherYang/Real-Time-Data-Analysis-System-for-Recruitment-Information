"""
技能词云服务
============
基于岗位 skills 字段（逗号分隔的技能标签）进行统计分析，包括：
- 技能频率统计（全局 Top N）
- 技能共现对分析（同时出现的技能组合）
- 按岗位大类的 Top 技能
- 词云数据生成（ECharts wordCloud 兼容格式）

所有技能解析在 Python 中进行（skills 字段为 VARCHAR 逗号分隔字符串）。

AI生成，待人工审查。
"""

from collections import Counter
from itertools import combinations
from typing import Optional

from sqlalchemy.orm import Session

from ..models.job import Job
from .cache import AnalysisCacheManager
from .filters import AnalysisFilters


class SkillWordCloudService:
    """
    技能词云分析服务。
    """

    CACHE_TYPE = "skill_analysis"

    def __init__(self, db: Session, cache: AnalysisCacheManager):
        """
        初始化服务。

        Args:
            db: SQLAlchemy 数据库会话。
            cache: 缓存管理器实例。
        """
        self.db = db
        self.cache = cache

    @staticmethod
    def _parse_skills(skills_str: Optional[str]) -> list[str]:
        """
        解析逗号分隔的技能字符串为列表。

        Args:
            skills_str: 如 "Python,Django,MySQL"。

        Returns:
            去空格后的技能列表，空字符串返回空列表。
        """
        if not skills_str or not skills_str.strip():
            return []
        return [s.strip() for s in skills_str.split(",") if s.strip()]

    def _fetch_all_skills(self, filters: AnalysisFilters) -> list[str]:
        """
        从数据库获取所有有效岗位的技能标签，并展开为扁平列表。

        Args:
            filters: 查询筛选参数。

        Returns:
            所有技能标签的扁平列表（含重复）。
        """
        query = filters.apply_to_query(self.db.query(Job.skills))
        results = query.filter(
            Job.skills.isnot(None),
            Job.skills != "",
        ).all()

        all_skills = []
        for (skills_str,) in results:
            all_skills.extend(self._parse_skills(skills_str))
        return all_skills

    def _fetch_all_skill_sets(
        self, filters: AnalysisFilters, job_category: Optional[str] = None
    ) -> list[list[str]]:
        """
        从数据库获取每个岗位的技能集合列表。

        Args:
            filters: 查询筛选参数。
            job_category: 可选，限定岗位大类。

        Returns:
            [[skill1, skill2, ...], ...] 每个子列表是一个岗位的技能。
        """
        query = filters.apply_to_query(self.db.query(Job.skills))
        query = query.filter(
            Job.skills.isnot(None),
            Job.skills != "",
        )
        if job_category:
            query = query.filter(Job.job_category == job_category)

        results = query.all()
        return [self._parse_skills(r[0]) for r in results]

    def get_skill_frequency(
        self, filters: AnalysisFilters, top_n: int = 100
    ) -> list[dict]:
        """
        获取技能频率统计（全局 Top N）。

        Args:
            filters: 查询筛选参数。
            top_n: 返回前 N 个技能，默认 100。

        Returns:
            [{skill, count, frequency_pct}, ...] 按 count 降序。
        """
        top_n = min(max(top_n, 1), 200)

        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "frequency" in cached:
            return cached["frequency"][:top_n]

        all_skills = self._fetch_all_skills(filters)
        total = len(all_skills)

        counter = Counter(all_skills)
        data = [
            {
                "skill": skill,
                "count": count,
                "frequency_pct": round(count / total * 100, 1) if total > 0 else 0,
            }
            for skill, count in counter.most_common(top_n)
        ]

        existing = cached or {}
        existing["frequency"] = data
        self.cache.set(self.CACHE_TYPE, params_hash, existing)

        return data

    def get_skill_cooccurrence(
        self, filters: AnalysisFilters, top_n: int = 50
    ) -> list[dict]:
        """
        获取技能共现对分析。

        对每个岗位的技能列表，生成所有 2-组合（无序对），
        统计各组合的出现频次。

        Args:
            filters: 查询筛选参数。
            top_n: 返回前 N 对。

        Returns:
            [{skill_a, skill_b, count}, ...] 按 count 降序。
        """
        top_n = min(max(top_n, 1), 100)

        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "cooccurrence" in cached:
            return cached["cooccurrence"][:top_n]

        skill_sets = self._fetch_all_skill_sets(filters)

        pair_counter = Counter()
        for skills in skill_sets:
            if len(skills) >= 2:
                for a, b in combinations(sorted(skills), 2):
                    pair_counter[(a, b)] += 1

        data = [
            {"skill_a": a, "skill_b": b, "count": count}
            for (a, b), count in pair_counter.most_common(top_n)
        ]

        existing = cached or {}
        existing["cooccurrence"] = data
        self.cache.set(self.CACHE_TYPE, params_hash, existing)

        return data

    def get_top_skills_by_category(
        self, filters: AnalysisFilters, top_n: int = 20
    ) -> dict:
        """
        获取按岗位大类分组的 Top 技能。

        Args:
            filters: 查询筛选参数。
            top_n: 每个类别返回前 N 个技能。

        Returns:
            {job_category: [{skill, count}, ...], ...}
        """
        top_n = min(max(top_n, 1), 50)

        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "by_category" in cached:
            return cached["by_category"]

        # 获取所有岗位大类
        cat_results = (
            filters.apply_to_query(self.db.query(Job.job_category))
            .filter(Job.job_category.isnot(None), Job.job_category != "")
            .distinct()
            .all()
        )
        categories = [r[0] for r in cat_results]

        result = {}
        for cat in categories:
            skill_sets = self._fetch_all_skill_sets(filters, job_category=cat)
            all_skills = []
            for skills in skill_sets:
                all_skills.extend(skills)

            counter = Counter(all_skills)
            result[cat] = [
                {"skill": skill, "count": count}
                for skill, count in counter.most_common(top_n)
            ]

        existing = cached or {}
        existing["by_category"] = result
        self.cache.set(self.CACHE_TYPE, params_hash, existing)

        return result

    def generate_wordcloud_data(
        self, filters: AnalysisFilters, top_n: int = 100
    ) -> list[dict]:
        """
        生成 ECharts wordCloud 兼容格式的词云数据。

        返回格式：[{name: "Python", value: 150}, ...]
        value 越大，词云中字体越大。

        Args:
            filters: 查询筛选参数。
            top_n: 返回前 N 个技能。

        Returns:
            [{name, value}, ...] 列表。
        """
        top_n = min(max(top_n, 1), 200)

        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "wordcloud" in cached:
            return cached["wordcloud"][:top_n]

        frequency = self.get_skill_frequency(filters, top_n)
        data = [
            {"name": item["skill"], "value": item["count"]}
            for item in frequency
        ]

        existing = cached or {}
        existing["wordcloud"] = data
        self.cache.set(self.CACHE_TYPE, params_hash, existing)

        return data
