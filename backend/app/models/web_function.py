"""
Web 功能定义模型

用于存储 Web 功能和子功能的定义
每个功能可以有多个子功能，每个子功能关联测试脚本、测试用例、测试计划
"""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2V21JMFFnPT06YTUxN2IxNGM=


class WebFunction(Base, UUIDMixin, TimestampMixin):
    """
    Web 功能表

    存储业务功能的定义，如"产品管理"、"订单管理"、"用户管理"等
    每个功能可以有多个子功能
    """
    __tablename__ = "web_functions"
    __table_args__ = {"comment": "Web 功能定义表"}

    # ========== 基本信息 ==========
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID"
    )

    folder_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="所属文件夹 ID (可选，用于组织功能结构)"
    )

    # ========== 功能标识 ==========
    identifier: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="功能标识符，如 WF-1001"
    )

    display_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="功能显示名称，如 '产品管理'"
    )

    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="功能名称（英文），如 'Product Management'"
    )

    # ========== 功能详细信息 ==========
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="功能描述"
    )

    base_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="功能基础 URL"
    )

    business_module: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="业务模块标识"
    )

    # ========== 功能配置 (JSONB 存储) ==========
    navigation: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="导航配置 [{name, url, icon, description}]"
    )

    pages: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="包含的页面列表 [{url, name, type}]"
    )
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2V21JMFFnPT06YTUxN2IxNGM=

    tags: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="功能标签"
    )

    custom_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="自定义配置"
    )

    # ========== 统计信息 ==========
    total_sub_functions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="子功能总数"
    )

    total_test_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="关联的测试用例总数"
    )

    total_test_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="测试运行总数"
    )

    last_run_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="最后一次运行状态"
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="排序顺序"
    )

    # ========== 关系 ==========
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="web_functions"
    )
    folder: Mapped["Folder | None"] = relationship(
        "Folder",
        back_populates="web_functions"
    )
    sub_functions: Mapped[list["WebSubFunction"]] = relationship(
        "WebSubFunction",
        back_populates="function",
        cascade="all, delete-orphan",
        order_by="WebSubFunction.sort_order"
    )

    web_tests: Mapped[list["WebTest"]] = relationship(
        "WebTest",
        back_populates="function",
        cascade="all, delete-orphan",
        order_by="WebTest.created_at"
    )

    def __repr__(self) -> str:
        return f"<WebFunction(id={self.id}, identifier={self.identifier}, name={self.name})>"


class WebSubFunction(Base, UUIDMixin, TimestampMixin):
    """
    Web 子功能表

    存储功能下的子功能定义，如"产品管理"下的"产品添加"、"产品修改"、"产品删除"等
    每个子功能关联具体的测试脚本、测试用例、测试计划
    """
    __tablename__ = "web_sub_functions"
    __table_args__ = {"comment": "Web 子功能定义表"}

    # ========== 基本信息 ==========
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID"
    )

    function_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("web_functions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属功能 ID"
    )

    folder_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="所属文件夹 ID (可选)"
    )

    # ========== 子功能标识 ==========
    identifier: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="子功能标识符，如 WSF-1001"
    )
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2V21JMFFnPT06YTUxN2IxNGM=

    display_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="子功能显示名称，如 '产品添加'"
    )

    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="子功能名称（英文），如 'Add Product'"
    )

    # ========== 子功能详细信息 ==========
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="子功能描述"
    )

    test_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="functional",
        comment="测试类型: functional, regression, smoke, etc."
    )

    # ========== 页面和元素信息 (JSONB 存储) ==========
    target_pages: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="目标页面列表 [{url, name, elements, actions}]"
    )

    test_scenario: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="测试场景描述"
    )

    test_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="测试数据模板"
    )
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2V21JMFFnPT06YTUxN2IxNGM=

    expected_results: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="预期结果列表"
    )

    # ========== 优先级和配置 ==========
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        comment="优先级: critical, high, medium, low"
    )

    tags: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="标签"
    )

    custom_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="自定义配置"
    )

    # ========== 统计信息 ==========
    total_test_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="关联的测试用例总数"
    )

    total_test_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="测试运行总数"
    )

    last_run_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="最后一次运行状态"
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="排序顺序"
    )

    # ========== 关系 ==========
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="web_sub_functions"
    )
    folder: Mapped["Folder | None"] = relationship(
        "Folder",
        back_populates="web_sub_functions"
    )
    function: Mapped["WebFunction"] = relationship(
        "WebFunction",
        back_populates="sub_functions"
    )

    web_tests: Mapped[list["WebTest"]] = relationship(
        "WebTest",
        back_populates="sub_function",
        cascade="all, delete-orphan",
        order_by="WebTest.created_at"
    )

    def __repr__(self) -> str:
        return f"<WebSubFunction(id={self.id}, identifier={self.identifier}, name={self.name})>"
