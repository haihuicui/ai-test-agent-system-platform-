"""
API Agent 的场景测试工具

提供多接口业务流场景测试的创建、编排、执行功能
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import async_session_factory
from app.models.api_endpoint import APIEndpoint
from app.models.project import Project
from app.models.test_scenario import (
    TestScenario,
    ScenarioStep,
    StepDataMapping,
    ScenarioVariable,
)


@tool
async def create_test_scenario(
    project_identifier: str,
    name: str,
    description: str = "",
    folder_id: str | None = None,
) -> str:
    """
    创建一个新的测试场景

    测试场景用于编排多个 API 接口的业务流测试，例如：
    - 用户登录 → 创建订单 → 支付 → 查询订单状态
    - 注册用户 → 验证邮箱 → 完善资料 → 上传头像

    Args:
        project_identifier: 项目标识符（如 "PR-1234"）
        name: 场景名称（如 "用户下单完整流程"）
        description: 场景描述
        folder_id: 所属文件夹 ID（可选）

    Returns:
        JSON 格式的创建结果，包含场景 ID 和标识符

    Example:
        >>> result = await create_test_scenario(
        ...     project_identifier="PR-1234",
        ...     name="用户下单完整流程",
        ...     description="测试从登录到支付的完整业务流"
        ... )
    """
    async with async_session_factory() as session:
        try:
            # 1. 查询项目
            project_stmt = select(Project).where(
                Project.identifier == project_identifier
            )
            project_result = await session.execute(project_stmt)
            project = project_result.scalar_one_or_none()

            if not project:
                return json.dumps({
                    "success": False,
                    "error": f"项目 {project_identifier} 不存在"
                }, ensure_ascii=False, indent=2)

            # 2. 生成场景标识符
            # 查询当前项目的场景数量
            count_stmt = select(TestScenario).where(
                TestScenario.project_id == project.id
            )
            count_result = await session.execute(count_stmt)
            scenario_count = len(count_result.scalars().all())
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDJWMVlRPT06MTVjYjUwZTk=
            
            identifier = f"TS-{scenario_count + 1:04d}"

            # 3. 创建场景
            scenario = TestScenario(
                id=uuid4(),
                project_id=project.id,
                folder_id=UUID(folder_id) if folder_id else None,
                identifier=identifier,
                name=name,
                description=description,
                status="draft",
                created_by=project.created_by,
            )
            session.add(scenario)
            await session.commit()
            await session.refresh(scenario)

            return json.dumps({
                "success": True,
                "message": f"成功创建测试场景 {identifier}",
                "data": {
                    "scenario_id": str(scenario.id),
                    "identifier": scenario.identifier,
                    "name": scenario.name,
                    "status": scenario.status,
                    "total_steps": 0,
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            await session.rollback()
            return json.dumps({
                "success": False,
                "error": f"创建场景失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def update_test_scenario(
    scenario_id: str,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    global_variables: dict | None = None,
) -> str:
    """
    更新测试场景的基本信息

    可以修改场景的名称、描述、状态和全局变量。

    Args:
        scenario_id: 场景 ID
        name: 新的场景名称（可选）
        description: 新的场景描述（可选）
        status: 新的场景状态（可选，draft/active/archived）
        global_variables: 全局变量字典（可选）

    Returns:
        JSON 格式的更新结果

    Example:
        >>> result = await update_test_scenario(
        ...     scenario_id="uuid-xxx",
        ...     name="更新后的场景名称",
        ...     description="更新后的描述",
        ...     status="active"
        ... )
    """
    async with async_session_factory() as session:
        try:
            # 1. 查询场景
            scenario_stmt = select(TestScenario).where(
                TestScenario.id == UUID(scenario_id)
            )
            scenario_result = await session.execute(scenario_stmt)
            scenario = scenario_result.scalar_one_or_none()

            if not scenario:
                return json.dumps({
                    "success": False,
                    "error": f"场景 {scenario_id} 不存在"
                }, ensure_ascii=False, indent=2)

            # 2. 更新字段
            updated_fields = []
            if name is not None:
                scenario.name = name
                updated_fields.append("name")

            if description is not None:
                scenario.description = description
                updated_fields.append("description")

            if status is not None:
                # 验证状态值
                valid_statuses = ["draft", "active", "archived"]
                if status not in valid_statuses:
                    return json.dumps({
                        "success": False,
                        "error": f"无效的状态值。可选值: {', '.join(valid_statuses)}"
                    }, ensure_ascii=False, indent=2)
                scenario.status = status
                updated_fields.append("status")
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDJWMVlRPT06MTVjYjUwZTk=

            if global_variables is not None:
                scenario.global_variables = global_variables
                updated_fields.append("global_variables")

            scenario.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(scenario)

            return json.dumps({
                "success": True,
                "message": f"成功更新场景 {scenario.identifier}",
                "data": {
                    "scenario_id": str(scenario.id),
                    "identifier": scenario.identifier,
                    "name": scenario.name,
                    "description": scenario.description,
                    "status": scenario.status,
                    "total_steps": scenario.total_steps,
                    "global_variables": scenario.global_variables,
                    "updated_fields": updated_fields,
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            await session.rollback()
            return json.dumps({
                "success": False,
                "error": f"更新场景失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def add_scenario_step(
    scenario_id: str,
    endpoint_id: str,
    name: str,
    description: str = "",
    step_order: int | None = None,
    request_override: dict | None = None,
    headers_override: dict | None = None,
) -> str:
    """
    向测试场景添加一个步骤

    每个步骤代表一个 API 接口调用，可以配置请求参数、请求头等。

    Args:
        scenario_id: 场景 ID
        endpoint_id: API 端点 ID
        name: 步骤名称（如 "用户登录"）
        description: 步骤描述
        step_order: 步骤顺序（可选，默认追加到最后）
        request_override: 请求参数覆盖（可选）
        headers_override: 请求头覆盖（可选）

    Returns:
        JSON 格式的添加结果

    Example:
        >>> result = await add_scenario_step(
        ...     scenario_id="uuid-xxx",
        ...     endpoint_id="uuid-yyy",
        ...     name="用户登录",
        ...     request_override={"body": {"username": "{{username}}", "password": "{{password}}"}}
        ... )
    """
    async with async_session_factory() as session:
        try:
            # 1. 查询场景
            scenario_stmt = select(TestScenario).where(
                TestScenario.id == UUID(scenario_id)
            )
            scenario_result = await session.execute(scenario_stmt)
            scenario = scenario_result.scalar_one_or_none()

            if not scenario:
                return json.dumps({
                    "success": False,
                    "error": f"场景 {scenario_id} 不存在"
                }, ensure_ascii=False, indent=2)

            # 2. 查询端点
            endpoint_stmt = select(APIEndpoint).where(
                APIEndpoint.id == UUID(endpoint_id)
            )
            endpoint_result = await session.execute(endpoint_stmt)
            endpoint = endpoint_result.scalar_one_or_none()

            if not endpoint:
                return json.dumps({
                    "success": False,
                    "error": f"端点 {endpoint_id} 不存在"
                }, ensure_ascii=False, indent=2)

            # 3. 确定步骤顺序
            if step_order is None:
                # 查询当前最大步骤顺序
                steps_stmt = select(ScenarioStep).where(
                    ScenarioStep.scenario_id == UUID(scenario_id)
                )
                steps_result = await session.execute(steps_stmt)
                existing_steps = steps_result.scalars().all()
                step_order = len(existing_steps) + 1

            # 4. 创建步骤
            step = ScenarioStep(
                id=uuid4(),
                scenario_id=UUID(scenario_id),
                endpoint_id=UUID(endpoint_id),
                step_order=step_order,
                name=name,
                description=description,
                request_override=request_override or {},
                headers_override=headers_override or {},
            )
            session.add(step)

            # 5. 更新场景的步骤总数
            scenario.total_steps = len(existing_steps) + 1
            scenario.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(step)

            return json.dumps({
                "success": True,
                "message": f"成功添加步骤 {step_order}: {name}",
                "data": {
                    "step_id": str(step.id),
                    "step_order": step.step_order,
                    "name": step.name,
                    "endpoint": {
                        "id": str(endpoint.id),
                        "method": endpoint.method,
                        "path": endpoint.path,
                        "display_name": endpoint.display_name,
                    }
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            await session.rollback()
            return json.dumps({
                "success": False,
                "error": f"添加步骤失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def update_scenario_step(
    step_id: str,
    name: str | None = None,
    description: str | None = None,
    request_override: dict | None = None,
    headers_override: dict | None = None,
    continue_on_failure: bool | None = None,
    delay_ms: int | None = None,
) -> str:
    """
    更新测试场景步骤的配置

    可以修改步骤的名称、描述、请求参数、请求头等配置。

    Args:
        step_id: 步骤 ID
        name: 新的步骤名称（可选）
        description: 新的步骤描述（可选）
        request_override: 新的请求参数覆盖（可选）
        headers_override: 新的请求头覆盖（可选）
        continue_on_failure: 失败后是否继续执行（可选）
        delay_ms: 执行延迟（毫秒，可选）

    Returns:
        JSON 格式的更新结果

    Example:
        >>> result = await update_scenario_step(
        ...     step_id="uuid-xxx",
        ...     name="更新后的步骤名称",
        ...     request_override={"body": {"new_param": "value"}},
        ...     continue_on_failure=True
        ... )
    """
    async with async_session_factory() as session:
        try:
            # 1. 查询步骤
            step_stmt = select(ScenarioStep).where(
                ScenarioStep.id == UUID(step_id)
            )
            step_result = await session.execute(step_stmt)
            step = step_result.scalar_one_or_none()

            if not step:
                return json.dumps({
                    "success": False,
                    "error": f"步骤 {step_id} 不存在"
                }, ensure_ascii=False, indent=2)
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDJWMVlRPT06MTVjYjUwZTk=

            # 2. 更新字段
            updated_fields = []

            if name is not None:
                step.name = name
                updated_fields.append("name")

            if description is not None:
                step.description = description
                updated_fields.append("description")

            if request_override is not None:
                step.request_override = request_override
                updated_fields.append("request_override")

            if headers_override is not None:
                step.headers_override = headers_override
                updated_fields.append("headers_override")

            if continue_on_failure is not None:
                step.continue_on_failure = continue_on_failure
                updated_fields.append("continue_on_failure")

            if delay_ms is not None:
                step.delay_ms = delay_ms
                updated_fields.append("delay_ms")

            step.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(step)

            # 查询关联的端点信息
            endpoint = None
            if step.endpoint_id:
                endpoint_stmt = select(APIEndpoint).where(
                    APIEndpoint.id == step.endpoint_id
                )
                endpoint_result = await session.execute(endpoint_stmt)
                endpoint = endpoint_result.scalar_one_or_none()

            return json.dumps({
                "success": True,
                "message": f"成功更新步骤 {step.name}",
                "data": {
                    "step_id": str(step.id),
                    "step_order": step.step_order,
                    "name": step.name,
                    "description": step.description,
                    "endpoint": {
                        "id": str(endpoint.id),
                        "method": endpoint.method,
                        "path": endpoint.path,
                        "display_name": endpoint.display_name,
                    } if endpoint else None,
                    "continue_on_failure": step.continue_on_failure,
                    "delay_ms": step.delay_ms,
                    "updated_fields": updated_fields,
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            await session.rollback()
            return json.dumps({
                "success": False,
                "error": f"更新步骤失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def add_data_mapping(
    step_id: str,
    source_type: str,
    target_path: str,
    source_step_id: str | None = None,
    source_path: str | None = None,
    transform_expression: str | None = None,
    description: str = "",
) -> str:
    """
    为步骤添加数据映射（数据依赖）

    数据映射用于将前一个步骤的响应数据传递给后续步骤，例如：
    - 将登录接口返回的 token 传递给后续接口的 Authorization 头
    - 将创建订单返回的 orderId 传递给支付接口

    Args:
        step_id: 目标步骤 ID
        source_type: 数据源类型，可选值：
            - "previous_response": 前一个步骤的响应数据
            - "variable": 场景变量
            - "static": 静态值
        target_path: 目标路径（如 "headers.Authorization" 或 "body.orderId"）
        source_step_id: 源步骤 ID（当 source_type 为 previous_response 时必填）
        source_path: 源数据路径（JSONPath 格式，如 "$.data.token"）
        transform_expression: 转换表达式（可选，如 "'Bearer ' + value"）
        description: 映射描述

    Returns:
        JSON 格式的添加结果

    Example:
        >>> # 将登录接口的 token 传递给后续接口
        >>> result = await add_data_mapping(
        ...     step_id="step-2-uuid",
        ...     source_type="previous_response",
        ...     source_step_id="step-1-uuid",
        ...     source_path="$.data.token",
        ...     target_path="headers.Authorization",
        ...     transform_expression="'Bearer ' + value"
        ... )
    """
    async with async_session_factory() as session:
        try:
            # 1. 查询步骤
            step_stmt = select(ScenarioStep).where(
                ScenarioStep.id == UUID(step_id)
            )
            step_result = await session.execute(step_stmt)
            step = step_result.scalar_one_or_none()

            if not step:
                return json.dumps({
                    "success": False,
                    "error": f"步骤 {step_id} 不存在"
                }, ensure_ascii=False, indent=2)

            # 2. 验证源步骤（如果是 previous_response 类型）
            if source_type == "previous_response":
                if not source_step_id:
                    return json.dumps({
                        "success": False,
                        "error": "source_type 为 previous_response 时，必须提供 source_step_id"
                    }, ensure_ascii=False, indent=2)

                source_step_stmt = select(ScenarioStep).where(
                    ScenarioStep.id == UUID(source_step_id)
                )
                source_step_result = await session.execute(source_step_stmt)
                source_step = source_step_result.scalar_one_or_none()

                if not source_step:
                    return json.dumps({
                        "success": False,
                        "error": f"源步骤 {source_step_id} 不存在"
                    }, ensure_ascii=False, indent=2)

            # 3. 创建数据映射
            mapping = StepDataMapping(
                id=uuid4(),
                step_id=UUID(step_id),
                source_type=source_type,
                source_step_id=UUID(source_step_id) if source_step_id else None,
                source_path=source_path,
                target_path=target_path,
                transform_expression=transform_expression,
                description=description,
            )
            session.add(mapping)
            await session.commit()
            await session.refresh(mapping)
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDJWMVlRPT06MTVjYjUwZTk=

            return json.dumps({
                "success": True,
                "message": f"成功添加数据映射: {source_path} → {target_path}",
                "data": {
                    "mapping_id": str(mapping.id),
                    "source_type": mapping.source_type,
                    "source_path": mapping.source_path,
                    "target_path": mapping.target_path,
                    "transform": mapping.transform_expression,
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            await session.rollback()
            return json.dumps({
                "success": False,
                "error": f"添加数据映射失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def add_step_extractor(
    step_id: str,
    name: str,
    path: str,
    extractor_type: str = "jsonpath",
) -> str:
    """
    为步骤添加数据提取器

    数据提取器用于从 API 响应中提取数据，保存到变量中供后续步骤使用。

    Args:
        step_id: 步骤 ID
        name: 提取的变量名（如 "token", "orderId"）
        path: 提取路径（JSONPath 格式，如 "$.data.token"）
        extractor_type: 提取器类型（默认 "jsonpath"）

    Returns:
        JSON 格式的添加结果

    Example:
        >>> # 从登录响应中提取 token
        >>> result = await add_step_extractor(
        ...     step_id="step-1-uuid",
        ...     name="token",
        ...     path="$.data.token"
        ... )
    """
    async with async_session_factory() as session:
        try:
            # 1. 查询步骤
            step_stmt = select(ScenarioStep).where(
                ScenarioStep.id == UUID(step_id)
            )
            step_result = await session.execute(step_stmt)
            step = step_result.scalar_one_or_none()

            if not step:
                return json.dumps({
                    "success": False,
                    "error": f"步骤 {step_id} 不存在"
                }, ensure_ascii=False, indent=2)

            # 2. 添加提取器到步骤的 extractors 列表
            extractor = {
                "name": name,
                "path": path,
                "type": extractor_type,
            }

            extractors = step.extractors or []
            extractors.append(extractor)
            step.extractors = extractors
            step.updated_at = datetime.now(timezone.utc)

            await session.commit()

            return json.dumps({
                "success": True,
                "message": f"成功添加数据提取器: {name} = {path}",
                "data": {
                    "extractor": extractor,
                    "total_extractors": len(extractors),
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            await session.rollback()
            return json.dumps({
                "success": False,
                "error": f"添加提取器失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def add_step_assertion(
    step_id: str,
    assertion_type: str,
    expected: Any,
    path: str | None = None,
    operator: str = "eq",
) -> str:
    """
    为步骤添加断言

    断言用于验证 API 响应是否符合预期。

    Args:
        step_id: 步骤 ID
        assertion_type: 断言类型，可选值：
            - "status": 验证 HTTP 状态码
            - "jsonpath": 验证 JSON 路径的值
            - "header": 验证响应头
        expected: 期望值
        path: 数据路径（当 assertion_type 为 jsonpath 或 header 时必填）
        operator: 比较运算符（eq, ne, gt, lt, contains 等）

    Returns:
        JSON 格式的添加结果

    Example:
        >>> # 验证状态码为 200
        >>> result = await add_step_assertion(
        ...     step_id="step-1-uuid",
        ...     assertion_type="status",
        ...     expected=200
        ... )
        >>> # 验证响应中的 success 字段为 true
        >>> result = await add_step_assertion(
        ...     step_id="step-1-uuid",
        ...     assertion_type="jsonpath",
        ...     path="$.success",
        ...     expected=True
        ... )
    """
    async with async_session_factory() as session:
        try:
            # 1. 查询步骤
            step_stmt = select(ScenarioStep).where(
                ScenarioStep.id == UUID(step_id)
            )
            step_result = await session.execute(step_stmt)
            step = step_result.scalar_one_or_none()

            if not step:
                return json.dumps({
                    "success": False,
                    "error": f"步骤 {step_id} 不存在"
                }, ensure_ascii=False, indent=2)

            # 2. 添加断言到步骤的 assertions 列表
            assertion = {
                "type": assertion_type,
                "expected": expected,
                "operator": operator,
            }

            if path:
                assertion["path"] = path

            assertions = step.assertions or []
            assertions.append(assertion)
            step.assertions = assertions
            step.updated_at = datetime.now(timezone.utc)

            await session.commit()

            return json.dumps({
                "success": True,
                "message": f"成功添加断言: {assertion_type}",
                "data": {
                    "assertion": assertion,
                    "total_assertions": len(assertions),
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            await session.rollback()
            return json.dumps({
                "success": False,
                "error": f"添加断言失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def get_scenario_details(scenario_id: str) -> str:
    """
    获取测试场景的详细信息

    包括场景的所有步骤、数据映射、变量等完整信息。

    Args:
        scenario_id: 场景 ID

    Returns:
        JSON 格式的场景详情

    Example:
        >>> result = await get_scenario_details("uuid-xxx")
    """
    async with async_session_factory() as session:
        try:
            # 1. 查询场景（包含关联数据）
            scenario_stmt = select(TestScenario).where(
                TestScenario.id == UUID(scenario_id)
            )
            scenario_result = await session.execute(scenario_stmt)
            scenario = scenario_result.scalar_one_or_none()

            if not scenario:
                return json.dumps({
                    "success": False,
                    "error": f"场景 {scenario_id} 不存在"
                }, ensure_ascii=False, indent=2)

            # 2. 查询所有步骤
            steps_stmt = select(ScenarioStep).where(
                ScenarioStep.scenario_id == UUID(scenario_id)
            ).order_by(ScenarioStep.step_order)
            steps_result = await session.execute(steps_stmt)
            steps = steps_result.scalars().all()

            # 3. 构建步骤详情
            steps_data = []
            for step in steps:
                # 查询端点信息
                endpoint = None
                if step.endpoint_id:
                    endpoint_stmt = select(APIEndpoint).where(
                        APIEndpoint.id == step.endpoint_id
                    )
                    endpoint_result = await session.execute(endpoint_stmt)
                    endpoint = endpoint_result.scalar_one_or_none()

                # 查询数据映射
                mappings_stmt = select(StepDataMapping).where(
                    StepDataMapping.step_id == step.id
                )
                mappings_result = await session.execute(mappings_stmt)
                mappings = mappings_result.scalars().all()

                steps_data.append({
                    "step_id": str(step.id),
                    "step_order": step.step_order,
                    "name": step.name,
                    "description": step.description,
                    "endpoint": {
                        "id": str(endpoint.id),
                        "method": endpoint.method,
                        "path": endpoint.path,
                        "display_name": endpoint.display_name,
                    } if endpoint else None,
                    "extractors": step.extractors,
                    "assertions": step.assertions,
                    "data_mappings": [
                        {
                            "mapping_id": str(m.id),
                            "source_type": m.source_type,
                            "source_path": m.source_path,
                            "target_path": m.target_path,
                            "transform": m.transform_expression,
                        }
                        for m in mappings
                    ],
                })

            return json.dumps({
                "success": True,
                "data": {
                    "scenario_id": str(scenario.id),
                    "identifier": scenario.identifier,
                    "name": scenario.name,
                    "description": scenario.description,
                    "status": scenario.status,
                    "total_steps": scenario.total_steps,
                    "steps": steps_data,
                    "global_variables": scenario.global_variables,
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"获取场景详情失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def list_test_scenarios(
    project_identifier: str,
    status: str | None = None,
) -> str:
    """
    列出项目的所有测试场景

    Args:
        project_identifier: 项目标识符
        status: 场景状态筛选（可选，draft/active/archived）

    Returns:
        JSON 格式的场景列表

    Example:
        >>> result = await list_test_scenarios("PR-1234")
    """
    async with async_session_factory() as session:
        try:
            # 1. 查询项目
            project_stmt = select(Project).where(
                Project.identifier == project_identifier
            )
            project_result = await session.execute(project_stmt)
            project = project_result.scalar_one_or_none()

            if not project:
                return json.dumps({
                    "success": False,
                    "error": f"项目 {project_identifier} 不存在"
                }, ensure_ascii=False, indent=2)

            # 2. 查询场景
            scenarios_stmt = select(TestScenario).where(
                TestScenario.project_id == project.id
            )

            if status:
                scenarios_stmt = scenarios_stmt.where(
                    TestScenario.status == status
                )

            scenarios_result = await session.execute(scenarios_stmt)
            scenarios = scenarios_result.scalars().all()

            # 3. 构建场景列表
            scenarios_data = [
                {
                    "scenario_id": str(s.id),
                    "identifier": s.identifier,
                    "name": s.name,
                    "description": s.description,
                    "status": s.status,
                    "total_steps": s.total_steps,
                    "last_run_status": s.last_run_status,
                    "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
                    "created_at": s.created_at.isoformat(),
                }
                for s in scenarios
            ]

            return json.dumps({
                "success": True,
                "message": f"找到 {len(scenarios_data)} 个测试场景",
                "data": {
                    "total": len(scenarios_data),
                    "scenarios": scenarios_data,
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"查询场景列表失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def execute_scenario(
    scenario_id: str,
    variables: dict | None = None,
    base_url: str = "",
    debug: bool = False,
) -> str:
    """
    执行测试场景

    按照场景定义的步骤顺序执行所有 API 调用，处理数据依赖，验证断言。

    Args:
        scenario_id: 场景 ID
        variables: 运行时变量（可选，如 {"username": "test", "password": "123456"}）
        base_url: API 基础 URL（可选，如 "https://api.example.com"）
        debug: 是否启用调试模式（可选，启用后会返回详细的请求/响应信息）

    Returns:
        JSON 格式的执行结果，包含每个步骤的详细执行信息

    Example:
        >>> result = await execute_scenario(
        ...     scenario_id="uuid-xxx",
        ...     variables={"username": "testuser", "password": "pass123"},
        ...     base_url="https://api.example.com",
        ...     debug=True
        ... )
    """
    from app.services.scenario_execution_engine import ScenarioExecutionEngine

    async with async_session_factory() as session:
        try:
            # 创建执行引擎
            engine = ScenarioExecutionEngine(session)

            # 执行场景
            run = await engine.execute(
                scenario_id=UUID(scenario_id),
                variables=variables or {},
                base_url=base_url,
            )

            # 查询步骤结果
            from app.models.test_scenario import ScenarioStepResult
            results_stmt = select(ScenarioStepResult).where(
                ScenarioStepResult.run_id == run.id
            ).order_by(ScenarioStepResult.step_order)
            results_result = await session.execute(results_stmt)
            step_results = results_result.scalars().all()

            # 构建详细的步骤结果
            detailed_results = []
            for r in step_results:
                step_info = {
                    "step_order": r.step_order,
                    "status": r.status,
                    "duration_ms": r.duration_ms,
                    "extracted_data": r.extracted_data,
                    "assertion_results": r.assertion_results,
                    "error_message": r.error_message,
                }

                # 如果启用调试模式，添加请求和响应的详细信息
                if debug:
                    step_info["request_data"] = r.request_data
                    step_info["response_data"] = {
                        "status": r.response_data.get("status") if r.response_data else None,
                        "body": r.response_data.get("body") if r.response_data else None,
                        "headers": r.response_data.get("headers") if r.response_data else None,
                    }

                detailed_results.append(step_info)

            # 如果启用调试模式，添加上下文变量信息
            debug_info = {}
            if debug:
                debug_info = {
                    "input_variables": variables or {},
                    "runtime_variables": run.runtime_variables,
                    "global_variables": {},  # 可以从场景获取
                }

            # 构建结果
            return json.dumps({
                "success": True,
                "message": f"场景执行{'成功' if run.status == 'completed' else '失败'}",
                "data": {
                    "run_id": str(run.id),
                    "identifier": run.identifier,
                    "status": run.status,
                    "total_steps": run.total_steps,
                    "passed_steps": run.passed_steps,
                    "failed_steps": run.failed_steps,
                    "duration_ms": run.duration_ms,
                    "error_message": run.error_message,
                    "debug_info": debug_info if debug else None,
                    "step_results": detailed_results,
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            import traceback
            return json.dumps({
                "success": False,
                "error": f"执行场景失败: {str(e)}",
                "stack_trace": traceback.format_exc() if debug else None,
            }, ensure_ascii=False, indent=2)


@tool
async def debug_scenario_dependencies(
    scenario_id: str,
) -> str:
    """
    调试场景的数据依赖配置

    分析场景中所有步骤的数据映射配置，检查数据依赖链是否完整。

    Args:
        scenario_id: 场景 ID

    Returns:
        JSON 格式的依赖分析结果

    Example:
        >>> result = await debug_scenario_dependencies("uuid-xxx")
    """
    async with async_session_factory() as session:
        try:
            # 1. 查询场景和步骤
            scenario_stmt = select(TestScenario).where(
                TestScenario.id == UUID(scenario_id)
            )
            scenario_result = await session.execute(scenario_stmt)
            scenario = scenario_result.scalar_one_or_none()

            if not scenario:
                return json.dumps({
                    "success": False,
                    "error": f"场景 {scenario_id} 不存在"
                }, ensure_ascii=False, indent=2)

            # 2. 查询所有步骤和数据映射
            steps_stmt = select(ScenarioStep).where(
                ScenarioStep.scenario_id == scenario_id
            ).order_by(ScenarioStep.step_order)
            steps_result = await session.execute(steps_stmt)
            steps = steps_result.scalars().all()

            # 3. 分析每个步骤的数据依赖
            steps_analysis = []
            for step in steps:
                # 查询数据映射
                mappings_stmt = select(StepDataMapping).where(
                    StepDataMapping.step_id == step.id
                )
                mappings_result = await session.execute(mappings_stmt)
                mappings = mappings_result.scalars().all()

                step_info = {
                    "step_order": step.step_order,
                    "step_id": str(step.id),
                    "step_name": step.name,
                    "endpoint_id": str(step.endpoint_id) if step.endpoint_id else None,
                    "data_mappings": [],
                    "extractors": step.extractors or [],
                    "assertions": step.assertions or [],
                }

                # 分析每个数据映射
                for mapping in mappings:
                    mapping_info = {
                        "source_type": mapping.source_type,
                        "source_step_id": str(mapping.source_step_id) if mapping.source_step_id else None,
                        "source_path": mapping.source_path,
                        "target_path": mapping.target_path,
                        "transform_expression": mapping.transform_expression,
                    }

                    # 验证数据源是否存在
                    if mapping.source_type == "previous_response":
                        if mapping.source_step_id:
                            # 检查源步骤是否存在
                            source_step = await session.execute(
                                select(ScenarioStep).where(
                                    ScenarioStep.id == mapping.source_step_id,
                                    ScenarioStep.scenario_id == scenario_id
                                )
                            )
                            if source_step.scalar_one_or_none():
                                mapping_info["source_step_exists"] = True
                                mapping_info["source_step_order"] = source_step.scalar_one_or_none().step_order
                            else:
                                mapping_info["source_step_exists"] = False
                                mapping_info["warning"] = "源步骤不存在"
                        else:
                            mapping_info["warning"] = "未指定源步骤 ID"
                    elif mapping.source_type == "variable":
                        # 检查变量是否定义
                        if mapping.source_path in scenario.global_variables:
                            mapping_info["variable_defined"] = True
                            mapping_info["variable_value"] = scenario.global_variables[mapping.source_path]
                        else:
                            mapping_info["variable_defined"] = False
                            mapping_info["warning"] = f"变量 '{mapping.source_path}' 未在全局变量中定义"

                    step_info["data_mappings"].append(mapping_info)

                steps_analysis.append(step_info)

            # 4. 生成依赖链图
            dependency_chain = []
            for step_info in steps_analysis:
                for mapping in step_info["data_mappings"]:
                    if mapping.get("source_step_order") is not None:
                        dependency_chain.append({
                            "from_step": mapping["source_step_order"],
                            "to_step": step_info["step_order"],
                            "data_path": f"{mapping['source_path']} → {mapping['target_path']}",
                        })

            return json.dumps({
                "success": True,
                "data": {
                    "scenario_id": str(scenario.id),
                    "scenario_name": scenario.name,
                    "total_steps": len(steps_analysis),
                    "steps": steps_analysis,
                    "dependency_chain": dependency_chain,
                    "global_variables": scenario.global_variables,
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            import traceback
            return json.dumps({
                "success": False,
                "error": f"调试场景依赖失败: {str(e)}",
                "stack_trace": traceback.format_exc(),
            }, ensure_ascii=False, indent=2)

