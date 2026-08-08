"""
文件夹服务

处理文件夹相关的业务逻辑
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func as sa_func, select

from app.models.folder import Folder
from app.models.folder_type import FolderType
from app.models.api_endpoint import APIEndpoint
from app.models.test_case import TestCase
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

    async def _folders_to_infos(
        self,
        folders: list[Folder],
        project_identifier: str,
        project_id: UUID,
    ) -> list[FolderInfo]:
        """
        批量将文件夹模型转换为响应模型（消除 N+1）。

        原实现每个文件夹 5-6 次查询（详情/子文件夹数/直接用例/递归 CTE 总用例/
        递归 CTE 端点数/端点列表），N 个文件夹约 6N 次查询。
        本实现：项目树骨架 + 分组统计，恒定 4-7 次查询，子树合计在内存完成。
        """
        if not folders:
            return []

        # Q1: 项目全量文件夹树骨架（id, parent_id），用于直接子数与子树聚合
        skel_result = await self.session.execute(
            select(Folder.id, Folder.parent_id).where(Folder.project_id == project_id)
        )
        children: dict[UUID, list[UUID]] = {}
        all_ids: list[UUID] = []
        for row in skel_result.all():
            all_ids.append(row[0])
            if row[1] is not None:
                children.setdefault(row[1], []).append(row[0])

        # Q2/Q3: 各文件夹直接用例数 / 直接端点数（GROUP BY 一次查出）
        direct_cases: dict[UUID, int] = {}
        direct_eps: dict[UUID, int] = {}
        if all_ids:
            case_rows = await self.session.execute(
                select(TestCase.folder_id, sa_func.count(TestCase.id))
                .where(TestCase.folder_id.in_(all_ids))
                .group_by(TestCase.folder_id)
            )
            direct_cases = {row[0]: int(row[1]) for row in case_rows.all()}

            ep_rows = await self.session.execute(
                select(APIEndpoint.folder_id, sa_func.count(APIEndpoint.id))
                .where(APIEndpoint.folder_id.in_(all_ids))
                .group_by(APIEndpoint.folder_id)
            )
            direct_eps = {row[0]: int(row[1]) for row in ep_rows.all()}

        def subtree_total(folder_id: UUID, direct: dict[UUID, int]) -> int:
            """子树合计（迭代 DFS，带环路保护）"""
            total = 0
            seen: set[UUID] = set()
            stack = [folder_id]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                total += direct.get(cur, 0)
                stack.extend(children.get(cur, ()))
            return total

        # Q4: 本页 API_TEST 文件夹的端点列表（一次查出后按 folder_id 分组）
        api_folder_ids = [f.id for f in folders if f.folder_type == FolderType.API_TEST]
        eps_by_folder: dict[UUID, list] = {}
        if api_folder_ids:
            ep_result = await self.session.execute(
                select(APIEndpoint)
                .where(APIEndpoint.folder_id.in_(api_folder_ids))
                .order_by(APIEndpoint.folder_id, APIEndpoint.sort_order, APIEndpoint.display_name)
            )
            for ep in ep_result.scalars().all():
                eps_by_folder.setdefault(ep.folder_id, []).append(ep)

        # Q5/Q6: 本页 WEB_TEST 文件夹的功能列表 + 子功能数/用例数分组统计
        web_folder_ids = [f.id for f in folders if f.folder_type == FolderType.WEB_TEST]
        funcs_by_folder: dict[UUID, list] = {}
        sub_func_counts: dict[str, int] = {}
        test_case_sums: dict[str, int] = {}
        if web_folder_ids:
            from app.models.web_function import WebFunction, WebSubFunction

            func_result = await self.session.execute(
                select(WebFunction)
                .where(WebFunction.folder_id.in_(web_folder_ids))
                .order_by(WebFunction.folder_id, WebFunction.sort_order, WebFunction.display_name)
            )
            all_func_ids = []
            for wf in func_result.scalars().all():
                funcs_by_folder.setdefault(wf.folder_id, []).append(wf)
                all_func_ids.append(wf.id)

            if all_func_ids:
                sub_func_count_result = await self.session.execute(
                    select(WebSubFunction.function_id, sa_func.count(WebSubFunction.id))
                    .where(WebSubFunction.function_id.in_(all_func_ids))
                    .group_by(WebSubFunction.function_id)
                )
                sub_func_counts = {str(row[0]): row[1] for row in sub_func_count_result.all()}

                test_case_sum_result = await self.session.execute(
                    select(WebSubFunction.function_id, sa_func.sum(WebSubFunction.total_test_cases))
                    .where(WebSubFunction.function_id.in_(all_func_ids))
                    .group_by(WebSubFunction.function_id)
                )
                test_case_sums = {
                    str(row[0]): int(row[1]) if row[1] is not None else 0
                    for row in test_case_sum_result.all()
                }

        infos: list[FolderInfo] = []
        for folder in folders:
            api_endpoints = [
                APIEndpointSummary(
                    id=ep.id,
                    display_name=ep.display_name,
                    method=ep.method,
                    path=ep.path,
                    tag_group=ep.tag_group,
                    total_test_cases=ep.total_test_cases or 0,
                    total_test_runs=ep.total_test_runs or 0,
                )
                for ep in eps_by_folder.get(folder.id, [])
            ]

            web_functions: list[dict] = []
            total_sub_functions = 0
            if folder.folder_type == FolderType.WEB_TEST:
                for wf in funcs_by_folder.get(folder.id, []):
                    wf_sub_count = sub_func_counts.get(str(wf.id), 0)
                    wf_tc_sum = test_case_sums.get(str(wf.id), 0)
                    total_sub_functions += wf_sub_count
                    web_functions.append({
                        "id": str(wf.id),
                        "identifier": wf.identifier,
                        "display_name": wf.display_name,
                        "name": wf.name,
                        "description": wf.description,
                        "base_url": wf.base_url,
                        "business_module": wf.business_module,
                        "folder_id": str(wf.folder_id) if wf.folder_id else None,
                        "total_sub_functions": wf_sub_count,
                        "total_test_cases": wf_tc_sum,
                    })

            infos.append(FolderInfo(
                id=folder.id,
                name=folder.name,
                description=folder.description,
                folder_type=folder.folder_type,
                parent_id=folder.parent_id,
                direct_cases_count=direct_cases.get(folder.id, 0),
                cases_count=subtree_total(folder.id, direct_cases),
                sub_folders_count=len(children.get(folder.id, [])),
                endpoints_count=subtree_total(folder.id, direct_eps),
                links=FolderLinks(
                    sub_folders=f"{settings.api_prefix}/projects/{project_identifier}/folders/{folder.id}/sub-folders",
                ),
                api_endpoints=api_endpoints,
                web_functions=web_functions if web_functions else None,
                total_sub_functions=total_sub_functions if folder.folder_type == FolderType.WEB_TEST else None,
            ))

        return infos

    async def _folder_to_info(self, folder: Folder, project_identifier: str) -> FolderInfo:
        """单文件夹转换（走批量实现，消除 N+1；保留签名兼容所有调用点）"""
        project = await self._get_project_by_identifier(project_identifier)
        infos = await self._folders_to_infos([folder], project_identifier, project.id)
        return infos[0]
    
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
        from sqlalchemy import func as sa_func, select
        from app.models.folder import Folder as FolderModel
        from app.models.folder_type import FolderType

        count_query = select(sa_func.count()).select_from(FolderModel).where(
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
        from sqlalchemy import func as sa_func, select
        from app.models.folder import Folder as FolderModel
        from app.models.folder_type import FolderType

        count_query = select(sa_func.count()).select_from(FolderModel).where(
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

