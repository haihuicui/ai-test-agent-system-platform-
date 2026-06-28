"""
测试结果服务

处理测试结果相关的业务逻辑
参考: https://www.browserstack.com/docs/test-management/api-reference/test-results
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1RoVlpnPT06NGEzZmJhMGE=

from app.models.test_result import TestResult, TestStepResult
from app.models.test_run import TestRunTestCase
from app.repositories.test_result_repo import TestResultRepository
from app.repositories.test_run_repo import TestRunRepository, TestRunTestCaseRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.test_case_repo import TestCaseRepository
from app.schemas.test_result import (
    TestResultCreate,
    TestResultItem,
    TestResultInfo,
    TestResultListInfo,
    TestResultHistoryInfo,
    StepResultInfo,
    ResultStatus,
    IssueInfo,
    CustomFieldValue,
)
from app.schemas.enums import TestResultStatus
from app.utils.exceptions import NotFoundException, BadRequestException


class TestResultService:
    """测试结果服务类"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TestResultRepository(session)
        self.run_repo = TestRunRepository(session)
        self.run_tc_repo = TestRunTestCaseRepository(session)
        self.project_repo = ProjectRepository(session)
        self.tc_repo = TestCaseRepository(session)
    
    async def _get_project_by_identifier(self, project_identifier: str):
        """根据标识符获取项目"""
        project = await self.project_repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=project_identifier)
        return project
    
    async def _get_test_run(self, project_id: UUID, test_run_identifier: str):
        """获取测试运行"""
        test_run = await self.run_repo.get_by_identifier(test_run_identifier)
        if not test_run or test_run.project_id != project_id:
            raise NotFoundException(resource_type="测试运行", resource_id=test_run_identifier)
        return test_run
    
    def _status_to_display(self, status: TestResultStatus) -> str:
        """将状态枚举转换为显示文本 (BS 7 状态 + 历史 not_executed)"""
        status_map = {
            TestResultStatus.UNTESTED: "Untested",
            TestResultStatus.PASSED: "Passed",
            TestResultStatus.RETEST: "Retest",
            TestResultStatus.FAILED: "Failed",
            TestResultStatus.BLOCKED: "Blocked",
            TestResultStatus.SKIPPED: "Skipped",
            TestResultStatus.IN_PROGRESS: "In Progress",
            TestResultStatus.NOT_EXECUTED: "Not Executed",
        }
        return status_map.get(status, str(status.value).title())

    async def _to_info(self, result: TestResult, test_run_identifier: str) -> TestResultInfo:
        """将模型转换为响应信息"""
        tc = result.test_case

        # 转换步骤结果
        step_result = None
        if result.step_results:
            step_result = [
                StepResultInfo(
                    step=None,  # 需要从原始测试用例获取
                    result=sr.description,
                    result_status=ResultStatus(field_value=self._status_to_display(sr.status)),
                    created_by=None,
                    created_at=sr.created_at,
                    custom_fields=None,
                )
                for sr in result.step_results
            ]

        # 转换问题列表
        issues = None
        if result.issues:
            issues = [
                IssueInfo(
                    issue_id=issue,
                    issue_type=result.issue_tracker.get("name") if result.issue_tracker else None,
                    created_at=result.created_at,
                )
                for issue in result.issues
            ]

        # 转换自定义字段
        custom_fields = None
        if result.custom_fields:
            custom_fields = [
                CustomFieldValue(field_name=k, value=v)
                for k, v in result.custom_fields.items()
            ]

        return TestResultInfo(
            id=result.id,
            test_run_id=test_run_identifier,
            test_case_id=tc.identifier if tc else "",
            result_status=ResultStatus(field_value=self._status_to_display(result.status)),
            description=result.description,
            created_by=result.created_by,
            issues=issues,
            custom_fields=custom_fields,
            step_result=step_result,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )

    async def _to_list_info(self, result: TestResult, test_run_identifier: str) -> TestResultListInfo:
        """将模型转换为列表项信息"""
        tc = result.test_case
        return TestResultListInfo(
            id=result.id,
            test_run_id=test_run_identifier,
            test_case_id=tc.identifier if tc else "",
            result_status=ResultStatus(field_value=self._status_to_display(result.status)),
            description=result.description,
            created_by=result.created_by,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )
    
    async def get_list(
        self,
        project_identifier: str,
        test_run_identifier: str,
        status: Optional[TestResultStatus] = None,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestResultListInfo], int]:
        """获取测试结果列表"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._get_test_run(project.id, test_run_identifier)
        
        results, total = await self.repo.get_list(
            test_run_id=test_run.id,
            status=status,
            offset=offset,
            limit=limit,
        )

        items = [await self._to_list_info(r, test_run_identifier) for r in results]
        return items, total

    async def get_by_id(
        self,
        project_identifier: str,
        test_run_identifier: str,
        result_id: UUID,
    ) -> TestResultInfo:
        """获取测试结果详情"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._get_test_run(project.id, test_run_identifier)

        result = await self.repo.get_by_id(result_id)
        if not result or result.test_run_id != test_run.id:
            raise NotFoundException(resource_type="测试结果", resource_id=str(result_id))

        return await self._to_info(result, test_run_identifier)

    async def get_history(
        self,
        project_identifier: str,
        test_run_identifier: str,
        test_case_identifier: str,
        configuration_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestResultHistoryInfo], int]:
        """获取测试用例在测试运行中的历史结果"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._get_test_run(project.id, test_run_identifier)

        test_case = await self.tc_repo.get_by_identifier(test_case_identifier)
        if not test_case or test_case.project_id != project.id:
            raise NotFoundException(resource_type="测试用例", resource_id=test_case_identifier)
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1RoVlpnPT06NGEzZmJhMGE=

        results, total = await self.repo.get_history(
            test_run_id=test_run.id,
            test_case_id=test_case.id,
            configuration_id=configuration_id,
            offset=offset,
            limit=limit,
        )

        items = [
            TestResultHistoryInfo(
                id=r.id,
                result_status=ResultStatus(field_value=self._status_to_display(r.status)),
                description=r.description,
                created_by=r.created_by,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in results
        ]
        return items, total

    async def _add_single_result(
        self,
        project_id: UUID,
        test_run,
        test_run_identifier: str,
        item: TestResultItem,
    ) -> TestResultInfo:
        """添加单个测试结果（内部方法）"""
        # 获取测试用例
        test_case = await self.tc_repo.get_by_identifier(item.test_case_id)
        if not test_case or test_case.project_id != project_id:
            raise BadRequestException(f"测试用例 {item.test_case_id} 不存在")

        # 获取测试运行中的测试用例关联
        run_tc = await self.run_tc_repo.get_by_test_run_and_case(
            test_run.id, test_case.id, item.configuration_id
        )

        # 创建测试结果
        result = TestResult(
            test_run_id=test_run.id,
            test_case_id=test_case.id,
            test_run_test_case_id=run_tc.id if run_tc else None,
            configuration_id=item.configuration_id,
            status=item.test_result.status,
            description=item.test_result.description,
            issues=item.test_result.issues,
            issue_tracker=item.test_result.issue_tracker.model_dump() if item.test_result.issue_tracker else None,
            custom_fields=item.test_result.custom_fields,
        )
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1RoVlpnPT06NGEzZmJhMGE=

        # 添加步骤结果
        if item.test_result.step_results:
            for idx, sr in enumerate(item.test_result.step_results, 1):
                step_result = TestStepResult(
                    step_id=sr.step_id,
                    step_index=sr.step_index or idx,
                    status=sr.status,
                    description=sr.description,
                    issues=sr.issues,
                )
                result.step_results.append(step_result)

        result = await self.repo.create(result)

        # 更新 TestRunTestCase 的最新状态
        if run_tc:
            await self.run_tc_repo.update_status(run_tc.id, result.status, result.id)
            # 更新测试运行的统计
            await self.run_repo.update_counts(test_run.id)

        # 刷新以加载关系
        await self.session.refresh(result)
        result = await self.repo.get_by_id(result.id)

        return await self._to_info(result, test_run_identifier)

    async def add_result(
        self,
        project_identifier: str,
        test_run_identifier: str,
        data: TestResultCreate,
    ):
        """
        添加测试结果

        支持两种格式:
        1. 单个结果: {"test_result": {app..}, "test_case_id": "app.."}
        2. 批量结果: {"results": [app..]}
        """
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._get_test_run(project.id, test_run_identifier)

        # 判断是单个还是批量
        if data.results:
            # 批量添加
            return await self._add_bulk_results_internal(
                project.id, test_run, test_run_identifier, data.results
            )
        elif data.test_result and data.test_case_id:
            # 单个添加
            item = TestResultItem(
                test_result=data.test_result,
                test_case_id=data.test_case_id,
                configuration_id=data.configuration_id,
            )
            return await self._add_single_result(
                project.id, test_run, test_run_identifier, item
            )
        else:
            raise BadRequestException(
                "请求格式错误: 需要提供 test_result 和 test_case_id，或者 results 数组"
            )

    async def _add_bulk_results_internal(
        self,
        project_id: UUID,
        test_run,
        test_run_identifier: str,
        results: list[TestResultItem],
    ) -> dict:
        """批量添加测试结果（内部方法）"""
        success_count = 0
        errors = []

        for item in results:
            try:
                # 获取测试用例
                test_case = await self.tc_repo.get_by_identifier(item.test_case_id)
                if not test_case or test_case.project_id != project_id:
                    errors.append({"test_case_id": item.test_case_id, "error": "测试用例不存在"})
                    continue

                # 获取测试运行中的测试用例关联
                run_tc = await self.run_tc_repo.get_by_test_run_and_case(
                    test_run.id, test_case.id, item.configuration_id
                )

                # 创建测试结果
                result = TestResult(
                    test_run_id=test_run.id,
                    test_case_id=test_case.id,
                    test_run_test_case_id=run_tc.id if run_tc else None,
                    configuration_id=item.configuration_id,
                    status=item.test_result.status,
                    description=item.test_result.description,
                    issues=item.test_result.issues,
                    issue_tracker=item.test_result.issue_tracker.model_dump() if item.test_result.issue_tracker else None,
                    custom_fields=item.test_result.custom_fields,
                )

                # 添加步骤结果
                if item.test_result.step_results:
                    for idx, sr in enumerate(item.test_result.step_results, 1):
                        step_result = TestStepResult(
                            step_id=sr.step_id,
                            step_index=sr.step_index or idx,
                            status=sr.status,
                            description=sr.description,
                            issues=sr.issues,
                        )
                        result.step_results.append(step_result)

                await self.repo.create(result)

                # 更新 TestRunTestCase 的最新状态
                if run_tc:
                    await self.run_tc_repo.update_status(run_tc.id, result.status, result.id)

                success_count += 1
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1RoVlpnPT06NGEzZmJhMGE=

            except Exception as e:
                errors.append({"test_case_id": item.test_case_id, "error": str(e)})

        # 更新测试运行的统计
        await self.run_repo.update_counts(test_run.id)

        return {
            "success": True,
            "processed": len(results),
            "success_count": success_count,
            "error_count": len(errors),
            "errors": errors if errors else None,
        }

