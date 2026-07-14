"""
Web 功能管理工具

提供 Web 功能和子功能的查询和管理功能
"""

from uuid import UUID
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.tools import tool

from app.models.web_function import WebFunction, WebSubFunction
from app.models.folder import Folder
from app.config.database import async_session_factory


@tool
async def list_web_functions(
    project_identifier: str,
    folder_id: Optional[str] = None
) -> dict:
    """
    列出项目中的 Web 功能

    Args:
        project_identifier: 项目标识符
        folder_id: 文件夹 ID（可选），如果提供则只返回该文件夹下的功能

    Returns:
        dict: 包含功能列表的字典
    """
    async with async_session_factory() as session:
        # 首先通过 identifier 获取项目 ID
        from app.models.project import Project
        project_stmt = select(Project.id).where(Project.identifier == project_identifier)
        project_result = await session.execute(project_stmt)
        project_id = project_result.scalar_one_or_none()

        if not project_id:
            return {"error": f"Project {project_identifier} not found"}
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlROaFdnPT06N2MxZjJkOGQ=

        # 构建查询
        stmt = select(WebFunction).where(WebFunction.project_id == project_id)

        if folder_id:
            stmt = stmt.where(WebFunction.folder_id == UUID(folder_id))

        stmt = stmt.order_by(WebFunction.sort_order, WebFunction.created_at)

        # 执行查询
        result = await session.execute(stmt)
        functions = result.scalars().all()

        # 格式化返回
        functions_list = []
        for function in functions:
            functions_list.append({
                "id": str(function.id),
                "identifier": function.identifier,
                "display_name": function.display_name,
                "name": function.name,
                "description": function.description,
                "base_url": function.base_url,
                "business_module": function.business_module,
                "folder_id": str(function.folder_id) if function.folder_id else None,
                "total_sub_functions": function.total_sub_functions,
                "total_test_cases": function.total_test_cases,
                "total_test_runs": function.total_test_runs,
                "last_run_status": function.last_run_status,
                "sort_order": function.sort_order,
                "created_at": function.created_at.isoformat() if function.created_at else None,
            })

        return {
            "success": True,
            "functions": functions_list,
            "total": len(functions_list)
        }


@tool
async def get_function_details(
    function_id: str
) -> dict:
    """
    获取功能详情

    Args:
        function_id: 功能 ID

    Returns:
        dict: 包含功能详细信息的字典
    """
    # 验证 function_id 是否为有效的 UUID
    try:
        function_uuid = UUID(function_id)
    except (ValueError, AttributeError):
        return {"error": f"Invalid function_id format: {function_id}. Must be a valid UUID."}

    async with async_session_factory() as session:
        # 查询功能
        stmt = select(WebFunction).where(WebFunction.id == function_uuid)
        result = await session.execute(stmt)
        function = result.scalar_one_or_none()

        if not function:
            return {"error": f"Function {function_id} not found"}

        return {
            "success": True,
            "id": str(function.id),
            "identifier": function.identifier,
            "display_name": function.display_name,
            "name": function.name,
            "description": function.description,
            "base_url": function.base_url,
            "business_module": function.business_module,
            "navigation": function.navigation,
            "pages": function.pages,
            "tags": function.tags,
            "custom_config": function.custom_config,
            "folder_id": str(function.folder_id) if function.folder_id else None,
            "total_sub_functions": function.total_sub_functions,
            "total_test_cases": function.total_test_cases,
            "total_test_runs": function.total_test_runs,
            "last_run_status": function.last_run_status,
            "sort_order": function.sort_order,
            "created_at": function.created_at.isoformat() if function.created_at else None,
            "updated_at": function.updated_at.isoformat() if function.updated_at else None,
        }

# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlROaFdnPT06N2MxZjJkOGQ=

