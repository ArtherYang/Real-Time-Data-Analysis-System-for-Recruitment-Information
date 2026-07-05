"""
用户扩展信息 ORM 模型
====================
1:1 关联 users 表，存储用户的详细个人资料。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.models.database import Base


class UserProfile(Base):
    """用户扩展信息 — 1:1 关联 users"""

    __tablename__ = "user_profiles"

    profile_id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    user_id = Column(
        String(32), ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False, unique=True, comment="用户ID"
    )
    real_name = Column(String(50), nullable=True, comment="真实姓名")
    age = Column(Integer, nullable=True, comment="年龄")
    university = Column(String(100), nullable=True, comment="毕业院校")
    major = Column(String(100), nullable=True, comment="专业")
    city = Column(String(50), nullable=True, comment="所在城市")
    phone = Column(String(20), nullable=True, comment="手机号")
    avatar_url = Column(String(500), nullable=True, comment="头像URL")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "user_id": self.user_id,
            "real_name": self.real_name,
            "age": self.age,
            "university": self.university,
            "major": self.major,
            "city": self.city,
            "phone": self.phone,
            "avatar_url": self.avatar_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<UserProfile profile_id={self.profile_id} user_id={self.user_id}>"
