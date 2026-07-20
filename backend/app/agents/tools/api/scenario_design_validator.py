"""
场景设计校验工具

把场景测试的生成阶段质量检查沉淀为可复用、可测试的独立工具，
供 AI 助手在生成场景时主动调用，也被 execute_scenario 在执行前复用。
"""

import re
from typing import Any
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import async_session_factory
from app.models.api_endpoint import APIEndpoint
from app.models.test_scenario import (
    ScenarioStep,
    StepDataMapping,
    TestScenario,
)


def _extract_path_params(path: str | None) -> list[str]:
    """从 URL 路径中提取 {param} 参数名"""
    return re.findall(r"\{(\w+)\}", path or "")


def _get_request_body_required(endpoint: APIEndpoint) -> list[str]:
    """获取 endpoint request_body 中声明的必填字段"""
    try:
        body = endpoint.request_body or {}
        content = body.get("content", {})
        json_schema = content.get("application/json", {}).get("schema", {})
        return json_schema.get("required", []) or []
    except Exception:
        return []


def _get_query_param_names(endpoint: APIEndpoint) -> set[str] | None:
    """获取 endpoint parameters 中声明的 query 参数名。

    返回 None 表示接口没有 parameters 信息（schema 未提供），
    返回空集合表示明确声明了 parameters 但其中没有 query 参数。
    """
    try:
        params = endpoint.parameters
        if params is None:
            return None
        return {p["name"] for p in params if isinstance(p, dict) and p.get("in") == "query"}
    except Exception:
        return None


