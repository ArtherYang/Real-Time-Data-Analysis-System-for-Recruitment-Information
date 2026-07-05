"""
用户 ORM 模型
=============
定义 users 表的 SQLAlchemy 映射，支持注册登录和角色管理。

密码安全：使用 bcrypt 哈希加密存储，不支持明文密码。
"""

import uuid
from datetime import datetime, timezone

_UTC_NOW = lambda: datetime.now(timezone.utc).replace(tzinfo=None)
from sqlalchemy import Column, String, DateTime, Enum, Boolean, Integer, Index
from app.models.database import Base


def generate_uuid() -> str:
    """生成32位UUID（去连字符），用作主键。"""
    return uuid.uuid4().hex


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    # ==== 主键 ====
    user_id = Column(String(32), primary_key=True, default=generate_uuid, comment="用户唯一标识")

    # ==== 账号信息 ====
    email = Column(String(100), nullable=True, unique=True, comment="邮箱地址")
    phone = Column(String(20), nullable=True, unique=True, comment="手机号")
    password_hash = Column(String(255), nullable=False, comment="bcrypt密码哈希")
    nickname = Column(String(50), nullable=False, comment="用户昵称")

    # ==== 角色与状态 ====
    role = Column(
        Enum("普通用户", "企业HR", "管理员", name="user_role_enum"),
        nullable=False, default="普通用户", comment="用户角色"
    )
    avatar_url = Column(String(500), nullable=True, comment="头像URL")
    is_active = Column(Boolean, nullable=False, default=True, comment="账号是否启用")

    # ==== 时间 ====
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="注册时间")
    last_login = Column(DateTime, nullable=True, comment="最后登录时间")

    # ==== 登录安全 ====
    login_attempts = Column(Integer, nullable=False, default=0, comment="连续登录失败次数")
    locked_until = Column(DateTime, nullable=True, comment="账号锁定截止时间")

    __table_args__ = (
        Index("idx_email", "email"),
        Index("idx_phone", "phone"),
        Index("idx_role", "role"),
        Index("idx_created_at", "created_at"),
    )

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        将模型实例转换为字典。

        Args:
            include_sensitive: 是否包含敏感字段（password_hash等），默认不包含。
        """
        result = {
            "user_id": self.user_id,
            "email": self.email,
            "phone": self._mask_phone(self.phone) if self.phone else None,
            "nickname": self.nickname,
            "role": self.role,
            "avatar_url": self.avatar_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
        if include_sensitive:
            result["password_hash"] = self.password_hash
            result["phone"] = self.phone  # 原始手机号（不脱敏）
            result["is_active"] = self.is_active
            result["login_attempts"] = self.login_attempts
        return result

    @staticmethod
    def _mask_phone(phone: str) -> str:
        """手机号脱敏：138****5678"""
        if not phone or len(phone) < 7:
            return phone
        return phone[:3] + "****" + phone[-4:]

    def is_locked(self) -> bool:
        """检查账号是否处于锁定状态。"""
        if self.locked_until and self.locked_until > _UTC_NOW():
            return True
        return False

    def __repr__(self) -> str:
        return f"<User {self.user_id}: {self.nickname} ({self.role})>"