@tool
async def list_web_sub_functions(
    project_identifier: str,
    function_id: Optional[str] = None,
    folder_id: Optional[str] = None
) -> dict:
    """
    列出项目中的 Web 子功能

    Args:
        project_identifier: 项目标识符
        function_id: 功能 ID（可选），如果提供则只返回该功能下的子功能
        folder_id: 文件夹 ID（可选），如果提供则只返回该文件夹下的子功能

    Returns:
        dict: 包含子功能列表的字典
    """
    async with async_session_factory() as session:
        # 首先通过 identifier 获取项目 ID
        from app.models.project import Project
        project_stmt = select(Project.id).where(Project.identifier == project_identifier)
        project_result = await session.execute(project_stmt)
        project_id = project_result.scalar_one_or_none()

        if not project_id:
            return {"error": f"Project {project_identifier} not found"}

        # 构建查询
        stmt = select(WebSubFunction).where(WebSubFunction.project_id == project_id)

        if function_id:
            stmt = stmt.where(WebSubFunction.function_id == UUID(function_id))
        if folder_id:
            stmt = stmt.where(WebSubFunction.folder_id == UUID(folder_id))

        stmt = stmt.order_by(WebSubFunction.sort_order, WebSubFunction.created_at)

        # 执行查询
        result = await session.execute(stmt)
        sub_functions = result.scalars().all()

        # 格式化返回
        sub_functions_list = []
        for sub_function in sub_functions:
            sub_functions_list.append({
                "id": str(sub_function.id),
                "identifier": sub_function.identifier,
                "function_id": str(sub_function.function_id),
                "display_name": sub_function.display_name,
                "name": sub_function.name,
                "description": sub_function.description,
                "test_type": sub_function.test_type,
                "folder_id": str(sub_function.folder_id) if sub_function.folder_id else None,
                "total_test_cases": sub_function.total_test_cases,
                "total_test_runs": sub_function.total_test_runs,
                "last_run_status": sub_function.last_run_status,
                "priority": sub_function.priority,
                "sort_order": sub_function.sort_order,
                "created_at": sub_function.created_at.isoformat() if sub_function.created_at else None,
            })

        return {
            "success": True,
            "sub_functions": sub_functions_list,
            "total": len(sub_functions_list)
        }


@tool
async def get_sub_function_details(
    sub_function_id: str
) -> dict:
    """
    获取子功能详情

    Args:
        sub_function_id: 子功能 ID

    Returns:
        dict: 包含子功能详细信息的字典
    """
    # 验证 sub_function_id 是否为有效的 UUID
    try:
        sub_function_uuid = UUID(sub_function_id)
    except (ValueError, AttributeError):
        return {"error": f"Invalid sub_function_id format: {sub_function_id}. Must be a valid UUID."}

    async with async_session_factory() as session:
        # 查询子功能
        stmt = select(WebSubFunction).where(WebSubFunction.id == sub_function_uuid)
        result = await session.execute(stmt)
        sub_function = result.scalar_one_or_none()

        if not sub_function:
            return {"error": f"Sub-function {sub_function_id} not found"}

        return {
            "success": True,
            "id": str(sub_function.id),
            "identifier": sub_function.identifier,
            "function_id": str(sub_function.function_id),
            "display_name": sub_function.display_name,
            "name": sub_function.name,
            "description": sub_function.description,
            "test_type": sub_function.test_type,
            "target_pages": sub_function.target_pages,
            "test_scenario": sub_function.test_scenario,
            "test_data": sub_function.test_data,
            "expected_results": sub_function.expected_results,
            "priority": sub_function.priority,
            "tags": sub_function.tags,
            "custom_config": sub_function.custom_config,
            "folder_id": str(sub_function.folder_id) if sub_function.folder_id else None,
            "total_test_cases": sub_function.total_test_cases,
            "total_test_runs": sub_function.total_test_runs,
            "last_run_status": sub_function.last_run_status,
            "sort_order": sub_function.sort_order,
            "created_at": sub_function.created_at.isoformat() if sub_function.created_at else None,
            "updated_at": sub_function.updated_at.isoformat() if sub_function.updated_at else None,
        }


@tool
async def get_folder_structure(
    project_identifier: str
) -> dict:
    """
    获取文件夹结构

    Args:
        project_identifier: 项目标识符

    Returns:
        dict: 包含文件夹结构的字典
    """
    async with async_session_factory() as session:
        # 查询所有 web_test 类型的文件夹
        from app.models.folder_type import FolderType

        # 首先通过 identifier 获取项目 ID
        from app.models.project import Project
        project_stmt = select(Project.id).where(Project.identifier == project_identifier)
        project_result = await session.execute(project_stmt)
        project_id = project_result.scalar_one_or_none()

        if not project_id:
            return {"error": f"Project {project_identifier} not found"}

        stmt = select(Folder).where(
            Folder.project_id == project_id,
            Folder.folder_type == FolderType.WEB_TEST
        )
        result = await session.execute(stmt)
        folders = result.scalars().all()
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlROaFdnPT06N2MxZjJkOGQ=

        # 构建树形结构
        def build_tree(parent_id=None):
            children = []
            for folder in folders:
                if folder.parent_id == parent_id:
                    children.append({
                        "id": str(folder.id),
                        "name": folder.name,
                        "description": folder.description,
                        "parent_id": str(folder.parent_id) if folder.parent_id else None,
                        "children": build_tree(folder.id)
                    })
            return children

        tree = build_tree()

        return {
            "success": True,
            "folders": tree,
            "total": len(folders)
        }


