"""
配置模型

定义测试配置（操作系统、浏览器、设备组合）的表结构
参考: https://www.browserstack.com/docs/test-management/api-reference/configurations
"""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0RoVE5BPT06MGIyYWVjZTI=

from app.models.base import Base, TimestampMixin


class Configuration(Base, TimestampMixin):
    """
    配置表

    存储测试配置信息，包括操作系统、浏览器、设备组合
    配置分为系统定义（is_system=True）和用户自定义（is_system=False）
    """
    __tablename__ = "configurations"
    __table_args__ = {"comment": "测试配置表"}

    # 主键使用整数 ID（符合 BrowserStack API）
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="配置 ID"
    )
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0RoVE5BPT06MGIyYWVjZTI=
    
    # 配置名称
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="配置名称"
    )
    
    # 操作系统信息
    os: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="操作系统"
    )
    os_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="操作系统版本"
    )
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0RoVE5BPT06MGIyYWVjZTI=
    
    # 设备信息
    device: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="设备"
    )
    
    # 浏览器信息
    browser: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="浏览器"
    )
    browser_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="浏览器版本"
    )
    
    # 是否为系统定义
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否为系统定义配置"
    )
    
    # 描述
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="配置描述"
    )

    def __repr__(self) -> str:
        return f"<Configuration(id={self.id}, name={self.name})>"
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0RoVE5BPT06MGIyYWVjZTI=