def _scan_template_variables(obj: Any) -> list[str]:
    """扫描对象中的 {{variable}} 和 {{$dynamic}} 模板变量名"""
    found: list[str] = []
    if isinstance(obj, str):
        for match in re.finditer(r"\{\{\s*\$(\s*\w+(?:\.\w+)*(?:\([^)]*\))?\s*)\s*\}\}", obj):
            found.append("$" + match.group(1).strip())
        for match in re.finditer(r"\{\{\s*(\w+(?:\.\w+)*)\s*\}\}", obj):
            found.append(match.group(1).strip())
    elif isinstance(obj, dict):
        for value in obj.values():
            found.extend(_scan_template_variables(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_scan_template_variables(item))
    return found


async def _validate_scenario_design(
    session: AsyncSession,
    scenario_id: UUID,
    steps: list[ScenarioStep],
    endpoints: dict[UUID, APIEndpoint],
    teardown_config: dict | None,
) -> dict:
    """场景设计静态预检：在执行真实 HTTP 请求前拦截生成侧质量问题"""
    errors: list[dict] = []
    warnings: list[dict] = []

    # 收集每个步骤的提取器变量名
    extractor_vars_by_step: dict[UUID, set[str]] = {}
    for step in steps:
        extractors = step.extractors or []
        extractor_vars_by_step[step.id] = {
            e.get("name") for e in extractors if e.get("name")
        }

    # 收集每个步骤的数据映射目标变量名（target_path 最后一段）
    mapping_targets_by_step: dict[UUID, set[str]] = {}
    if steps:
        mappings_result = await session.execute(
            select(StepDataMapping).where(
                StepDataMapping.step_id.in_([s.id for s in steps])
            )
        )
        for mapping in mappings_result.scalars().all():
            target_var = (
                mapping.target_path.rsplit(".", 1)[-1]
                if "." in mapping.target_path
                else mapping.target_path
            )
            mapping_targets_by_step.setdefault(mapping.step_id, set()).add(target_var)

    # 全局变量
    scenario = await session.get(TestScenario, scenario_id)
    global_vars: set[str] = set((scenario.global_variables or {}).keys()) if scenario else set()

    for step in steps:
        endpoint = endpoints.get(step.endpoint_id)
        if not endpoint:
            continue

        request_override = step.request_override or {}
        body = request_override.get("body") or {}
        params = request_override.get("params") or {}
        assertions = step.assertions or []

        # 1. 必填字段缺失检查
        required_fields = _get_request_body_required(endpoint)
        if isinstance(body, dict):
            for field in required_fields:
                if field not in body or body[field] is None:
                    errors.append({
                        "step_order": step.step_order,
                        "step_name": step.name,
                        "severity": "error",
                        "category": "missing_required_field",
                        "message": f"步骤 {step.step_order} 的请求体缺少必填字段: {field}",
                        "fix": f"使用 update_scenario_step 为 request_override.body 补充 {field}",
                    })

        # 2. 路径参数残留检查
        path_used = request_override.get("path") or endpoint.path or ""
        endpoint_params = set(_extract_path_params(endpoint.path))
        override_params = set(_extract_path_params(path_used))
        all_path_params = endpoint_params | override_params
        available_vars = (
            extractor_vars_by_step.get(step.id, set())
            | mapping_targets_by_step.get(step.id, set())
            | global_vars
        )
        for param in all_path_params:
            if param not in available_vars:
                errors.append({
                    "step_order": step.step_order,
                    "step_name": step.name,
                    "severity": "error",
                    "category": "unmapped_path_param",
                    "message": f"路径参数 {{{param}}} 未映射到任何 extractor / data_mapping / 全局变量",
                    "fix": (
                        f"在前序步骤添加 add_step_extractor(name='{param}')，"
                        f"或在 request_override.path 中使用 {{{{ {param} }}}} 引用"
                    ),
                })

        # 3. 分页/列表步骤业务断言检查
        method = (endpoint.method or "GET").upper()
        params_str = str(params).lower()
        is_pagination = (
            method == "GET"
            or "page" in params_str
            or "size" in params_str
            or "current" in params_str
        )
        if is_pagination:
            has_list_assertion = any(
                a.get("type") == "jsonpath"
                and any(k in (a.get("path") or "") for k in ("records", "list", "total", "data"))
                for a in assertions
            )
            if not has_list_assertion:
                warnings.append({
                    "step_order": step.step_order,
                    "step_name": step.name,
                    "severity": "warning",
                    "category": "weak_pagination_assertion",
                    "message": "分页/列表步骤缺少针对 records/list/total 等业务字段的断言",
                    "fix": "使用 add_step_assertion 添加 $.data.records ne null 和 $.data.total 相关断言",
                })

        # 4. 创建类步骤 teardown 检查
        step_name_lower = (step.name or "").lower()
        create_keywords = {
            "创建", "新建", "新增", "添加", "上传", "生成",
            "create", "add", "new", "upload", "generate",
        }
        is_create_step = (
            method == "POST"
            and any(k in step_name_lower for k in create_keywords)
        )
        if is_create_step:
            teardown_steps = (teardown_config or {}).get("steps", [])
            if not teardown_steps:
                warnings.append({
                    "step_order": step.step_order,
                    "step_name": step.name,
                    "severity": "warning",
                    "category": "missing_teardown",
                    "message": "创建类步骤未配置 teardown 清理，可能导致脏数据堆积",
                    "fix": "使用 add_teardown_step 添加删除/禁用该资源的步骤，并引用本步骤提取的资源 ID",
                })

        # 5. 未在 schema 中声明的 query 参数检查
        declared_query = _get_query_param_names(endpoint)
        if isinstance(params, dict) and declared_query is not None:
            for param_name in params:
                if param_name not in declared_query:
                    warnings.append({
                        "step_order": step.step_order,
                        "step_name": step.name,
                        "severity": "warning",
                        "category": "unverified_param",
                        "message": f"params.{param_name} 未在接口 schema 的 query 参数中声明",
                        "fix": "确认该参数是否必需；非必需请移除，必需请先以最小参数验证基础流程",
                    })

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


@tool
async def validate_scenario_design(scenario_id: str) -> str:
    """
    对场景设计做静态预检，在执行前发现生成侧质量问题。

    校验项：
    - 必填字段缺失
    - 路径参数未映射
    - 分页/列表步骤缺少业务断言
    - 创建类步骤缺少 teardown
    - params 中未在 schema 声明的参数

    Args:
        scenario_id: 场景 ID

    Returns:
        JSON 格式的校验报告，包含 errors / warnings / suggestions

    Example:
        >>> result = await validate_scenario_design("uuid-xxx")
    """
    async with async_session_factory() as session:
        try:
            # 加载场景步骤
            steps_stmt = select(ScenarioStep).where(
                ScenarioStep.scenario_id == UUID(scenario_id)
            ).order_by(ScenarioStep.step_order)
            steps_result = await session.execute(steps_stmt)
            steps = list(steps_result.scalars().all())

            # 加载关联端点
            endpoint_ids = {s.endpoint_id for s in steps if s.endpoint_id}
            endpoints: dict[UUID, APIEndpoint] = {}
            if endpoint_ids:
                endpoints_result = await session.execute(
                    select(APIEndpoint).where(APIEndpoint.id.in_(endpoint_ids))
                )
                endpoints = {e.id: e for e in endpoints_result.scalars().all()}

            # 加载 teardown 配置
            scenario = await session.get(TestScenario, UUID(scenario_id))
            teardown_config = scenario.teardown_config if scenario else None

            design_check = await _validate_scenario_design(
                session, UUID(scenario_id), steps, endpoints, teardown_config
            )

            suggestions: list[str] = []
            for issue in design_check["errors"] + design_check["warnings"]:
                fix = issue.get("fix")
                if fix:
                    suggestions.append(f"[步骤 {issue.get('step_order')}] {fix}")

            return __import__("json").dumps({
                "success": True,
                "scenario_id": scenario_id,
                "valid": design_check["valid"],
                "summary": {
                    "errors": len(design_check["errors"]),
                    "warnings": len(design_check["warnings"]),
                },
                "issues": design_check["errors"] + design_check["warnings"],
                "suggestions": suggestions,
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            import traceback
            return __import__("json").dumps({
                "success": False,
                "error": f"场景设计校验失败: {str(e)}",
                "stack_trace": traceback.format_exc(),
            }, ensure_ascii=False, indent=2)
