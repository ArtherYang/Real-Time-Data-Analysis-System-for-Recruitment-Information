"""
简历 ORM 模型
=============
用户简历主表，关联 users 和 resume_templates 表。
"""

import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from app.models.database import Base


class Resume(Base):
    """用户简历 — N:1 关联 users, N:1 关联 resume_templates"""

    __tablename__ = "resumes"

    resume_id = Column(Integer, primary_key=True, autoincrement=True, comment="简历ID")
    user_id = Column(
        String(32), ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False, index=True, comment="用户ID"
    )
    template_id = Column(
        Integer, ForeignKey("resume_templates.template_id"),
        nullable=False, default=1, index=True, comment="模板ID"
    )
    full_name = Column(String(50), nullable=False, comment="姓名")
    email = Column(String(100), nullable=True, comment="联系邮箱")
    phone = Column(String(20), nullable=True, comment="联系电话")
    university = Column(String(100), nullable=True, comment="毕业院校")
    major = Column(String(100), nullable=True, comment="专业")
    degree = Column(String(20), nullable=True, comment="学历")
    graduation_year = Column(Integer, nullable=True, comment="毕业年份")
    skills_text = Column(Text, nullable=True, comment="技能描述")
    work_experience = Column(Text, nullable=True, comment="工作经历（JSON格式）")
    project_experience = Column(Text, nullable=True, comment="项目经历（JSON格式）")
    self_intro = Column(Text, nullable=True, comment="自我评价")
    status = Column(String(20), default="draft", index=True, comment="状态（draft/published）")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    def to_dict(self) -> dict:
        return {
            "resume_id": self.resume_id,
            "user_id": self.user_id,
            "template_id": self.template_id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "university": self.university,
            "major": self.major,
            "degree": self.degree,
            "graduation_year": self.graduation_year,
            "skills_text": self.skills_text,
            "work_experience": self._parse_json(self.work_experience),
            "project_experience": self._parse_json(self.project_experience),
            "self_intro": self.self_intro,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def _parse_json(value):
        """安全解析 JSON 字符串，解析失败返回原值。"""
        if value is None:
            return None
        try:
            return json.loads(value) if isinstance(value, str) else value
        except (json.JSONDecodeError, TypeError):
            return value

    def __repr__(self) -> str:
        return f"<Resume resume_id={self.resume_id} user_id={self.user_id} status={self.status}>"


class ResumeTemplate(Base):
    """简历模板"""

    __tablename__ = "resume_templates"

    template_id = Column(Integer, primary_key=True, autoincrement=True, comment="模板ID")
    name = Column(String(50), nullable=False, comment="模板名称")
    preview_url = Column(String(500), nullable=True, comment="预览图URL")
    css_styles = Column(Text, nullable=True, comment="CSS样式定义（JSON）")
    is_active = Column(Integer, default=1, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "preview_url": self.preview_url,
            "css_styles": Resume._parse_json(self.css_styles),
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<ResumeTemplate template_id={self.template_id} name={self.name}>"
