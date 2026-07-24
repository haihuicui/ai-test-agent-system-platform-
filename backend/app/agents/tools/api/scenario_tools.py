"""
API Agent 的场景测试工具

提供多接口业务流场景测试的创建、编排、执行功能
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.api.runtime_context import get_conversation_id
from app.agents.tools.api.scenario_design_validator import _validate_scenario_design
from app.config.database import async_session_factory
from app.models.api_endpoint import APIEndpoint
from app.models.project import Project
from app.models.test_scenario import (
    TestScenario,
    ScenarioStep,
    StepDataMapping,
    ScenarioVariable,
)
from app.utils.assertion_operators import normalize_operator


# 同一次 AI 对话（conversation）内创建场景的去重缓存。
# key: (conversation_id, project_id), value: (scenario_id, created_at)
# 用于在同一次对话中重新生成时，覆盖/替换旧场景。
SCENARIO_CONVERSATION_CACHE_TTL_MINUTES = 60
_scenario_conversation_cache: dict[tuple[str | None, UUID], tuple[UUID, datetime]] = {}


def _cache_key(conversation_id: str | None, project_id: UUID) -> tuple[str | None, UUID]:
    return (conversation_id, project_id)


def _get_conversation_scenario_id(
    conversation_id: str | None,
    project_id: UUID,
) -> UUID | None:
    """
    获取指定 conversation + project 最近创建的场景 ID。

    如果缓存中的场景已超过 TTL，则清理并返回 None。
    """
    key = _cache_key(conversation_id, project_id)
    entry = _scenario_conversation_cache.get(key)
    if not entry:
        return None
    scenario_id, created_at = entry
    if datetime.now(timezone.utc) - created_at > timedelta(
        minutes=SCENARIO_CONVERSATION_CACHE_TTL_MINUTES
    ):
        _scenario_conversation_cache.pop(key, None)
        return None
    return scenario_id


def _set_conversation_scenario_id(
    conversation_id: str | None,
    project_id: UUID,
    scenario_id: UUID,
) -> None:
    """记录指定 conversation + project 已创建的场景 ID。"""
    key = _cache_key(conversation_id, project_id)
    _scenario_conversation_cache[key] = (scenario_id, datetime.now(timezone.utc))


def _clear_conversation_scenario_id(conversation_id: str | None, project_id: UUID) -> None:
    """清除指定 conversation + project 的缓存记录。"""
    _scenario_conversation_cache.pop(_cache_key(conversation_id, project_id), None)


def _build_scenario_warnings(steps_data: list[dict]) -> list[dict]:
    """分析场景步骤配置，生成诊断警告列表。

    检测以下问题：
    - 步骤未配置任何断言
    - 步骤只有 status 断言，缺少 jsonpath/header 业务断言
    - 所有步骤 step_order 相同（可能的排序 bug）
    """
    warnings: list[dict] = []
    step_orders: set[int] = set()

    for step in steps_data:
        step_orders.add(step.get("step_order", 0))
        assertions = step.get("assertions") or []

        if not assertions:
            warnings.append({
                "step_order": step["step_order"],
                "step_name": step["name"],
                "severity": "error",
                "issue": "未配置任何断言",
                "fix": "使用 add_step_assertion 为步骤添加 status + jsonpath 断言",
            })
            continue

        has_non_status = any(
            a.get("type") in ("jsonpath", "header") for a in assertions
        )
        if not has_non_status:
            warnings.append({
                "step_order": step["step_order"],
                "step_name": step["name"],
                "severity": "warning",
                "issue": "只有 status 断言，缺少 jsonpath/header 业务断言",
                "fix": "使用 add_step_assertion 添加 jsonpath 断言（如 $.code = \"2000\"）",
            })

    # 检测所有步骤 step_order 相同的异常情况
    if len(steps_data) >= 2 and len(step_orders) == 1:
        warnings.append({
            "step_order": "all",
            "step_name": "全部步骤",
            "severity": "critical",
            "issue": f"所有 {len(steps_data)} 个步骤的 step_order 都为 {list(step_orders)[0]}，"
                     f"场景将按数据库插入顺序而非业务顺序执行",
            "fix": "使用 update_scenario_step 逐个修正 step_order 为 1, 2, 3...",
        })

    return warnings


def _generate_default_value_for_field(field_name: str, schema: dict) -> Any:
    """根据字段名和 schema 为必填字段生成合理的默认值或动态占位符"""
    field_type = (schema.get("type") or "string").lower()
    lower_name = field_name.lower()

    if field_type == "string":
        if "email" in lower_name:
            return "{{$faker.email}}"
        if "phone" in lower_name or "mobile" in lower_name or "tel" in lower_name:
            return "{{$faker.phone_number}}"
        if "address" in lower_name:
            return "{{$faker.address}}"
        if any(k in lower_name for k in ("name", "title", "subject")):
            return "{{$faker.name}}"
        return "{{$randomString(8)}}"
    elif field_type in ("integer", "number"):
        if any(k in lower_name for k in ("count", "quantity", "size", "page", "limit", "age", "num")):
            return 1
        return 0
    elif field_type == "boolean":
        return True
    elif field_type == "array":
        return []
    elif field_type == "object":
        return {}
    else:
        return "{{$randomString(8)}}"


def _fill_required_body_defaults(
    endpoint: APIEndpoint,
    request_override: dict | None,
) -> tuple[dict, list[str]]:
    """
    如果 request_override.body 为空，按 endpoint request_body schema 自动填充必填字段默认值。

    Returns:
        (新的 request_override, 被填充的字段名列表)
    """
    result: dict = dict(request_override or {})
    body = result.get("body")
    if body is not None:
        return result, []

    try:
        endpoint_body = endpoint.request_body or {}
        content = endpoint_body.get("content", {})
        json_schema = content.get("application/json", {}).get("schema", {})
        required = json_schema.get("required", []) or []
        properties = json_schema.get("properties", {}) or {}
        if not required:
            return result, []

        filled_fields: list[str] = []
        filled_body: dict = {}
        for field in required:
            field_schema = properties.get(field, {}) if isinstance(properties, dict) else {}
            filled_body[field] = _generate_default_value_for_field(field, field_schema)
            filled_fields.append(field)

        result["body"] = filled_body
        return result, filled_fields
    except Exception:
        return result, []


def _deep_equal(a: Any, b: Any) -> bool:
    """深度比较两个 Python 对象（支持 dict/list/基本类型）。"""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_deep_equal(a[k], b[k]) for k in a.keys())
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(_deep_equal(x, y) for x, y in zip(a, b))
    return a == b


def _get_current_conversation_id(config: RunnableConfig | None) -> str | None:
    """
    获取当前 AI 会话 ID。

    优先从 LangGraph 运行配置读取（工具调用上下文内最可靠），
    读取不到时回退到 contextvar。
    """
    if config and isinstance(config.get("configurable"), dict):
        conversation_id = config["configurable"].get("conversation_id")
        if conversation_id:
            return conversation_id
    return get_conversation_id()


async def _replace_conversation_scenario(
    session: AsyncSession,
    conversation_id: str | None,
    project_id: UUID,
) -> dict | None:
    """
    删除当前 conversation + project 下已创建的场景，以便重新生成。

    通过级联删除清理关联的步骤、变量、执行记录等。

    Returns:
        被删除的场景信息（identifier, name），若无需删除则返回 None。
    """
    if not conversation_id:
        return None

    existing_id = _get_conversation_scenario_id(conversation_id, project_id)
    if not existing_id:
        return None

    scenario = await session.get(TestScenario, existing_id)
    if scenario:
        replaced_info = {
            "identifier": scenario.identifier,
            "name": scenario.name,
        }
        await session.delete(scenario)
        await session.commit()
        _clear_conversation_scenario_id(conversation_id, project_id)
        return replaced_info

    _clear_conversation_scenario_id(conversation_id, project_id)
    return None


@tool
async def create_test_scenario(
    project_identifier: str,
    name: str,
    description: str = "",
    folder_id: str | None = None,
    config: Annotated[RunnableConfig, InjectedToolArg()] = None,
) -> str:
    """
    创建一个新的测试场景

    测试场景用于编排多个 API 接口的业务流测试，例如：
    - 用户登录 → 创建订单 → 支付 → 查询订单状态
    - 注册用户 → 验证邮箱 → 完善资料 → 上传头像

    注意：同一次 AI 对话（conversation_id 相同）中最终只保留一个场景。如果 AI
    在同一次对话中再次调用本工具，会先删除该对话下已创建的旧场景，然后创建
    新场景，实现覆盖/替换。不同对话之间互不影响。

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
    # 从 LangGraph 运行时配置或 contextvar 中获取当前对话的 conversation_id
    conversation_id = _get_current_conversation_id(config)

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

            # 2. 同一次对话（conversation）内如果已创建过场景，先删除旧场景以便重新生成
            replaced_info = await _replace_conversation_scenario(session, conversation_id, project.id)

            # 2.1 检测同 project 下同名场景（跨对话去重提示，避免列表被同名场景刷屏）
            # 不强制阻断创建——用户可能确实需要多版本；但通过 warning 告知 AI，
            # 让它在后续回复里提示用户或改用 update_test_scenario。
            duplicate_stmt = select(TestScenario).where(
                TestScenario.project_id == project.id,
                TestScenario.name == name,
            )
            duplicate_result = await session.execute(duplicate_stmt)
            existing_same_name = duplicate_result.scalars().all()
            same_name_warning: str | None = None
            if existing_same_name:
                identifiers = ", ".join(s.identifier for s in existing_same_name[:5])
                same_name_warning = (
                    f"项目下已存在 {len(existing_same_name)} 个同名场景 '{name}'"
                    f"（{identifiers}）。如果意图是更新/重新生成，"
                    f"建议使用 update_test_scenario 更新现有场景，"
                    f"或为新场景使用不同的名称以区分版本。"
                )

            # 3. 生成场景标识符
            # 使用 MAX(identifier) + 1 而非 COUNT(*) + 1，避免因删除/间隙导致
            # 标识符冲突（如 TS-0004 已存在时 COUNT 无法感知而反复失败）
            from sqlalchemy import func
            max_stmt = select(func.max(TestScenario.identifier)).where(
                TestScenario.project_id == project.id
            )
            max_result = await session.execute(max_stmt)
            max_identifier = max_result.scalar()
            if max_identifier and max_identifier.startswith("TS-"):
                try:
                    max_number = int(max_identifier.split("-")[1])
                except (ValueError, IndexError):
                    max_number = 0
            else:
                max_number = 0
            identifier = f"TS-{max_number + 1:04d}"

            # 4. 创建场景
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

            # 记录当前 conversation 已创建的场景，用于同对话去重
            _set_conversation_scenario_id(conversation_id, project.id, scenario.id)

            response_data = {
                "success": True,
                "message": f"成功创建测试场景 {identifier}",
                "data": {
                    "scenario_id": str(scenario.id),
                    "identifier": scenario.identifier,
                    "name": scenario.name,
                    "status": scenario.status,
                    "total_steps": 0,
                }
            }
            # 如果覆盖了对话内的旧场景，明确告知 AI
            if replaced_info:
                response_data["replaced"] = {
                    "identifier": replaced_info["identifier"],
                    "name": replaced_info["name"],
                    "note": (
                        f"已删除本对话内之前创建的场景 {replaced_info['identifier']} "
                        f"({replaced_info['name']})，新场景 {identifier} 将替换它。"
                        f"如需修复而非重建，请使用 update_test_scenario / update_scenario_step。"
                    ),
                }
            if same_name_warning:
                response_data["warning"] = same_name_warning

            return json.dumps(response_data, ensure_ascii=False, indent=2)

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
    teardown_config: dict | None = None,
) -> str:
    """
    更新测试场景的基本信息

    可以修改场景的名称、描述、状态、全局变量和 teardown 清理配置。

    Args:
        scenario_id: 场景 ID
        name: 新的场景名称（可选）
        description: 新的场景描述（可选）
        status: 新的场景状态（可选，draft/active/archived）
        global_variables: 全局变量字典（可选）
        teardown_config: teardown 清理配置（可选），格式示例：
            {
              "steps": [
                {
                  "name": "删除测试客户",
                  "endpoint_id": "uuid",
                  "request_override": {"method": "DELETE", "path": "/customers/{{customerId}}"},
                  "headers_override": {},
                  "continue_on_failure": true
                }
              ]
            }

    Returns:
        JSON 格式的更新结果

    Example:
        >>> result = await update_test_scenario(
        ...     scenario_id="uuid-xxx",
        ...     name="更新后的场景名称",
        ...     teardown_config={"steps": [{"name": "清理客户", "endpoint_id": "...", "request_override": {"method": "DELETE", "path": "/customers/{{customerId}}"}}]}
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

            if teardown_config is not None:
                scenario.teardown_config = teardown_config
                updated_fields.append("teardown_config")

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
                    "teardown_config": scenario.teardown_config,
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
async def add_teardown_step(
    scenario_id: str,
    name: str,
    request_override: dict,
    endpoint_id: str | None = None,
    headers_override: dict | None = None,
    continue_on_failure: bool = True,
) -> str:
    """
    向场景追加一个 teardown 清理步骤

    场景主流程执行结束后，会按顺序执行 teardown 步骤，用于删除/禁用
    主流程中创建的资源（如客户、订单、文件等）。

    Args:
        scenario_id: 场景 ID
        name: 清理步骤名称（如 "删除测试客户"）
        request_override: 请求覆盖配置，可引用主流程提取的变量，如
            {"method": "DELETE", "path": "/customers/{{customerId}}"}
        endpoint_id: 清理接口端点 ID（可选；若为空则尝试从 request_override 推断）
        headers_override: 请求头覆盖（可选）
        continue_on_failure: 该步骤失败后是否继续执行后续 teardown，默认 true

    Returns:
        JSON 格式的添加结果

    Example:
        >>> result = await add_teardown_step(
        ...     scenario_id="uuid-xxx",
        ...     name="删除测试客户",
        ...     endpoint_id="uuid-yyy",
        ...     request_override={"method": "DELETE", "path": "/customers/{{customerId}}"},
        ...     continue_on_failure=True
        ... )
    """
    async with async_session_factory() as session:
        try:
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

            teardown_config = scenario.teardown_config or {}
            steps = list(teardown_config.get("steps", []))
            steps.append({
                "name": name,
                "endpoint_id": endpoint_id,
                "request_override": request_override or {},
                "headers_override": headers_override or {},
                "continue_on_failure": continue_on_failure,
            })
            scenario.teardown_config = {**teardown_config, "steps": steps}
            scenario.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(scenario)

            return json.dumps({
                "success": True,
                "message": f"成功为场景 {scenario.identifier} 添加 teardown 步骤: {name}",
                "data": {
                    "scenario_id": str(scenario.id),
                    "teardown_step_count": len(steps),
                    "teardown_config": scenario.teardown_config,
                }
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            await session.rollback()
            return json.dumps({
                "success": False,
                "error": f"添加 teardown 步骤失败: {str(e)}"
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
    variable_exports: list[dict] | None = None,
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
        variable_exports: 变量导出配置（可选），用于将步骤请求/响应中的值导出为变量，
            供后续步骤引用。格式示例：
            [{"name": "siteName", "source": "request", "path": "$.body.name"}]

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

            # 3. 查询当前已有步骤并确定步骤顺序
            steps_stmt = select(ScenarioStep).where(
                ScenarioStep.scenario_id == UUID(scenario_id)
            )
            steps_result = await session.execute(steps_stmt)
            existing_steps = steps_result.scalars().all()

            if step_order is None:
                step_order = len(existing_steps) + 1

            # 3.5 按 endpoint schema 自动填充必填字段默认值
            request_override, auto_filled_fields = _fill_required_body_defaults(
                endpoint, request_override
            )

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
                variable_exports=variable_exports or [],
            )
            session.add(step)

            # 5. 更新场景的步骤总数
            scenario.total_steps = len(existing_steps) + 1
            scenario.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(step)

            response_data = {
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
            }
            if auto_filled_fields:
                response_data["data"]["auto_filled_required_fields"] = auto_filled_fields
                response_data["note"] = (
                    f"已根据接口 schema 自动填充必填字段: {', '.join(auto_filled_fields)}。"
                    f"请检查生成的占位符是否符合业务语义，必要时用 update_scenario_step 调整。"
                )

            return json.dumps(response_data, ensure_ascii=False, indent=2)

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
    assertions: list[dict] | None = None,
    extractors: list[dict] | None = None,
    variable_exports: list[dict] | None = None,
) -> str:
    """
    更新测试场景步骤的配置

    可以修改步骤的名称、描述、请求参数、请求头、断言、提取器、变量导出等配置。

    Args:
        step_id: 步骤 ID
        name: 新的步骤名称（可选）
        description: 新的步骤描述（可选）
        request_override: 新的请求参数覆盖（可选）
        headers_override: 新的请求头覆盖（可选）
        continue_on_failure: 失败后是否继续执行（可选）
        delay_ms: 执行延迟（毫秒，可选）
        assertions: 完整的断言列表（可选），会替换现有所有断言。
            每个断言格式: {"type": "jsonpath", "path": "$.code", "expected": "2000", "operator": "eq"}
            当 add_step_assertion 持久化异常时，可用此参数一次性设置。
        extractors: 完整的提取器列表（可选），会替换现有所有提取器。
            每个提取器格式: {"name": "siteId", "path": "$.data.id", "type": "jsonpath"}
        variable_exports: 完整的变量导出列表（可选），会替换现有所有导出。
            每个导出格式: {"name": "siteName", "source": "request", "path": "$.body.name", "type": "jsonpath"}

    Returns:
        JSON 格式的更新结果

    Example:
        >>> result = await update_scenario_step(
        ...     step_id="uuid-xxx",
        ...     name="更新后的步骤名称",
        ...     request_override={"body": {"new_param": "value"}},
        ...     continue_on_failure=True,
        ...     assertions=[
        ...         {"type": "status", "expected": 200, "operator": "eq"},
        ...         {"type": "jsonpath", "path": "$.code", "expected": "2000", "operator": "eq"},
        ...     ]
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

            if assertions is not None:
                step.assertions = assertions
                updated_fields.append("assertions")

            if extractors is not None:
                step.extractors = extractors
                updated_fields.append("extractors")

            if variable_exports is not None:
                step.variable_exports = variable_exports
                updated_fields.append("variable_exports")

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
                    "assertions": step.assertions,
                    "extractors": step.extractors,
                    "variable_exports": step.variable_exports,
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

            # 3. 按 target_path 去重：同一目标路径已有映射则更新，避免重复配置
            existing_mapping_stmt = select(StepDataMapping).where(
                StepDataMapping.step_id == UUID(step_id),
                StepDataMapping.target_path == target_path,
            )
            existing_mapping_result = await session.execute(existing_mapping_stmt)
            existing_mapping = existing_mapping_result.scalar_one_or_none()

            if existing_mapping:
                existing_mapping.source_type = source_type
                existing_mapping.source_step_id = UUID(source_step_id) if source_step_id else None
                existing_mapping.source_path = source_path
                existing_mapping.transform_expression = transform_expression
                existing_mapping.description = description
                mapping = existing_mapping
                action = "更新"
            else:
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
                action = "添加"
            await session.commit()
            await session.refresh(mapping)
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDJWMVlRPT06MTVjYjUwZTk=

            return json.dumps({
                "success": True,
                "message": f"成功{action}数据映射: {source_path} → {target_path}",
                "data": {
                    "mapping_id": str(mapping.id),
                    "source_type": mapping.source_type,
                    "source_path": mapping.source_path,
                    "target_path": mapping.target_path,
                    "transform": mapping.transform_expression,
                    "action": action,
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

            # 2. 添加提取器到步骤的 extractors 列表（按 name 去重）
            extractor = {
                "name": name,
                "path": path,
                "type": extractor_type,
            }

            extractors = step.extractors or []
            # 按 name 去重：已存在同名提取器则更新，否则追加
            updated_existing = False
            for i, e in enumerate(extractors):
                if e.get("name") == name:
                    extractors[i] = extractor
                    updated_existing = True
                    break

            if updated_existing:
                action = "更新"
            else:
                extractors.append(extractor)
                action = "添加"

            # 使用原子 UPDATE 而非 ORM change-tracking，避免 JSONB 变异追踪问题
            from sqlalchemy import update as sa_update
            await session.execute(
                sa_update(ScenarioStep)
                .where(ScenarioStep.id == step.id)
                .values(extractors=extractors, updated_at=datetime.now(timezone.utc))
            )
            await session.commit()

            # 强制刷新，避免 expire_on_commit=False 导致 identity map 返回旧对象
            await session.refresh(step, ["extractors"])

            # ---- 提交后验证：确认数据库中的内容是否与预期一致 ----
            persisted_extractors = step.extractors or []
            actually_persisted = _deep_equal(persisted_extractors, extractors)

            response_data = {
                "success": actually_persisted,
                "message": f"成功{action}数据提取器: {name} = {path}" if actually_persisted else f"数据提取器{action}后验证失败",
                "data": {
                    "action": action,
                    "extractor": extractor,
                    "total_extractors": len(extractors),
                    "verified": actually_persisted,
                }
            }

            if not actually_persisted:
                response_data["error"] = (
                    f"提取器已写入但提交后验证失败：数据库中的内容与预期不一致。"
                    f"这可能是 JSONB 持久化 bug，"
                    f"建议改用 update_scenario_step 一次性设置完整的 extractors 列表。"
                )

            return json.dumps(response_data, ensure_ascii=False, indent=2)

        except Exception as e:
            await session.rollback()
            import traceback
            return json.dumps({
                "success": False,
                "error": f"添加提取器失败: {str(e)}",
                "stack_trace": traceback.format_exc(),
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

            # 归一化操作符，防止 AI 传入空字符串或非法值
            try:
                operator = normalize_operator(operator, default="eq")
            except ValueError as e:
                return json.dumps({
                    "success": False,
                    "error": str(e),
                }, ensure_ascii=False, indent=2)

            # 2. 添加断言到步骤的 assertions 列表（按 type+path 去重）
            assertion = {
                "type": assertion_type,
                "expected": expected,
                "operator": operator,
            }

            if path:
                assertion["path"] = path

            assertions: list[dict] = step.assertions or []
            # 按 (type, path) 去重：已存在同类型同路径的断言则更新，否则追加
            dedup_key = (assertion_type, path)
            updated_existing = False
            for i, a in enumerate(assertions):
                if (a.get("type"), a.get("path")) == dedup_key:
                    assertions[i] = assertion
                    updated_existing = True
                    break

            if updated_existing:
                action = "更新"
            else:
                assertions.append(assertion)
                action = "添加"

            # 使用原子 UPDATE 而非 ORM change-tracking，避免 JSONB 变异追踪问题
            # 以及并发场景下潜在的丢失更新（Lost Update）
            from sqlalchemy import update as sa_update
            await session.execute(
                sa_update(ScenarioStep)
                .where(ScenarioStep.id == step.id)
                .values(assertions=assertions, updated_at=datetime.now(timezone.utc))
            )
            await session.commit()

            # 强制刷新，避免 expire_on_commit=False 导致 identity map 返回旧对象
            await session.refresh(step, ["assertions"])

            # ---- 提交后验证：确认数据库中的内容是否与预期一致 ----
            persisted_assertions = step.assertions or []
            actually_persisted = _deep_equal(persisted_assertions, assertions)

            response_data: dict = {
                "success": actually_persisted,
                "message": f"成功{action}断言: {assertion_type}" if actually_persisted else f"断言{action}后验证失败",
                "data": {
                    "action": action,
                    "assertion": assertion,
                    "total_assertions": len(assertions),
                    "verified": actually_persisted,
                }
            }

            if not actually_persisted:
                response_data["error"] = (
                    f"断言已写入但提交后验证失败：数据库中的内容与预期不一致。"
                    f"这可能是 JSONB 持久化 bug，"
                    f"建议改用 update_scenario_step 一次性设置完整的 assertions 列表。"
                )

            return json.dumps(response_data, ensure_ascii=False, indent=2)

        except Exception as e:
            await session.rollback()
            import traceback
            return json.dumps({
                "success": False,
                "error": f"添加断言失败: {str(e)}",
                "stack_trace": traceback.format_exc(),
            }, ensure_ascii=False, indent=2)


@tool
async def add_step_variable_export(
    step_id: str,
    name: str,
    path: str,
    source: str = "request",
    export_type: str = "jsonpath",
) -> str:
    """
    为步骤添加变量导出

    将步骤执行后的请求值或响应值导出到上下文变量，供后续步骤通过 {{name}} 引用。
    常用于解决 {{$timestamp}}、{{$uuid}} 等动态占位符跨步骤不一致的问题。

    Args:
        step_id: 步骤 ID
        name: 导出的变量名（如 "siteName"）
        path: 提取路径（JSONPath 格式，如 "$.body.name"）
        source: 数据来源（"request" 或 "response"，默认 "request"）
        export_type: 提取器类型（默认 "jsonpath"）

    Returns:
        JSON 格式的添加结果

    Example:
        >>> result = await add_step_variable_export(
        ...     step_id="uuid-xxx",
        ...     name="siteName",
        ...     path="$.body.name",
        ...     source="request",
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

            # 校验 source
            if source not in ("request", "response"):
                return json.dumps({
                    "success": False,
                    "error": f"无效的 source: {source}。可选值: request, response"
                }, ensure_ascii=False, indent=2)

            # 2. 添加/更新变量导出配置（按 name 去重）
            export = {
                "name": name,
                "path": path,
                "source": source,
                "type": export_type,
            }

            variable_exports = step.variable_exports or []
            updated_existing = False
            for i, e in enumerate(variable_exports):
                if e.get("name") == name:
                    variable_exports[i] = export
                    updated_existing = True
                    break

            action = "更新" if updated_existing else "添加"
            if not updated_existing:
                variable_exports.append(export)

            # 使用原子 UPDATE 避免 JSONB 变异追踪问题
            from sqlalchemy import update as sa_update
            await session.execute(
                sa_update(ScenarioStep)
                .where(ScenarioStep.id == step.id)
                .values(variable_exports=variable_exports, updated_at=datetime.now(timezone.utc))
            )
            await session.commit()

            # 强制刷新，避免 expire_on_commit=False 导致 identity map 返回旧对象
            await session.refresh(step, ["variable_exports"])

            # 提交后验证
            persisted_exports = step.variable_exports or []
            actually_persisted = _deep_equal(persisted_exports, variable_exports)

            response_data = {
                "success": actually_persisted,
                "message": f"成功{action}变量导出: {name} = {path} (source={source})" if actually_persisted else f"变量导出{action}后验证失败",
                "data": {
                    "action": action,
                    "export": export,
                    "total_exports": len(variable_exports),
                    "verified": actually_persisted,
                }
            }

            if not actually_persisted:
                response_data["error"] = (
                    f"变量导出已写入但提交后验证失败：数据库中的内容与预期不一致。"
                    f"这可能是 JSONB 持久化 bug，"
                    f"建议改用 update_scenario_step 一次性设置完整的 variable_exports 列表。"
                )

            return json.dumps(response_data, ensure_ascii=False, indent=2)

        except Exception as e:
            await session.rollback()
            import traceback
            return json.dumps({
                "success": False,
                "error": f"添加变量导出失败: {str(e)}",
                "stack_trace": traceback.format_exc(),
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
                    "request_override": step.request_override,
                    "headers_override": step.headers_override,
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
                    "warnings": _build_scenario_warnings(steps_data),
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
    skip_assertion_gate: bool = False,
    skip_design_gate: bool = False,
) -> str:
    """
    执行测试场景

    按照场景定义的步骤顺序执行所有 API 调用，处理数据依赖，验证断言。

    Args:
        scenario_id: 场景 ID
        variables: 运行时变量（可选，如 {"username": "test", "password": "123456"}）
        base_url: API 基础 URL（可选，如 "https://api.example.com"）
        debug: 是否启用调试模式（可选，启用后会返回详细的请求/响应信息）
        skip_assertion_gate: 是否跳过断言质量门禁（可选，默认 False）。
            当断言持久化存在后端 bug 导致无法配置断言时，可设为 True 绕过门禁执行。
            注意：跳过门禁后，步骤即使没有 jsonpath 断言也能执行，但步骤结果中不会有业务断言验证。
        skip_design_gate: 是否跳过场景设计静态预检（可选，默认 False）。
            当接口 schema 不完整导致误报，或调试生成阶段行为时可设为 True 绕过。

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
            # ---- 预加载场景步骤与端点，供设计门禁和断言门禁共用 ----
            steps_stmt = select(ScenarioStep).where(
                ScenarioStep.scenario_id == UUID(scenario_id)
            ).order_by(ScenarioStep.step_order)
            steps_result = await session.execute(steps_stmt)
            steps = list(steps_result.scalars().all())

            endpoint_ids = {s.endpoint_id for s in steps if s.endpoint_id}
            endpoints: dict[UUID, APIEndpoint] = {}
            if endpoint_ids:
                endpoints_result = await session.execute(
                    select(APIEndpoint).where(APIEndpoint.id.in_(endpoint_ids))
                )
                endpoints = {e.id: e for e in endpoints_result.scalars().all()}

            scenario = await session.get(TestScenario, UUID(scenario_id))
            teardown_config = scenario.teardown_config if scenario else None

            # ---- 场景设计静态预检：在执行真实 HTTP 请求前拦截生成侧质量问题 ----
            design_warnings: list[dict] = []
            if not skip_design_gate:
                design_check = await _validate_scenario_design(
                    session, UUID(scenario_id), steps, endpoints, teardown_config,
                    runtime_variables=variables,
                )
                design_warnings = design_check["warnings"]
                if design_check["errors"]:
                    return json.dumps({
                        "success": False,
                        "error": "场景设计静态预检未通过，请在执行前修复以下问题",
                        "issues": design_check["errors"] + design_check["warnings"],
                        "hint": (
                            "根据 message/fix 提示修复后重试；"
                            "如确认是 schema 不全导致误报，可设置 skip_design_gate=true 绕过。"
                        ),
                    }, ensure_ascii=False, indent=2)
            else:
                import logging
                logging.getLogger(__name__).warning(
                    "跳过场景设计静态预检（skip_design_gate=true），生成侧质量问题可能无法提前发现"
                )

            # ---- 断言质量门禁：执行前校验每个步骤的断言配置 ----
            if not skip_assertion_gate:
                invalid_steps: list[dict] = []
                for step in steps:
                    assertions = step.assertions or []
                    if not assertions:
                        invalid_steps.append({
                            "step_order": step.step_order,
                            "step_name": step.name,
                            "issue": "未配置任何断言",
                        })
                        continue
                    has_non_status = any(
                        a.get("type") in ("jsonpath", "header") for a in assertions
                    )
                    if not has_non_status:
                        invalid_steps.append({
                            "step_order": step.step_order,
                            "step_name": step.name,
                            "issue": "只有 status 断言，缺少 jsonpath/header 业务断言",
                        })

                if invalid_steps:
                    return json.dumps({
                        "success": False,
                        "error": "场景断言质量门禁未通过：每个步骤必须至少包含 1 个非 status 断言（jsonpath/header）",
                        "invalid_steps": invalid_steps,
                        "hint": "请使用 add_step_assertion 为缺失步骤补充 jsonpath 或 header 断言后重试执行。"
                                "如果断言持久化存在后端 bug，可设置 skip_assertion_gate=true 跳过门禁。",
                    }, ensure_ascii=False, indent=2)
            else:
                import logging
                logging.getLogger(__name__).warning(
                    "跳过断言质量门禁（skip_assertion_gate=true），步骤可能缺少业务断言"
                )

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
                    "global_variables": scenario.global_variables if scenario else {},
                }

            # 构建结果
            result_data = {
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
            if design_warnings:
                result_data["design_warnings"] = design_warnings

            return json.dumps({
                "success": True,
                "message": f"场景执行{'成功' if run.status == 'completed' else '失败'}",
                "data": result_data,
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

