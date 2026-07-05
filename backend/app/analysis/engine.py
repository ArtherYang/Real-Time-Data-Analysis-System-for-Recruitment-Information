"""
M3 数据分析引擎 - 核心编排器
=============================
负责四个分析子模块的统一调度和资源共享。

所有分析服务共享：
- 数据库会话（SQLAlchemy Session）
- 缓存管理器（AnalysisCacheManager）
- 公共查询工具（来自 filters 模块）

使用方式：
    engine = AnalysisEngine(db_session)
    ranking = engine.ranking.get_category_ranking(filters)

AI生成，待人工审查。
"""

from sqlalchemy.orm import Session

from .cache import AnalysisCacheManager
from .ranking import TrendingRankingService
from .salary import SalaryDistributionService
from .regional import RegionalAnalysisService
from .skills import SkillWordCloudService


class AnalysisEngine:
    """
    M3 数据分析引擎 — 核心编排器。

    以懒加载属性方式暴露四个分析服务，所有服务共享
    同一个数据库会话和缓存管理器。

    Attributes:
        db: SQLAlchemy 数据库会话。
        cache: 分析结果缓存管理器。
        ranking: 热度排行服务（懒加载）。
        salary: 薪资分布服务（懒加载）。
        regional: 地域分析服务（懒加载）。
        skills: 技能词云服务（懒加载）。
    """

    def __init__(self, db_session: Session, cache_ttl: int = 3600):
        """
        初始化分析引擎。

        Args:
            db_session: SQLAlchemy 数据库会话。
            cache_ttl: 缓存有效期（秒），默认 3600。
        """
        self.db = db_session
        self.cache = AnalysisCacheManager(db_session, ttl_seconds=cache_ttl)

        # 懒加载的服务实例
        self._ranking: TrendingRankingService = None
        self._salary: SalaryDistributionService = None
        self._regional: RegionalAnalysisService = None
        self._skills: SkillWordCloudService = None

    @property
    def ranking(self) -> TrendingRankingService:
        """热度排行服务（懒加载）。"""
        if self._ranking is None:
            self._ranking = TrendingRankingService(self.db, self.cache)
        return self._ranking

    @property
    def salary(self) -> SalaryDistributionService:
        """薪资分布服务（懒加载）。"""
        if self._salary is None:
            self._salary = SalaryDistributionService(self.db, self.cache)
        return self._salary

    @property
    def regional(self) -> RegionalAnalysisService:
        """地域分析服务（懒加载）。"""
        if self._regional is None:
            self._regional = RegionalAnalysisService(self.db, self.cache)
        return self._regional

    @property
    def skills(self) -> SkillWordCloudService:
        """技能词云服务（懒加载）。"""
        if self._skills is None:
            self._skills = SkillWordCloudService(self.db, self.cache)
        return self._skills
