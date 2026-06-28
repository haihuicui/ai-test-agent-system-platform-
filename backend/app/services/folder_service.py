"""
文件夹服务

处理文件夹相关的业务逻辑
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.folder import Folder
from app.models.folder_type import FolderType
from app.models.api_endpoint import APIEndpoint
from app.repositories.folder_repo import FolderRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.folder import FolderCreate, FolderUpdate, FolderMove, FolderInfo, FolderLinks, APIEndpointSummary
from app.utils.exceptions import NotFoundException, BadRequestException
from app.config.settings import settings

# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhsalNRPT06MzE2YzI4Yzk=

class FolderService:
    """
    文件夹服务类
    
    处理文件夹相关的业务逻辑
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FolderRepository(session)
        self.project_repo = ProjectRepository(session)
    
    async def _get_project_by_identifier(self, identifier: str):
        """获取项目，不存在则抛出异常"""
        project = await self.project_repo.get_by_identifier(identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=identifier)
        return project

    async def _folder_to_info(self, folder: Folder, project_identifier: str) -> FolderInfo:
        """
        将文件夹模型转换为响应模型

        参考 BrowserStack API 响应格式:
        https://www.browserstack.com/docs/test-management/api-reference/folders

        显示格式: 直接用例数(总用例数)
        """
        data = await self.repo.get_with_counts(folder.id)

        # 如果是 API 测试文件夹，查询关联的 API 端点
        api_endpoints = []
        print(f"[FolderService] 处理文件夹: {folder.name}, type: {folder.folder_type}")

        if folder.folder_type == FolderType.API_TEST:
            endpoint_stmt = select(APIEndpoint).where(
                APIEndpoint.folder_id == folder.id
            ).order_by(APIEndpoint.sort_order, APIEndpoint.display_name)

            endpoint_result = await self.session.execute(endpoint_stmt)
            endpoints = endpoint_result.scalars().all()

            print(f"[FolderService] 文件夹 {folder.name} 找到 {len(endpoints)} 个端点")

            # 直接使用数据库中存储的统计数据
            for ep in endpoints:
                print(f"[FolderService] 端点: {ep.display_name}, total_test_cases: {ep.total_test_cases}, total_test_runs: {ep.total_test_runs}")

            api_endpoints = [
                APIEndpointSummary(
                    id=ep.id,
                    display_name=ep.display_name,
                    method=ep.method,
                    path=ep.path,
                    tag_group=ep.tag_group,
                    total_test_cases=ep.total_test_cases or 0,
                    total_test_runs=ep.total_test_runs or 0
                )
                for ep in endpoints
            ]

        # 如果是 WEB 测试文件夹，查询关联的 Web 功能
        web_functions = []
        total_sub_functions = 0  # 累计子功能数
        if folder.folder_type == FolderType.WEB_TEST:
            from app.models.web_function import WebFunction
            func_stmt = select(WebFunction).where(
                WebFunction.folder_id == folder.id
            ).order_by(WebFunction.sort_order, WebFunction.display_name)
            func_result = await self.session.execute(func_stmt)
            functions = func_result.scalars().all()

            print(f"[FolderService] 文件夹 {folder.name} 找到 {len(functions)} 个 Web 功能")

            # 累计所有功能的子功能总数
            for func in functions:
                total_sub_functions += func.total_sub_functions

            # 构造 Web 功能简要信息
            web_functions = [
                {
                    "id": str(func.id),
                    "identifier": func.identifier,
                    "display_name": func.display_name,
                    "name": func.name,
                    "description": func.description,
                    "base_url": func.base_url,
                    "business_module": func.business_module,
                    "folder_id": str(func.folder_id) if func.folder_id else None,
                    "total_sub_functions": func.total_sub_functions,
                    "total_test_cases": func.total_test_cases,
                }
                for func in functions
            ]
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhsalNRPT06MzE2YzI4Yzk=

        return FolderInfo(
            id=folder.id,
            name=folder.name,
            description=folder.description,
            folder_type=folder.folder_type,
            parent_id=folder.parent_id,
            direct_cases_count=data["direct_cases_count"] if data else 0,
            cases_count=data["cases_count"] if data else 0,
            sub_folders_count=data["sub_folders_count"] if data else 0,
            links=FolderLinks(
                sub_folders=f"{settings.api_prefix}/projects/{project_identifier}/folders/{folder.id}/sub-folders",
            ),
            api_endpoints=api_endpoints,
            web_functions=web_functions if web_functions else None,
            total_sub_functions=total_sub_functions if folder.folder_type == FolderType.WEB_TEST else None,
        )
    
    async def get_folders(
        self,
        project_identifier: str,
        offset: int = 0,
        limit: int = 30,
        folder_type: Optional[str] = None,
    ) -> tuple[list[FolderInfo], int]:
        """获取项目下的所有文件夹列表"""
        project = await self._get_project_by_identifier(project_identifier)

        folders = await self.repo.get_by_project(project.id, offset, limit, folder_type)
        total = await self.repo.count_by_project(project.id, folder_type)

        result = []
        for folder in folders:
            info = await self._folder_to_info(folder, project_identifier)
            result.append(info)

        return result, total

    async def get_root_folders(
        self,
        project_identifier: str,
        offset: int = 0,
        limit: int = 30,
        folder_type: Optional[str] = None,
    ) -> tuple[list[FolderInfo], int]:
        """获取项目下的根文件夹列表（parent_id为null）"""
        project = await self._get_project_by_identifier(project_identifier)

        folders = await self.repo.get_root_folders(project.id, offset, limit, folder_type)

        # 计算根文件夹总数
        from sqlalchemy import func, select
        from app.models.folder import Folder as FolderModel
        from app.models.folder_type import FolderType

        count_query = select(func.count()).select_from(FolderModel).where(
            FolderModel.project_id == project.id
        ).where(FolderModel.parent_id.is_(None))

        if folder_type:
            count_query = count_query.where(FolderModel.folder_type == FolderType(folder_type))

        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        result = []
        for folder in folders:
            info = await self._folder_to_info(folder, project_identifier)
            result.append(info)

        return result, total

    async def get_folder(
        self,
        project_identifier: str,
        folder_id: UUID,
    ) -> FolderInfo:
        """获取文件夹详情"""
        project = await self._get_project_by_identifier(project_identifier)
        
        folder = await self.repo.get_by_id(folder_id)
        if not folder or folder.project_id != project.id:
            raise NotFoundException(resource_type="文件夹", resource_id=str(folder_id))
        
        return await self._folder_to_info(folder, project_identifier)
    
    async def get_sub_folders(
        self,
        project_identifier: str,
        folder_id: UUID,
        offset: int = 0,
        limit: int = 30,
        folder_type: Optional[str] = None,
    ) -> tuple[list[FolderInfo], int]:
        """获取子文件夹列表"""
        project = await self._get_project_by_identifier(project_identifier)

        folder = await self.repo.get_by_id(folder_id)
        if not folder or folder.project_id != project.id:
            raise NotFoundException(resource_type="文件夹", resource_id=str(folder_id))
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhsalNRPT06MzE2YzI4Yzk=

        sub_folders = await self.repo.get_sub_folders(folder_id, offset, limit, folder_type)

        result = []
        for sub in sub_folders:
            info = await self._folder_to_info(sub, project_identifier)
            result.append(info)

        # 简化：子文件夹总数
        from sqlalchemy import func, select
        from app.models.folder import Folder as FolderModel
        from app.models.folder_type import FolderType

        count_query = select(func.count()).select_from(FolderModel).where(
            FolderModel.parent_id == folder_id
        )

        if folder_type:
            count_query = count_query.where(FolderModel.folder_type == FolderType(folder_type))

        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        return result, total
    
    async def create_folder(
        self,
        project_identifier: str,
        data: FolderCreate,
    ) -> FolderInfo:
        """创建文件夹"""
        project = await self._get_project_by_identifier(project_identifier)

        # 验证父文件夹
        if data.parent_id:
            parent = await self.repo.get_by_id(data.parent_id)
            if not parent or parent.project_id != project.id:
                raise BadRequestException("父文件夹不存在或不属于该项目")

        folder = await self.repo.create(
            project_id=project.id,
            parent_id=data.parent_id,
            name=data.name,
            description=data.description,
            folder_type=data.folder_type,
        )

        return await self._folder_to_info(folder, project_identifier)
    
    async def update_folder(
        self,
        project_identifier: str,
        folder_id: UUID,
        data: FolderUpdate,
    ) -> FolderInfo:
        """更新文件夹"""
        project = await self._get_project_by_identifier(project_identifier)
        
        folder = await self.repo.get_by_id(folder_id)
        if not folder or folder.project_id != project.id:
            raise NotFoundException(resource_type="文件夹", resource_id=str(folder_id))
        
        folder = await self.repo.update(
            folder,
            name=data.name,
            description=data.description,
        )
        
        return await self._folder_to_info(folder, project_identifier)
    
    async def delete_folder(
        self,
        project_identifier: str,
        folder_id: UUID,
    ) -> str:
        """删除文件夹"""
        project = await self._get_project_by_identifier(project_identifier)
        
        folder = await self.repo.get_by_id(folder_id)
        if not folder or folder.project_id != project.id:
            raise NotFoundException(resource_type="文件夹", resource_id=str(folder_id))
        
        await self.repo.delete(folder)
        return f"文件夹 {folder_id} 已成功删除"

    async def move_folder(
        self,
        project_identifier: str,
        folder_id: UUID,
        data: FolderMove,
    ) -> FolderInfo:
        """
        移动文件夹到新位置

        参考: https://www.browserstack.com/docs/test-management/api-reference/folders#move-a-folder

        Args:
            project_identifier: 项目标识符
            folder_id: 文件夹 ID
            data: 移动请求数据 (parent_id: 目标父文件夹 ID，为 null 则移动到根目录)

        Returns:
            FolderInfo: 移动后的文件夹信息
        """
        project = await self._get_project_by_identifier(project_identifier)

        folder = await self.repo.get_by_id(folder_id)
        if not folder or folder.project_id != project.id:
            raise NotFoundException(resource_type="文件夹", resource_id=str(folder_id))

        # 验证目标父文件夹
        if data.parent_id:
            dest = await self.repo.get_by_id(data.parent_id)
            if not dest or dest.project_id != project.id:
                raise BadRequestException("目标父文件夹不存在或不属于该项目")

            # 检查是否移动到自己
            if data.parent_id == folder_id:
                raise BadRequestException("不能将文件夹移动到自身")
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhsalNRPT06MzE2YzI4Yzk=

            # 检查是否是子文件夹（防止循环引用）
            current = dest
            while current.parent_id:
                if current.parent_id == folder_id:
                    raise BadRequestException("不能将文件夹移动到其子文件夹中")
                current = await self.repo.get_by_id(current.parent_id)

        folder = await self.repo.move_folder(folder, data.parent_id)
        return await self._folder_to_info(folder, project_identifier)

    async def copy_folder(
        self,
        project_identifier: str,
        folder_id: UUID,
    ) -> FolderInfo:
        """
        复制文件夹及其所有内容

        Args:
            project_identifier: 项目标识符
            folder_id: 源文件夹 ID

        Returns:
            FolderInfo: 新创建的文件夹信息
        """
        project = await self._get_project_by_identifier(project_identifier)

        folder = await self.repo.get_by_id(folder_id)
        if not folder or folder.project_id != project.id:
            raise NotFoundException(resource_type="文件夹", resource_id=str(folder_id))

        # 复制文件夹（递归复制）
        new_folder = await self.repo.copy_folder(folder, f"{folder.name} (副本)")

        return await self._folder_to_info(new_folder, project_identifier)

