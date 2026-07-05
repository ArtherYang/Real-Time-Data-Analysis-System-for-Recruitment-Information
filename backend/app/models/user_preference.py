"""
用户求职意向 ORM 模型
=====================
1:1 关联 users 表，存储用户的求职偏好设置。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.models.database import Base


class UserPreference(Base):
    """用户求职意向 — 1:1 关联 users"""

    __tablename__ = "user_preferences"

    pref_id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    user_id = Column(
        String(32), ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False, unique=True, comment="用户ID"
    )
    desired_position = Column(String(100), nullable=True, comment="意向岗位")
    desired_city = Column(String(50), nullable=True, comment="意向城市")
    desired_salary_min = Column(Integer, nullable=True, comment="期望最低薪资")
    desired_salary_max = Column(Integer, nullable=True, comment="期望最高薪资")
    industry_pref = Column(String(50), nullable=True, comment="偏好行业")
    job_type_pref = Column(String(20), nullable=True, comment="偏好工作类型")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    def to_dict(self) -> dict:
        return {
            "pref_id": self.pref_id,
            "user_id": self.user_id,
            "desired_position": self.desired_position,
            "desired_city": self.desired_city,
            "desired_salary_min": self.desired_salary_min,
            "desired_salary_max": self.desired_salary_max,
            "industry_pref": self.industry_pref,
            "job_type_pref": self.job_type_pref,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<UserPreference pref_id={self.pref_id} user_id={self.user_id}>"
