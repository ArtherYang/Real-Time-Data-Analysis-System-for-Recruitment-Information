"""
采集日志 ORM 模型
=================
记录每次数据采集任务的执行情况，支持状态跟踪和问题排查。
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, Enum, Index
from app.models.database import Base


def generate_uuid() -> str:
    """生成32位UUID（去连字符），用作主键。"""
    return uuid.uuid4().hex


class CrawlLog(Base):
    """采集日志模型"""

    __tablename__ = "crawl_logs"

    log_id = Column(String(32), primary_key=True, default=generate_uuid, comment="日志唯一标识")
    platform = Column(String(50), nullable=False, comment="采集平台")
    task_type = Column(
        Enum("全量采集", "增量更新", "手动触发", name="task_type_enum"),
        nullable=False, default="全量采集", comment="任务类型"
    )
    status = Column(
        Enum("排队中", "执行中", "已完成", "失败", "已取消", name="crawl_status_enum"),
        nullable=False, default="排队中", comment="任务状态"
    )
    keyword = Column(String(100), nullable=True, comment="搜索关键词")
    total_count = Column(Integer, nullable=False, default=0, comment="目标采集总数")
    success_count = Column(Integer, nullable=False, default=0, comment="成功采集数")
    fail_count = Column(Integer, nullable=False, default=0, comment="失败数")
    started_at = Column(DateTime, nullable=True, comment="任务开始时间")
    finished_at = Column(DateTime, nullable=True, comment="任务结束时间")
    error_msg = Column(Text, nullable=True, comment="错误信息（失败时记录）")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="记录创建时间")

    __table_args__ = (
        Index("idx_crawl_platform", "platform"),
        Index("idx_crawl_status", "status"),
        Index("idx_crawl_started_at", "started_at"),
        Index("idx_crawl_created_at", "created_at"),
    )

    @property
    def duration_seconds(self) -> float:
        """计算任务耗时（秒）。"""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0

    @property
    def success_rate(self) -> float:
        """计算采集成功率。"""
        if self.total_count > 0:
            return round(self.success_count / self.total_count * 100, 2)
        return 0.0

    def __repr__(self) -> str:
        return f"<CrawlLog {self.log_id}: {self.platform} [{self.status}]>"
