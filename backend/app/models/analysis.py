"""
分析结果缓存 ORM 模型
====================
缓存高频分析查询结果，避免重复实时计算。
缓存有效期默认1小时，过期后自动刷新（由业务逻辑控制）。
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy import JSON
from app.models.database import Base


def generate_uuid() -> str:
    """生成32位UUID（去连字符），用作主键。"""
    return uuid.uuid4().hex


class AnalysisCache(Base):
    """分析结果缓存模型"""

    __tablename__ = "analysis_cache"

    cache_id = Column(String(32), primary_key=True, default=generate_uuid, comment="缓存唯一标识")
    cache_type = Column(
        String(50), nullable=False,
        comment="缓存类型: hot_jobs/salary_dist/city_dist/skill_analysis"
    )
    params_hash = Column(String(64), nullable=False, comment="查询参数 SHA-256 哈希值")
    result_data = Column(JSON, nullable=False, comment="分析结果数据 (JSON格式)")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="缓存创建时间")
    expires_at = Column(DateTime, nullable=False, comment="缓存过期时间")

    __table_args__ = (
        Index("idx_cache_type", "cache_type"),
        Index("idx_params_hash", "params_hash"),
        Index("idx_expires_at", "expires_at"),
    )

    def is_expired(self) -> bool:
        """检查缓存是否已过期。"""
        return datetime.utcnow() > self.expires_at

    def __repr__(self) -> str:
        return f"<AnalysisCache {self.cache_id}: {self.cache_type}>"
