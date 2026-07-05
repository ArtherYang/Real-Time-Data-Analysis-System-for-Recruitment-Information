"""
Company ORM 模型
=================
功能：定义公司（Company）实体的 SQLAlchemy ORM 模型。
      对应数据库 companies 表。
输入：无
输出：Company 模型类，可进行 CRUD 操作

字段说明：
    - company_id: 公司唯一标识（UUID hex, 32位）
    - name: 公司名称（唯一索引）
    - size: 公司规模
    - company_type: 公司类型（民营/国企/外企/上市）
    - industry: 所属行业（索引）
    - created_at: 记录创建时间
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Index
from app.models.database import Base


class Company(Base):
    """公司信息 ORM 模型。

    以公司名称为唯一标识，存储公司的基础属性信息。
    与 Job 表通过 company 字段（公司名称）关联。

    使用示例:
        company = Company(name="字节跳动", size="10000人以上",
                          company_type="民营", industry="互联网")
        session.add(company)
        session.commit()
    """

    __tablename__ = "companies"

    # ======================== 主键 ========================
    company_id = Column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
        comment="公司唯一标识",
    )

    # ======================== 基础信息 ========================
    name = Column(
        String(200),
        nullable=False,
        unique=True,
        index=True,
        comment="公司名称",
    )

    size = Column(
        String(50),
        nullable=True,
        comment="公司规模（如 500-2000人）",
    )

    company_type = Column(
        String(50),
        nullable=True,
        comment="公司类型（民营/国企/外企/上市公司等）",
    )

    industry = Column(
        String(100),
        nullable=True,
        index=True,
        comment="所属行业（互联网/金融/教育等）",
    )

    # ======================== 时间戳 ========================
    created_at = Column(
        DateTime,
        default=datetime.now,
        nullable=False,
        comment="记录创建时间",
    )

    # ======================== 表级约束 ========================
    __table_args__ = (
        Index("idx_company_industry", "industry"),
    )

    def to_dict(self) -> dict:
        """将模型实例转换为字典。

        Returns:
            dict: 包含所有字段的字典
        """
        return {
            "company_id": self.company_id,
            "name": self.name,
            "size": self.size,
            "company_type": self.company_type,
            "industry": self.industry,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
        }

    def __repr__(self) -> str:
        return (
            f"<Company(id='{self.company_id}', name='{self.name}', "
            f"industry='{self.industry}')>"
        )
