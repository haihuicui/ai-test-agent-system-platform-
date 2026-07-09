"""
测试用例服务

处理测试用例相关的业务逻辑
"""

from datetime import datetime
from typing import Optional, Any, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_case import TestCase
from app.repositories.test_case_repo import TestCaseRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.folder_repo import FolderRepository
from app.repositories.user_repo import UserRepository
from app.schemas.test_case import (
    TestCaseCreate, TestCaseUpdate, TestCaseInfo, TestCaseMinifiedInfo,
    TestStepInfo, BulkEditWithOperationsRequest, TestCaseHistoryResponse,
    TestCaseHistoryItem, ModifiedFieldInfo
)
from app.schemas.common import LinkInfo
from app.schemas.enums import (
    Priority, TestCaseState, TestCaseType, AutomationStatus,
    TestCaseTemplate, BulkEditOperation,
)
from app.utils.exceptions import NotFoundException, BadRequestException
from app.utils.identifier import generate_test_case_identifier
from app.config.settings import settings
from app.services.mongodb_service import MongoDBService


class TestCaseService:
    """
    测试用例服务类

    处理测试用例相关的业务逻辑
    """

    def __init__(self, session: AsyncSession, mongodb=None):
        self.session = session
        self.mongodb = mongodb
        self.repo = TestCaseRepository(session)
        self.project_repo = ProjectRepository(session)
        self.folder_repo = FolderRepository(session)
    
    async def _get_project_by_identifier(self, identifier: str):
        """获取项目，不存在则抛出异常"""
        project = await self.project_repo.get_by_identifier(identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=identifier)
        return project
    
    async def _test_case_to_info(
        self,
        tc: TestCase,
        project_identifier: str
    ) -> TestCaseInfo:
        """将测试用例模型转换为完整响应模型"""
        steps = [
            TestStepInfo(
                id=step.id,
                order=step.step_number,
                step=step.action,
                result=step.expected_result,
            )
            for step in tc.steps
        ] if tc.steps else []

        tags = [tag.name for tag in tc.tags] if tc.tags else []
        issues = tc.issues if tc.issues else []

        return TestCaseInfo(
            id=tc.id,
            identifier=tc.identifier,
            case_number=tc.case_number,
            name=tc.name,
            description=tc.description,
            preconditions=tc.preconditions,
            module=tc.module,
            priority=tc.priority,
            status=tc.state,
            case_type=tc.test_case_type,
            template=tc.template,
            automation_status=tc.automation_status,
            project_id=tc.project_id,
            folder_id=tc.folder_id,
            owner=tc.owner.email if tc.owner else None,
            created_by=tc.creator.email if tc.creator else "",
            created_at=tc.created_at,
            updated_at=tc.updated_at,
            version=tc.version,
            tags=tags,
            issues=issues,
            custom_fields=tc.custom_fields,
            test_data=tc.test_data,
            test_case_steps=steps,
            feature=tc.feature,
            scenario=tc.scenario,
            background=tc.background,
            links=LinkInfo(
                self=f"{settings.api_prefix}/projects/{project_identifier}/test-cases/{tc.identifier}",
                project=f"{settings.api_prefix}/projects/{project_identifier}",
                folder=f"{settings.api_prefix}/projects/{project_identifier}/folders/{tc.folder_id}" if tc.folder_id else None,
            ),
        )

    async def _test_case_to_minified(
        self,
        tc: TestCase
    ) -> TestCaseMinifiedInfo:
        """将测试用例模型转换为精简响应模型"""
        tags = [tag.name for tag in tc.tags] if tc.tags else []

        return TestCaseMinifiedInfo(
            id=tc.id,
            identifier=tc.identifier,
            case_number=tc.case_number,
            name=tc.name,
            module=tc.module,
            priority=tc.priority,
            status=tc.state,
            case_type=tc.test_case_type,
            folder_id=tc.folder_id,
            owner=tc.owner.email if tc.owner else None,
            tags=tags,
        )
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZOaU13PT06YmQxMzRiZTc=
    
    async def get_test_cases(
        self,
        project_identifier: str,
        offset: int = 0,
        limit: int = 30,
        minify: bool = False,
        test_case_ids: Optional[list[str]] = None,
        folder_ids: Optional[list[str]] = None,
        statuses: Optional[list[str]] = None,
        priorities: Optional[list[str]] = None,
        case_types: Optional[list[str]] = None,
        owners: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        issue_ids: Optional[list[str]] = None,
        issue_type: Optional[str] = None,
        custom_fields: Optional[dict[str, list[str]]] = None,
        updated_after: Optional[datetime] = None,
        updated_before: Optional[datetime] = None,
        search: Optional[str] = None,
    ) -> tuple[list[Union[TestCaseInfo, TestCaseMinifiedInfo]], int]:
        """
        获取测试用例列表

        支持多种过滤条件，同一参数内的多个值为 OR 关系，不同参数之间为 AND 关系
        """
        project = await self._get_project_by_identifier(project_identifier)

        # 构建过滤条件
        filters = {
            "test_case_ids": test_case_ids,
            "folder_ids": folder_ids,
            "statuses": statuses,
            "priorities": priorities,
            "case_types": case_types,
            "owners": owners,
            "tags": tags,
            "issue_ids": issue_ids,
            "issue_type": issue_type,
            "custom_fields": custom_fields,
            "updated_after": updated_after,
            "updated_before": updated_before,
            "search": search,
        }

        test_cases = await self.repo.get_by_project_with_filters(
            project.id, offset, limit, **filters
        )
        total = await self.repo.count_by_project_with_filters(project.id, **filters)

        result = []
        for tc in test_cases:
            if minify:
                info = await self._test_case_to_minified(tc)
            else:
                info = await self._test_case_to_info(tc, project_identifier)
            result.append(info)

        return result, total

    async def get_test_cases_for_export(
        self,
        project_identifier: str,
        test_case_ids: Optional[list[str]] = None,
        folder_ids: Optional[list[str]] = None,
    ) -> list[TestCaseInfo]:
        """
        获取用于导出的测试用例列表（不分页）

        支持按测试用例标识符列表或文件夹列表过滤。
        """
        project = await self._get_project_by_identifier(project_identifier)

        filters = {
            "test_case_ids": test_case_ids,
            "folder_ids": folder_ids,
            "statuses": None,
            "priorities": None,
            "case_types": None,
            "owners": None,
            "tags": None,
            "issue_ids": None,
            "issue_type": None,
            "custom_fields": None,
            "updated_after": None,
            "updated_before": None,
        }

        test_cases = await self.repo.get_by_project_with_filters(
            project.id, offset=0, limit=100_000, **filters
        )

        return [
            await self._test_case_to_info(tc, project_identifier)
            for tc in test_cases
        ]

    async def get_test_case(
        self,
        project_identifier: str,
        test_case_identifier: str,
    ) -> TestCaseInfo:
        """获取测试用例详情"""
        project = await self._get_project_by_identifier(project_identifier)
        
        tc = await self.repo.get_by_identifier(test_case_identifier)
        if not tc or tc.project_id != project.id:
            raise NotFoundException(
                resource_type="测试用例", 
                resource_id=test_case_identifier
            )
        
        return await self._test_case_to_info(tc, project_identifier)
    
    async def create_test_case(
        self,
        project_identifier: str,
        data: TestCaseCreate,
        created_by: UUID,
        folder_id: Optional[UUID] = None,
    ) -> TestCaseInfo:
        """
        创建测试用例

        支持普通测试用例和 BDD 测试用例
        """
        project = await self._get_project_by_identifier(project_identifier)

        # 验证文件夹
        if folder_id:
            folder = await self.folder_repo.get_by_id(folder_id)
            if not folder or folder.project_id != project.id:
                raise BadRequestException("文件夹不存在或不属于该项目")

        # 查找负责人
        owner_id = None
        if data.owner:
            user_repo = UserRepository(self.session)
            owner = await user_repo.get_by_email(data.owner)
            if owner:
                owner_id = owner.id

        # 生成唯一标识符（使用随机数，最多重试 10 次）
        max_retries = 10
        identifier = None
        for _ in range(max_retries):
            identifier = generate_test_case_identifier()
            if not await self.repo.identifier_exists(identifier):
                break
        else:
            # 如果 10 次都冲突，抛出异常
            raise BadRequestException("无法生成唯一的测试用例标识符，请重试")

        # 创建测试用例
        tc = await self.repo.create(
            project_id=project.id,
            folder_id=folder_id,
            identifier=identifier,
            case_number=data.case_number,
            name=data.name,
            description=data.description,
            preconditions=data.preconditions,
            module=data.module,
            priority=data.priority,
            state=data.state,
            test_case_type=data.test_case_type,
            template=data.template,
            feature=data.feature,
            scenario=data.scenario,
            background=data.background,
            automation_status=data.automation_status,
            custom_fields=data.custom_fields,
            test_data=data.test_data,
            issues=data.issues,
            owner_id=owner_id,
            created_by=created_by,
        )

        # 添加测试步骤（仅普通测试用例）
        if data.test_case_steps and data.template != TestCaseTemplate.TEST_CASE_BDD:
            for idx, step in enumerate(data.test_case_steps, 1):
                await self.repo.add_step(
                    tc.id, idx, step.step, step.result
                )

        # 添加标签
        if data.tags:
            for tag_name in data.tags:
                tag = await self.repo.get_or_create_tag(project.id, tag_name)
                await self.repo.add_tag_to_test_case(tc.id, tag)

        # 重新获取完整数据
        tc = await self.repo.get_by_id_with_relations(tc.id)
        return await self._test_case_to_info(tc, project_identifier)

    async def update_test_case(
        self,
        project_identifier: str,
        test_case_identifier: str,
        data: TestCaseUpdate,
    ) -> TestCaseInfo:
        """更新测试用例"""
        project = await self._get_project_by_identifier(project_identifier)

        tc = await self.repo.get_by_identifier(test_case_identifier)
        if not tc or tc.project_id != project.id:
            raise NotFoundException(
                resource_type="测试用例",
                resource_id=test_case_identifier
            )

        # 验证文件夹
        if data.folder_id:
            folder = await self.folder_repo.get_by_id(data.folder_id)
            if not folder or folder.project_id != project.id:
                raise BadRequestException("文件夹不存在或不属于该项目")
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZOaU13PT06YmQxMzRiZTc=

        # 更新基本信息
        update_data = data.model_dump(exclude_unset=True, exclude={"steps", "tags"})
        tc = await self.repo.update(tc, **update_data)

        # 更新标签
        if data.tags is not None:
            await self.repo.clear_test_case_tags(tc.id)
            for tag_name in data.tags:
                tag = await self.repo.get_or_create_tag(project.id, tag_name)
                await self.repo.add_tag_to_test_case(tc.id, tag)

        # 更新版本号
        tc.version = (tc.version or 1) + 1

        # 重新获取完整数据
        tc = await self.repo.get_by_id_with_relations(tc.id)
        return await self._test_case_to_info(tc, project_identifier)

    async def delete_test_case(
        self,
        project_identifier: str,
        test_case_identifier: str,
    ) -> str:
        """删除测试用例"""
        project = await self._get_project_by_identifier(project_identifier)

        tc = await self.repo.get_by_identifier(test_case_identifier)
        if not tc or tc.project_id != project.id:
            raise NotFoundException(
                resource_type="测试用例",
                resource_id=test_case_identifier
            )
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZOaU13PT06YmQxMzRiZTc=

        await self.repo.delete(tc)
        return f"测试用例 {test_case_identifier} 已成功删除"

    async def bulk_update_test_cases(
        self,
        project_identifier: str,
        test_case_ids: list[str],
        update_data: Optional[dict],
    ) -> int:
        """批量更新测试用例（简单批量更新）"""
        project = await self._get_project_by_identifier(project_identifier)

        if not update_data:
            return 0

        # 统一字段名：前端使用别名，模型使用真实列名
        normalized = dict(update_data)
        if "status" in normalized:
            normalized["state"] = normalized.pop("status")
        if "case_type" in normalized:
            normalized["test_case_type"] = normalized.pop("case_type")

        # 负责人邮箱转换为 owner_id
        owner_email = normalized.pop("owner", None)
        if owner_email is not None:
            if owner_email:
                user_repo = UserRepository(self.session)
                owner = await user_repo.get_by_email(owner_email)
                if owner:
                    normalized["owner_id"] = owner.id
            else:
                normalized["owner_id"] = None

        # 将字符串转换为对应的枚举成员，避免 SQLAlchemy 对字符串/枚举的兼容性问题
        enum_converters = {
            "state": TestCaseState,
            "priority": Priority,
            "test_case_type": TestCaseType,
            "automation_status": AutomationStatus,
        }
        for key, enum_cls in enum_converters.items():
            value = normalized.get(key)
            if value is not None:
                try:
                    normalized[key] = enum_cls(value)
                except ValueError:
                    # 非法枚举值时直接跳过，不更新该字段
                    normalized.pop(key, None)

        updated_count = 0
        for tc_identifier in test_case_ids:
            tc = await self.repo.get_by_identifier(tc_identifier)
            if not tc or tc.project_id != project.id:
                continue

            for key, value in normalized.items():
                if hasattr(tc, key):
                    setattr(tc, key, value)

            tc.version = (tc.version or 1) + 1
            updated_count += 1

        await self.session.flush()
        return updated_count

    async def bulk_update_with_operations(
        self,
        project_identifier: str,
        data: BulkEditWithOperationsRequest,
    ) -> int:
        """
        带操作符的批量更新测试用例

        支持 ignore, replace, add, remove 操作
        """
        project = await self._get_project_by_identifier(project_identifier)

        updated_count = 0
        for tc_identifier in data.test_case_ids:
            tc = await self.repo.get_by_identifier(tc_identifier)
            if not tc or tc.project_id != project.id:
                continue

            update_fields = {}

            # 处理单值字段（只支持 ignore, replace）
            single_value_fields = [
                ("automation_status", data.automation_status),
                ("case_type", data.case_type),
                ("priority", data.priority),
                ("state", data.state),
                ("owner", data.owner),
                ("preconditions", data.preconditions),
            ]

            for field_name, field_op in single_value_fields:
                if field_op and field_op.operation == BulkEditOperation.REPLACE:
                    update_fields[field_name] = field_op.value

            # 处理多值字段（支持 ignore, replace, add, remove）
            # 标签
            if data.tags and data.tags.operation != BulkEditOperation.IGNORE:
                await self._apply_list_operation(
                    tc, "tags", data.tags.operation, data.tags.value, project.id
                )

            # Issues
            if data.issues and data.issues.operation != BulkEditOperation.IGNORE:
                current_issues = tc.issues or []
                new_issues = self._apply_list_op(
                    current_issues, data.issues.operation, data.issues.value
                )
                update_fields["issues"] = new_issues

            # 自定义字段
            if data.custom_fields and data.custom_fields.operation != BulkEditOperation.IGNORE:
                current_cf = tc.custom_fields or {}
                if data.custom_fields.operation == BulkEditOperation.REPLACE:
                    update_fields["custom_fields"] = data.custom_fields.value
                elif data.custom_fields.operation == BulkEditOperation.ADD:
                    current_cf.update(data.custom_fields.value or {})
                    update_fields["custom_fields"] = current_cf
                elif data.custom_fields.operation == BulkEditOperation.REMOVE:
                    for key in (data.custom_fields.value or {}).keys():
                        current_cf.pop(key, None)
                    update_fields["custom_fields"] = current_cf

            if update_fields:
                await self.repo.update(tc, **update_fields)

            updated_count += 1

        return updated_count

    def _apply_list_op(
        self,
        current: list,
        operation: BulkEditOperation,
        value: Any
    ) -> list:
        """应用列表操作"""
        if operation == BulkEditOperation.REPLACE:
            return value or []
        elif operation == BulkEditOperation.ADD:
            return list(set(current + (value or [])))
        elif operation == BulkEditOperation.REMOVE:
            return [item for item in current if item not in (value or [])]
        return current

    async def _apply_list_operation(
        self,
        tc: TestCase,
        field: str,
        operation: BulkEditOperation,
        value: Any,
        project_id: UUID,
    ) -> None:
        """应用标签列表操作"""
        if field == "tags":
            if operation == BulkEditOperation.REPLACE:
                # 清除所有标签
                await self.repo.clear_test_case_tags(tc.id)
                # 添加新标签
                for tag_name in (value or []):
                    tag = await self.repo.get_or_create_tag(project_id, tag_name)
                    await self.repo.add_tag_to_test_case(tc.id, tag)
            elif operation == BulkEditOperation.ADD:
                # 获取现有标签
                existing_tags = await self.repo.get_test_case_tags(tc.id)
                existing_tag_names = {t.name for t in existing_tags}
                # 添加新标签
                for tag_name in (value or []):
                    if tag_name not in existing_tag_names:
                        tag = await self.repo.get_or_create_tag(project_id, tag_name)
                        await self.repo.add_tag_to_test_case(tc.id, tag)
            elif operation == BulkEditOperation.REMOVE:
                # 获取要移除的标签
                tags_to_remove = await self.repo.get_test_case_tags(tc.id)
                for tag in tags_to_remove:
                    if tag.name in (value or []):
                        await self.repo.remove_tag_from_test_case(tc.id, tag.id)
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZOaU13PT06YmQxMzRiZTc=

    async def bulk_delete_test_cases(
        self,
        project_identifier: str,
        test_case_ids: list[str],
    ) -> int:
        """批量删除测试用例"""
        project = await self._get_project_by_identifier(project_identifier)

        deleted_count = 0
        for tc_identifier in test_case_ids:
            tc = await self.repo.get_by_identifier(tc_identifier)
            if tc and tc.project_id == project.id:
                await self.repo.delete(tc)
                deleted_count += 1

        return deleted_count

    async def get_test_case_history(
        self,
        project_identifier: str,
        test_case_identifier: str,
        page: int = 1,
        page_size: int = 20,
    ) -> TestCaseHistoryResponse:
        """获取测试用例历史记录"""
        project = await self._get_project_by_identifier(project_identifier)

        tc = await self.repo.get_by_identifier(test_case_identifier)
        if not tc or tc.project_id != project.id:
            raise NotFoundException(
                resource_type="测试用例",
                resource_id=test_case_identifier
            )

        # 从 MongoDB 获取历史记录
        if not self.mongodb:
            return TestCaseHistoryResponse(
                success=True,
                info={
                    "page": page,
                    "page_size": page_size,
                    "count": 0,
                    "prev": None,
                    "next": None,
                },
                history=[]
            )

        mongodb_service = MongoDBService(self.mongodb)
        history_data = await mongodb_service.get_version_history(
            str(tc.id), page, page_size
        )

        # 转换为响应模型
        history_items = []
        for item in history_data.get("history", []):
            modified = {}
            for field, changes in item.get("modified", {}).items():
                modified[field] = ModifiedFieldInfo(
                    old=changes.get("old"),
                    new=changes.get("new")
                )

            history_items.append(TestCaseHistoryItem(
                version_id=item.get("version_id", ""),
                version_name=item.get("version_name", ""),
                source=item.get("source", "update"),
                modified_fields=item.get("modified_fields", []),
                modified=modified,
                user_id=item.get("user_id"),
                updated_by=item.get("updated_by"),
                testcase_id=test_case_identifier,
                created_at=item.get("created_at", datetime.utcnow()),
            ))

        return TestCaseHistoryResponse(
            success=True,
            info={
                "page": page,
                "page_size": page_size,
                "count": len(history_items),
                "prev": None if page <= 1 else f"?p={page-1}&page_size={page_size}",
                "next": None,  # 需要根据总数判断
            },
            history=history_items
        )
