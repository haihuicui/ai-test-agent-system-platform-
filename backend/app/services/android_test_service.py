"""
Android 测试服务

处理 Android 测试相关的业务逻辑
"""

import logging
from typing import Optional
from uuid import UUID
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUROcmRBPT06YmFhODUyZTE=

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.android_test import AndroidTest
from app.repositories.android_test_repo import AndroidTestRepository
from app.repositories.project_repo import ProjectRepository
from app.utils.adb_utils import scan_devices
from app.utils.exceptions import NotFoundException

logger = logging.getLogger(__name__)


class AndroidTestService:
    """Android 测试服务类"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.android_test_repo = AndroidTestRepository(session)
        self.project_repo = ProjectRepository(session)

    async def _get_project_by_identifier(self, identifier: str):
        """获取项目，不存在则抛出异常"""
        project = await self.project_repo.get_by_identifier(identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=identifier)
        return project

    # ==================== Android 功能管理 ====================

    async def create_android_function(
        self,
        project_identifier: str,
        display_name: str,
        name: str,
        folder_id: Optional[str] = None,
        description: Optional[str] = None,
        app_package: Optional[str] = None,
        app_activity: Optional[str] = None,
        device_udid: Optional[str] = None,
        business_module: Optional[str] = None,
        script_format: str = "midscene",
        script_language: str = "typescript",
        test_config: Optional[dict] = None,
        pages: Optional[list] = None,
        tags: Optional[list] = None,
        custom_config: Optional[dict] = None,
        sort_order: int = 0,
    ) -> dict:
        """创建 Android 功能"""
        project = await self._get_project_by_identifier(project_identifier)
        identifier = await self.android_test_repo.get_next_identifier(project.id)

        android_test = await self.android_test_repo.create(
            project_id=project.id,
            identifier=identifier,
            name=display_name,
            description=description,
            folder_id=UUID(folder_id) if folder_id else None,
            app_package=app_package,
            app_activity=app_activity,
            device_udid=device_udid,
            script_path="",
            script_format=script_format,
            script_language=script_language,
            test_config=test_config or {},
            test_scenarios=[],
            generation_params={},
        )

        return self._to_function_dict(android_test)

    async def get_android_function(
        self,
        function_id: str,
    ) -> dict:
        """获取 Android 功能详情"""
        android_test = await self.android_test_repo.get_by_id_with_relations(UUID(function_id))

        if not android_test:
            raise NotFoundException(resource_type="Android 功能", resource_id=function_id)

        return self._to_function_detail_dict(android_test)

    async def list_android_functions(
        self,
        project_identifier: str,
        folder_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
    ) -> dict:
        """获取 Android 功能列表"""
        project = await self._get_project_by_identifier(project_identifier)

        if folder_id:
            items, total = await self.android_test_repo.get_by_folder(
                UUID(folder_id),
                offset=offset,
                limit=limit,
                search=search,
            )
        else:
            items, total = await self.android_test_repo.get_by_project(
                project.id,
                offset=offset,
                limit=limit,
                search=search,
            )

        return {
            "items": [self._to_function_dict(item) for item in items],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    async def update_android_function(
        self,
        function_id: str,
        display_name: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        app_package: Optional[str] = None,
        app_activity: Optional[str] = None,
        device_udid: Optional[str] = None,
        business_module: Optional[str] = None,
        script_format: Optional[str] = None,
        script_language: Optional[str] = None,
        test_config: Optional[dict] = None,
        pages: Optional[list] = None,
        tags: Optional[list] = None,
        custom_config: Optional[dict] = None,
        sort_order: Optional[int] = None,
    ) -> dict:
        """更新 Android 功能"""
        android_test = await self.android_test_repo.get_by_id(UUID(function_id))
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUROcmRBPT06YmFhODUyZTE=

        if not android_test:
            raise NotFoundException(resource_type="Android 功能", resource_id=function_id)

        update_data = {}
        if display_name is not None:
            update_data["name"] = display_name
        if description is not None:
            update_data["description"] = description
        if app_package is not None:
            update_data["app_package"] = app_package
        if app_activity is not None:
            update_data["app_activity"] = app_activity
        if device_udid is not None:
            update_data["device_udid"] = device_udid
        if script_format is not None:
            update_data["script_format"] = script_format
        if script_language is not None:
            update_data["script_language"] = script_language
        if test_config is not None:
            update_data["test_config"] = test_config

        updated = await self.android_test_repo.update(android_test, **update_data)

        return self._to_function_dict(updated)

    async def delete_android_function(
        self,
        function_id: str,
    ) -> dict:
        """删除 Android 功能"""
        android_test = await self.android_test_repo.get_by_id(UUID(function_id))

        if not android_test:
            raise NotFoundException(resource_type="Android 功能", resource_id=function_id)

        await self.android_test_repo.delete(android_test)
        await self.session.commit()

        return {"success": True, "message": "Android 功能已删除"}
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUROcmRBPT06YmFhODUyZTE=

    # ==================== 子功能接口（兼容前端）====================

    async def list_android_sub_functions(
        self,
        project_identifier: str,
        function_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
    ) -> dict:
        """
        获取 Android 子功能列表

        由于 Android 测试模型没有子功能的分层结构，
        这里将每个 Android 测试作为主功能返回，
        同时为每个测试生成一个默认的子功能条目。
        """
        project = await self._get_project_by_identifier(project_identifier)

        items, total = await self.android_test_repo.get_by_project(
            project.id,
            offset=offset,
            limit=limit,
            search=search,
        )

        sub_functions = []
        for item in items:
            # 为每个 Android 测试生成一个兼容的子功能条目
            sub_functions.append({
                "id": str(item.id),
                "identifier": item.identifier,
                "function_id": str(item.id),
                "display_name": item.name,
                "name": item.identifier.lower().replace("-", "_"),
                "description": item.description,
                "test_type": "functional",
                "target_pages": [],
                "test_scenario": None,
                "test_data": None,
                "expected_results": None,
                "priority": "medium",
                "tags": [],
                "custom_config": item.test_config,
                "folder_id": str(item.folder_id) if item.folder_id else None,
                "total_test_cases": item.total_cases,
                "total_test_runs": 0,
                "last_run_status": None,
                "sort_order": 0,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            })

        return {
            "items": sub_functions,
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    async def get_android_sub_function(
        self,
        sub_function_id: str,
    ) -> dict:
        """获取 Android 子功能详情"""
        android_test = await self.android_test_repo.get_by_id_with_relations(UUID(sub_function_id))

        if not android_test:
            raise NotFoundException(resource_type="Android 子功能", resource_id=sub_function_id)

        return {
            "id": str(android_test.id),
            "identifier": android_test.identifier,
            "function_id": str(android_test.id),
            "display_name": android_test.name,
            "name": android_test.identifier.lower().replace("-", "_"),
            "description": android_test.description,
            "test_type": "functional",
            "target_pages": [],
            "test_scenario": None,
            "test_data": None,
            "expected_results": None,
            "priority": "medium",
            "tags": [],
            "custom_config": android_test.test_config,
            "folder_id": str(android_test.folder_id) if android_test.folder_id else None,
            "total_test_cases": android_test.total_cases,
            "total_test_runs": 0,
            "last_run_status": None,
            "sort_order": 0,
            "created_at": android_test.created_at.isoformat() if android_test.created_at else None,
            "updated_at": android_test.updated_at.isoformat() if android_test.updated_at else None,
        }

    # ==================== 设备管理 ====================
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUROcmRBPT06YmFhODUyZTE=

    async def list_android_devices(
        self,
        project_identifier: str,
    ) -> list[dict]:
        """
        获取 Android 设备列表

        通过 ADB 扫描已连接的 Android 设备并返回详细信息。
        """
        try:
            devices = await scan_devices()
            return devices
        except FileNotFoundError as e:
            logger.warning("ADB 未找到: %s", e)
            return []
        except Exception as e:
            logger.exception("获取 Android 设备列表失败: %s", e)
            return []

    async def refresh_android_devices(
        self,
        project_identifier: str,
    ) -> list[dict]:
        """
        刷新 Android 设备列表

        重新通过 ADB 扫描已连接的 Android 设备并返回详细信息。
        """
        try:
            devices = await scan_devices()
            return devices
        except FileNotFoundError as e:
            logger.warning("ADB 未找到: %s", e)
            return []
        except Exception as e:
            logger.exception("刷新 Android 设备列表失败: %s", e)
            return []

    # ==================== 辅助方法 ====================

    def _to_function_dict(self, item: AndroidTest) -> dict:
        """将 AndroidTest 转换为功能字典"""
        return {
            "id": str(item.id),
            "identifier": item.identifier,
            "display_name": item.name,
            "name": item.identifier.lower().replace("-", "_"),
            "description": item.description,
            "app_package": item.app_package,
            "app_activity": item.app_activity,
            "device_udid": item.device_udid,
            "business_module": None,
            "script_format": item.script_format,
            "script_language": item.script_language,
            "test_config": item.test_config,
            "pages": [],
            "tags": [],
            "custom_config": item.test_config,
            "folder_id": str(item.folder_id) if item.folder_id else None,
            "total_sub_functions": 1,
            "total_test_cases": item.total_cases,
            "total_test_runs": 0,
            "last_run_status": None,
            "sort_order": 0,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

    def _to_function_detail_dict(self, item: AndroidTest) -> dict:
        """将 AndroidTest 转换为详细功能字典"""
        return {
            "id": str(item.id),
            "identifier": item.identifier,
            "display_name": item.name,
            "name": item.identifier.lower().replace("-", "_"),
            "description": item.description,
            "app_package": item.app_package,
            "app_activity": item.app_activity,
            "device_udid": item.device_udid,
            "business_module": None,
            "script_format": item.script_format,
            "script_language": item.script_language,
            "test_config": item.test_config,
            "pages": [],
            "tags": [],
            "custom_config": item.test_config,
            "folder_id": str(item.folder_id) if item.folder_id else None,
            "total_sub_functions": 1,
            "total_test_cases": item.total_cases,
            "total_test_runs": 0,
            "last_run_status": None,
            "sort_order": 0,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
