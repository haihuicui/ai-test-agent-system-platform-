"""
项目服务

处理项目相关的业务逻辑
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkhOQlNnPT06N2FkZDJhN2M=

from app.models.project import Project
from app.repositories.project_repo import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectInfo
from app.schemas.common import LinkInfo
from app.utils.exceptions import NotFoundException, ConflictException
from app.utils.identifier import generate_project_identifier
from app.config.settings import settings


class ProjectService:
    """
    项目服务类
    
    处理项目相关的业务逻辑
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ProjectRepository(session)
    
    async def get_projects(
        self,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[ProjectInfo], int]:
        """
        获取项目列表
        
        Args:
            offset: 偏移量
            limit: 限制数量
            
        Returns:
            tuple: (项目列表, 总数)
        """
        projects_data = await self.repo.get_all_with_counts(offset, limit)
        total = await self.repo.count()
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkhOQlNnPT06N2FkZDJhN2M=
        
        result = []
        for data in projects_data:
            project = data["project"]
            info = ProjectInfo(
                identifier=project.identifier,
                name=project.name,
                description=project.description,
                created_at=project.created_at,
                created_by=project.creator.email if project.creator else "",
                updated_at=project.updated_at,
                team_id=[t.id for t in project.teams] if project.teams else None,
                test_cases_count=data["test_cases_count"],
                folders_count=data["folders_count"],
                links=LinkInfo(
                    self=f"{settings.api_prefix}/projects/{project.identifier}",
                ),
            )
            result.append(info)
        
        return result, total
    
    async def get_project(self, project_identifier: str) -> ProjectInfo:
        """
        获取项目详情
        
        Args:
            project_identifier: 项目标识符
            
        Returns:
            ProjectInfo: 项目信息
            
        Raises:
            NotFoundException: 项目不存在
        """
        data = await self.repo.get_by_identifier_with_counts(project_identifier)
        if not data:
            raise NotFoundException(
                resource_type="项目",
                resource_id=project_identifier
            )

        project = data["project"]
        tc_count = data["test_cases_count"]
        folder_count = data["folders_count"]

        return ProjectInfo(
            identifier=project.identifier,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            created_by=project.creator.email if project.creator else "",
            updated_at=project.updated_at,
            team_id=[t.id for t in project.teams] if project.teams else None,
            test_cases_count=tc_count,
            folders_count=folder_count,
            links=LinkInfo(
                self=f"{settings.api_prefix}/projects/{project.identifier}",
                folders=f"{settings.api_prefix}/projects/{project.identifier}/folders",
                test_cases=f"{settings.api_prefix}/projects/{project.identifier}/test-cases",
            ),
        )
    
    async def create_project(
        self,
        data: ProjectCreate,
        created_by: UUID,
    ) -> ProjectInfo:
        """
        创建项目
        
        Args:
            data: 创建项目数据
            created_by: 创建者 ID
            
        Returns:
            ProjectInfo: 创建的项目信息
        """
        # 生成项目标识符
        sequence = await self.repo.get_next_sequence()
        identifier = generate_project_identifier(sequence)
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkhOQlNnPT06N2FkZDJhN2M=
        
        # 确保标识符唯一
        while await self.repo.identifier_exists(identifier):
            sequence += 1
            identifier = generate_project_identifier(sequence)
        
        # 创建项目
        project = await self.repo.create(
            identifier=identifier,
            name=data.name,
            description=data.description,
            created_by=created_by,
        )
        
        return ProjectInfo(
            identifier=project.identifier,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            created_by="",  # 需要查询用户邮箱
            team_id=data.team_id,
            test_cases_count=0,
            folders_count=0,
        )
    
    async def update_project(
        self,
        project_identifier: str,
        data: ProjectUpdate,
    ) -> ProjectInfo:
        """
        更新项目

        Args:
            project_identifier: 项目标识符
            data: 更新数据

        Returns:
            ProjectInfo: 更新后的项目信息

        Raises:
            NotFoundException: 项目不存在
        """
        project = await self.repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(
                resource_type="项目",
                resource_id=project_identifier
            )

        # 更新字段
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field != "team_id" and hasattr(project, field):
                setattr(project, field, value)

        # 刷新获取更新后的数据
        await self.session.flush()
        await self.session.refresh(project)

        return ProjectInfo(
            identifier=project.identifier,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            created_by=project.creator.email if project.creator else "",
            updated_at=project.updated_at,
            team_id=[t.id for t in project.teams] if project.teams else None,
            test_cases_count=0,
            folders_count=0,
            links=LinkInfo(
                self=f"{settings.api_prefix}/projects/{project.identifier}",
                folders=f"{settings.api_prefix}/projects/{project.identifier}/folders",
                test_cases=f"{settings.api_prefix}/projects/{project.identifier}/test-cases",
            ),
        )

    async def delete_project(self, project_identifier: str) -> str:
        """
        删除项目

        Args:
            project_identifier: 项目标识符

        Returns:
            str: 删除成功消息
        """
        project = await self.repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(
                resource_type="项目",
                resource_id=project_identifier
            )

        await self.repo.delete(project)
        return f"项目 {project_identifier} 已成功删除"

# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkhOQlNnPT06N2FkZDJhN2M=
