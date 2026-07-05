"""
分析结果缓存管理器
==================
基于 analysis_cache 表的缓存层，减少高频分析查询的实时计算压力。

缓存策略：
- TTL 默认 1 小时（来自 config.CACHE_TTL_SECONDS）
- 缓存键 = cache_type + params_hash（SHA-256）
- 写入时覆盖同类型同 hash 的旧缓存

AI生成，待人工审查。
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..models.analysis import AnalysisCache, generate_uuid


class AnalysisCacheManager:
    """
    分析结果缓存管理器。

    使用方式：
        cache = AnalysisCacheManager(db_session)
        cached = cache.get("hot_jobs", filters)
        if cached:
            return cached
        result = compute(...)
        cache.set("hot_jobs", filters, result)
    """

    def __init__(self, db_session: Session, ttl_seconds: int = 3600):
        """
        初始化缓存管理器。

        Args:
            db_session: SQLAlchemy 数据库会话。
            ttl_seconds: 缓存有效期（秒），默认 3600。
        """
        self.db = db_session
        self.ttl = ttl_seconds

    def get(self, cache_type: str, params_hash: str) -> Optional[dict]:
        """
        查询缓存。

        Args:
            cache_type: 缓存类型标识（如 "hot_jobs", "salary_dist"）。
            params_hash: 查询参数 SHA-256 哈希值。

        Returns:
            缓存命中时返回 result_data（dict），未命中或已过期返回 None。
        """
        cached = (
            self.db.query(AnalysisCache)
            .filter_by(cache_type=cache_type, params_hash=params_hash)
            .order_by(AnalysisCache.created_at.desc())
            .first()
        )
        if cached and not cached.is_expired():
            return cached.result_data
        return None

    def set(self, cache_type: str, params_hash: str, result_data: dict) -> None:
        """
        写入缓存（覆盖同类型同 hash 的旧条目）。

        Args:
            cache_type: 缓存类型标识。
            params_hash: 查询参数 SHA-256 哈希值。
            result_data: 分析结果数据（可 JSON 序列化的字典）。
        """
        # 删除旧缓存
        self.db.query(AnalysisCache).filter_by(
            cache_type=cache_type, params_hash=params_hash
        ).delete()

        # 写入新缓存
        cache_entry = AnalysisCache(
            cache_id=generate_uuid(),
            cache_type=cache_type,
            params_hash=params_hash,
            result_data=result_data,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=self.ttl),
        )
        self.db.add(cache_entry)
        self.db.commit()

    def invalidate(self, cache_type: Optional[str] = None) -> int:
        """
        清除缓存。

        Args:
            cache_type: 指定类型则只清除该类型；None 则清除全部。

        Returns:
            删除的缓存条目数。
        """
        query = self.db.query(AnalysisCache)
        if cache_type:
            query = query.filter_by(cache_type=cache_type)
        count = query.delete()
        self.db.commit()
        return count