@tool
async def create_web_function(
    project_identifier: str,
    display_name: str,
    name: str,
    folder_id: Optional[str] = None,
    description: Optional[str] = None,
    base_url: Optional[str] = None,
    business_module: Optional[str] = None,
    navigation: Optional[dict] = None,
    pages: Optional[list] = None,
    tags: Optional[list] = None,
    custom_config: Optional[dict] = None
) -> dict:
    """
    创建 Web 功能

    Args:
        project_identifier: 项目标识符
        display_name: 显示名称
        name: 功能名称（英文标识）
        folder_id: 所属文件夹 ID（可选）
        description: 功能描述（可选）
        base_url: 基础 URL（可选）
        business_module: 业务模块（可选）
        navigation: 导航配置（可选）
        pages: 页面列表（可选）
        tags: 标签列表（可选）
        custom_config: 自定义配置（可选）

    Returns:
        dict: 包含创建的功能信息的字典
    """
    async with async_session_factory() as session:
        from app.models.project import Project
        from app.repositories.web_function_repo import WebFunctionRepository

        # 获取项目
        project_stmt = select(Project).where(Project.identifier == project_identifier)
        project_result = await session.execute(project_stmt)
        project = project_result.scalar_one_or_none()

        if not project:
            return {"error": f"Project {project_identifier} not found"}

        # 使用仓库创建功能
        repo = WebFunctionRepository(session)

        # 生成下一个标识符
        identifier = await repo.get_next_identifier(project.id)

        # 创建功能
        function = await repo.create(
            project_id=project.id,
            identifier=identifier,
            display_name=display_name,
            name=name,
            folder_id=UUID(folder_id) if folder_id else None,
            description=description,
            base_url=base_url,
            business_module=business_module,
            navigation=navigation,
            pages=pages,
            tags=tags,
            custom_config=custom_config,
            sort_order=0
        )
        await session.commit()
        await session.refresh(function)

        return {
            "success": True,
            "id": str(function.id),
            "identifier": function.identifier,
            "display_name": function.display_name,
            "name": function.name,
            "message": f"Web 功能 '{display_name}' 创建成功"
        }


@tool
async def create_web_sub_function(
    project_identifier: str,
    function_id: str,
    display_name: str,
    name: str,
    folder_id: Optional[str] = None,
    description: Optional[str] = None,
    test_type: str = "functional",
    target_pages: Optional[list] = None,
    test_scenario: Optional[str] = None,
    test_data: Optional[dict] = None,
    expected_results: Optional[list] = None,
    priority: str = "medium",
    tags: Optional[list] = None,
    custom_config: Optional[dict] = None
) -> dict:
    """
    创建 Web 子功能

    Args:
        project_identifier: 项目标识符
        function_id: 所属功能 ID
        display_name: 显示名称
        name: 子功能名称（英文标识）
        folder_id: 所属文件夹 ID（可选）
        description: 子功能描述（可选）
        test_type: 测试类型（默认为 functional）
        target_pages: 目标页面列表（可选）
        test_scenario: 测试场景描述（可选）
        test_data: 测试数据（可选）
        expected_results: 预期结果列表（可选）
        priority: 优先级（默认为 medium）
        tags: 标签列表（可选）
        custom_config: 自定义配置（可选）

    Returns:
        dict: 包含创建的子功能信息的字典
    """
    async with async_session_factory() as session:
        from app.models.project import Project
        from app.repositories.web_function_repo import WebSubFunctionRepository

        # 获取项目
        project_stmt = select(Project).where(Project.identifier == project_identifier)
        project_result = await session.execute(project_stmt)
        project = project_result.scalar_one_or_none()

        if not project:
            return {"error": f"Project {project_identifier} not found"}

        # 使用仓库创建子功能
        repo = WebSubFunctionRepository(session)

        # 查询父功能，未显式指定 folder_id 时继承父功能所在文件夹，
        # 否则按文件夹过滤子功能时会查不到（前端显示"暂无功能数据"）
        function_stmt = select(WebFunction).where(WebFunction.id == UUID(function_id))
        function_result = await session.execute(function_stmt)
        parent_function = function_result.scalar_one_or_none()

        if not parent_function:
            return {"error": f"Web function {function_id} not found"}

        # 生成下一个标识符
        identifier = await repo.get_next_identifier(project.id)

        # 创建子功能
        sub_function = await repo.create(
            project_id=project.id,
            identifier=identifier,
            function_id=UUID(function_id),
            display_name=display_name,
            name=name,
            folder_id=UUID(folder_id) if folder_id else parent_function.folder_id,
            description=description,
            test_type=test_type,
            target_pages=target_pages,
            test_scenario=test_scenario,
            test_data=test_data,
            expected_results=expected_results,
            priority=priority,
            tags=tags,
            custom_config=custom_config,
            sort_order=0
        )
        await session.commit()
        await session.refresh(sub_function)
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlROaFdnPT06N2MxZjJkOGQ=

        return {
            "success": True,
            "id": str(sub_function.id),
            "identifier": sub_function.identifier,
            "display_name": sub_function.display_name,
            "name": sub_function.name,
            "message": f"Web 子功能 '{display_name}' 创建成功"
        }
