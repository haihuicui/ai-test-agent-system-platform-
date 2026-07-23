"""
测试用例管理工具

提供测试用例创建、更新和批量操作的 HTTP 接口调用工具，
以及用例抽样预览能力（用于 Phase 3 人工评审）。
"""

import logging
from typing import Optional, Any

import httpx
from langchain_core.tools import tool

from app.agents.tools.testcase.excel_tools import (
    _load_test_cases_from_file,
    _parse_json_objects,
)
from app.agents.tools.testcase.export_common import extract_field
from app.config.settings import settings

logger = logging.getLogger(__name__)

API_BASE_URL = settings.backend_api_url
API_PREFIX = settings.api_prefix


def _get_api_url(path: str) -> str:
    """构建完整的 API URL"""
    return f"{API_BASE_URL}{API_PREFIX}{path}"


def _resolve_field(data: dict[str, Any], *keys: str) -> Any:
    """按候选 key 顺序从字典中提取字段，用于兼容 Agent 输出的多种字段别名。"""
    for key in keys:
        if key in data:
            return data[key]
    return None


def _normalize_steps(steps: Any) -> Optional[list[dict[str, str]]]:
    """标准化测试步骤列表，兼容多种字段别名。

    支持的 step 字段别名：step, action, 操作描述, description, desc
    支持的 result 字段别名：result, expected_result, expected, 预期结果
    """
    if not steps:
        return None
    if not isinstance(steps, list):
        return None

    normalized: list[dict[str, str]] = []
    for step in steps:
        if isinstance(step, str):
            normalized.append({"step": step, "result": ""})
        elif isinstance(step, dict):
            action = _resolve_field(
                step, "step", "action", "操作描述", "description", "desc"
            )
            result = _resolve_field(
                step, "result", "expected_result", "expected", "预期结果"
            )
            normalized.append({"step": action or "", "result": result or ""})
        else:
            normalized.append({"step": str(step), "result": ""})
    return normalized


# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNOVE5RPT06YjNlZWQyMDc=

async def _make_http_request(
    method: str,
    url: str,
    json_data: Optional[dict] = None,
    params: Optional[dict] = None,
) -> dict[str, Any]:
    """发送 HTTP 请求的通用函数"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        try:
            error_json = e.response.json()
            error_detail = error_json.get("detail", error_detail)
        except Exception:
            pass
        raise Exception(f"HTTP {e.response.status_code}: {error_detail}")
    except httpx.RequestError as e:
        raise Exception(f"网络请求失败: {str(e)}")
    except Exception as e:
        raise Exception(f"请求失败: {str(e)}")


async def _create_test_case_impl(
    project_identifier: str,
    name: str,
    folder_id: Optional[str] = None,
    description: Optional[str] = None,
    preconditions: Optional[str] = None,
    priority: str = "medium",
    status: str = "new",
    case_type: str = "functional",
    owner: Optional[str] = None,
    tags: Optional[list[str]] = None,
    issues: Optional[list[str]] = None,
    automation_status: str = "not_automated",
    custom_fields: Optional[dict[str, Any]] = None,
    template: str = "test_case",
    test_case_steps: Optional[list[dict[str, str]]] = None,
    feature: Optional[str] = None,
    scenario: Optional[str] = None,
    background: Optional[str] = None,
    module: Optional[str] = None,
    test_data: Optional[dict[str, Any]] = None,
    case_number: Optional[str] = None,
    case_id: Optional[str] = None,
    remarks: Optional[str] = None,
) -> dict[str, Any]:
    """创建测试用例的内部实现"""
    # description 与 remarks 语义相同，优先使用显式传入的 description
    effective_description = description if description is not None else remarks

    if not project_identifier:
        return {
            "success": False,
            "error": "project_identifier 不能为空，请确认 AI 助手已正确获取项目上下文",
            "message": "创建测试用例失败：project_identifier 为空",
        }

    request_data: dict[str, Any] = {
        "name": name,
        "template": template,
        "priority": priority,
        "status": status,
        "case_type": case_type,
        "automation_status": automation_status,
    }

    if effective_description is not None:
        request_data["description"] = effective_description
    if preconditions is not None:
        request_data["preconditions"] = preconditions
    if owner is not None:
        request_data["owner"] = owner
    if tags is not None:
        request_data["tags"] = tags
    if issues is not None:
        request_data["issues"] = issues
    if custom_fields is not None:
        request_data["custom_fields"] = custom_fields
    if module is not None:
        request_data["module"] = module
    if test_data is not None:
        request_data["test_data"] = test_data
    # case_number 优先；未提供时尝试 case_id（兼容 Agent 输出中的 id/用例编号）
    effective_case_number = case_number if case_number is not None else case_id
    if effective_case_number is not None:
        request_data["case_number"] = effective_case_number

    if template == "test_case_bdd":
        if feature is not None:
            request_data["feature"] = feature
        if scenario is not None:
            request_data["scenario"] = scenario
        if background is not None:
            request_data["background"] = background
    else:
        if test_case_steps is not None:
            request_data["test_case_steps"] = test_case_steps

    if folder_id:
        url = _get_api_url(f"/projects/{project_identifier}/folders/{folder_id}/test-cases")
    else:
        url = _get_api_url(f"/projects/{project_identifier}/test-cases")
    response_data = await _make_http_request(method="POST", url=url, json_data=request_data)

    if response_data.get("success"):
        test_case_data = response_data.get("data", {})
        return {
            "success": True,
            "data": test_case_data,
            "message": f"测试用例 {test_case_data.get('identifier', '')} 创建成功"
        }
    else:
        return {"success": False, "error": "API 返回失败", "message": "创建测试用例失败"}


@tool
async def create_test_case_tool(
    project_identifier: str,
    name: str,
    folder_id: Optional[str] = None,
    description: Optional[str] = None,
    preconditions: Optional[str] = None,
    priority: str = "medium",
    status: str = "new",
    case_type: str = "functional",
    owner: Optional[str] = None,
    tags: Optional[list[str]] = None,
    issues: Optional[list[str]] = None,
    automation_status: str = "not_automated",
    custom_fields: Optional[dict[str, Any]] = None,
    template: str = "test_case",
    test_case_steps: Optional[list[dict[str, str]]] = None,
    feature: Optional[str] = None,
    scenario: Optional[str] = None,
    background: Optional[str] = None,
    module: Optional[str] = None,
    test_data: Optional[dict[str, Any]] = None,
    case_number: Optional[str] = None,
    case_id: Optional[str] = None,
    remarks: Optional[str] = None,
) -> dict[str, Any]:
    """
    创建测试用例工具（通过 HTTP 接口调用）。

    支持普通测试用例和 BDD 测试用例两种模板。

    Args:
        project_identifier: 项目标识符，如 'PROJ-001'
        folder_id: 文件夹 UUID（可选；为空时保存到项目根，对应前端“全部用例”）
        name: 测试用例名称（必填）
        description: 测试用例描述（可选，支持 HTML）；与 remarks 二选一
        preconditions: 前置条件（可选，支持 HTML）
        priority: 优先级，可选值：critical, high, medium, low（默认 medium）
        status: 状态，默认 new
        case_type: 测试类型，默认 functional
        owner: 负责人邮箱（可选）
        tags: 标签列表（可选）
        issues: 关联的 Jira issues（可选）
        automation_status: 自动化状态，默认 not_automated
        custom_fields: 自定义字段（可选）
        template: 模板类型，默认 test_case
        test_case_steps: 测试步骤列表（普通测试用例使用）
        feature: BDD Feature 描述（BDD 测试用例必填）
        scenario: BDD Scenario 描述（BDD 测试用例必填）
        background: BDD Background 描述（BDD 测试用例可选）
        module: 所属模块（可选）
        test_data: 测试数据（可选，JSON 对象）
        case_number: 用例编号（可选）
        case_id: 用例编号别名（可选，与 case_number 二选一，兼容 Agent 输出中的 id）
        remarks: 备注/需求编号（可选，description 的别名）

    Returns:
        dict: 包含创建结果的字典
    """
    try:
        return await _create_test_case_impl(
            project_identifier=project_identifier,
            folder_id=folder_id,
            name=name,
            description=description,
            preconditions=preconditions,
            priority=priority,
            status=status,
            case_type=case_type,
            owner=owner,
            tags=tags,
            issues=issues,
            automation_status=automation_status,
            custom_fields=custom_fields,
            template=template,
            test_case_steps=test_case_steps,
            feature=feature,
            scenario=scenario,
            background=background,
            module=module,
            test_data=test_data,
            case_number=case_number,
            case_id=case_id,
            remarks=remarks,
        )
    except Exception as e:
        return {"success": False, "error": str(e), "message": f"创建测试用例失败: {str(e)}"}

# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNOVE5RPT06YjNlZWQyMDc=

async def _update_test_case_impl(
    project_identifier: str,
    test_case_identifier: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    preconditions: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    folder_id: Optional[str] = None,
    owner: Optional[str] = None,
    tags: Optional[list[str]] = None,
    issues: Optional[list[str]] = None,
    automation_status: Optional[str] = None,
    custom_fields: Optional[dict[str, Any]] = None,
    test_case_steps: Optional[list[dict[str, str]]] = None,
    feature: Optional[str] = None,
    scenario: Optional[str] = None,
    background: Optional[str] = None,
    module: Optional[str] = None,
    test_data: Optional[dict[str, Any]] = None,
    case_number: Optional[str] = None,
    remarks: Optional[str] = None,
) -> dict[str, Any]:
    """更新测试用例的内部实现"""
    # description 与 remarks 语义相同，优先使用显式传入的 description
    effective_description = description if description is not None else remarks

    request_data: dict[str, Any] = {}

    if name is not None:
        request_data["name"] = name
    if effective_description is not None:
        request_data["description"] = effective_description
    if preconditions is not None:
        request_data["preconditions"] = preconditions
    if priority is not None:
        request_data["priority"] = priority
    if status is not None:
        request_data["status"] = status
    if case_type is not None:
        request_data["case_type"] = case_type
    if folder_id is not None:
        request_data["folder_id"] = folder_id
    if owner is not None:
        request_data["owner"] = owner
    if tags is not None:
        request_data["tags"] = tags
    if issues is not None:
        request_data["issues"] = issues
    if automation_status is not None:
        request_data["automation_status"] = automation_status
    if custom_fields is not None:
        request_data["custom_fields"] = custom_fields
    if test_case_steps is not None:
        request_data["test_case_steps"] = test_case_steps
    if feature is not None:
        request_data["feature"] = feature
    if scenario is not None:
        request_data["scenario"] = scenario
    if background is not None:
        request_data["background"] = background
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNOVE5RPT06YjNlZWQyMDc=

    if module is not None:
        request_data["module"] = module
    if test_data is not None:
        request_data["test_data"] = test_data
    if case_number is not None:
        request_data["case_number"] = case_number

    if not request_data:
        return {
            "success": False,
            "error": "没有提供任何需要更新的字段",
            "message": "更新测试用例失败：没有提供任何需要更新的字段"
        }

    url = _get_api_url(f"/projects/{project_identifier}/test-cases/{test_case_identifier}")
    response_data = await _make_http_request(method="PATCH", url=url, json_data=request_data)

    if response_data.get("success"):
        test_case_data = response_data.get("data", {})
        return {
            "success": True,
            "data": test_case_data,
            "message": f"测试用例 {test_case_data.get('identifier', '')} 更新成功"
        }
    else:
        return {"success": False, "error": "API 返回失败", "message": "更新测试用例失败"}


@tool
async def update_test_case_tool(
    project_identifier: str,
    test_case_identifier: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    preconditions: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    folder_id: Optional[str] = None,
    owner: Optional[str] = None,
    tags: Optional[list[str]] = None,
    issues: Optional[list[str]] = None,
    automation_status: Optional[str] = None,
    custom_fields: Optional[dict[str, Any]] = None,
    test_case_steps: Optional[list[dict[str, str]]] = None,
    feature: Optional[str] = None,
    scenario: Optional[str] = None,
    background: Optional[str] = None,
    module: Optional[str] = None,
    test_data: Optional[dict[str, Any]] = None,
    case_number: Optional[str] = None,
    remarks: Optional[str] = None,
) -> dict[str, Any]:
    """
    更新测试用例工具（通过 HTTP 接口调用）。

    所有字段都是可选的，只更新提供的字段。

    Args:
        project_identifier: 项目标识符，如 'PROJ-001'
        test_case_identifier: 测试用例标识符，如 'TC-1234'
        name: 测试用例名称
        description: 测试用例描述；与 remarks 二选一
        preconditions: 前置条件
        priority: 优先级（critical, high, medium, low）
        status: 状态
        case_type: 测试类型
        folder_id: 所属文件夹 UUID（用于移动测试用例）
        owner: 负责人邮箱
        tags: 标签列表
        issues: 关联的 Jira issues
        automation_status: 自动化状态
        custom_fields: 自定义字段
        test_case_steps: 测试步骤列表
        feature: BDD Feature 描述
        scenario: BDD Scenario 描述
        background: BDD Background 描述
        module: 所属模块（可选）
        test_data: 测试数据（可选，JSON 对象）
        case_number: 用例编号（可选）
        remarks: 备注/需求编号（可选，description 的别名）

    Returns:
        dict: 包含更新结果的字典
    """
    try:
        return await _update_test_case_impl(
            project_identifier=project_identifier,
            test_case_identifier=test_case_identifier,
            name=name,
            description=description,
            preconditions=preconditions,
            priority=priority,
            status=status,
            case_type=case_type,
            folder_id=folder_id,
            owner=owner,
            tags=tags,
            issues=issues,
            automation_status=automation_status,
            custom_fields=custom_fields,
            test_case_steps=test_case_steps,
            feature=feature,
            scenario=scenario,
            background=background,
            module=module,
            test_data=test_data,
            case_number=case_number,
            remarks=remarks,
        )
    except Exception as e:
        return {"success": False, "error": str(e), "message": f"更新测试用例失败: {str(e)}"}


async def _batch_create_test_cases_impl(
    project_identifier: str,
    test_cases: list[dict[str, Any]],
    folder_id: Optional[str] = None,
) -> dict[str, Any]:
    """批量创建测试用例的内部实现"""
    if not project_identifier:
        return {
            "success": False,
            "error": "project_identifier 不能为空，请确认 AI 助手已正确获取项目上下文",
            "message": "批量创建失败：project_identifier 为空",
        }

    if not test_cases:
        return {
            "success": False,
            "error": "测试用例列表为空",
            "message": "批量创建失败：测试用例列表为空"
        }

    results = []
    succeeded = 0
    failed = 0

    for index, test_case_data in enumerate(test_cases):
        try:
            name = test_case_data.get("name")
            if not name:
                results.append({
                    "index": index,
                    "success": False,
                    "name": None,
                    "error": "测试用例名称不能为空",
                })
                failed += 1
                continue

            result = await _create_test_case_impl(
                project_identifier=project_identifier,
                folder_id=folder_id,
                name=name,
                description=_resolve_field(
                    test_case_data,
                    "description", "desc", "描述", "remarks", "备注", "remark",
                ),
                preconditions=_resolve_field(
                    test_case_data, "preconditions", "precondition", "前置条件"
                ),
                priority=test_case_data.get("priority", "medium"),
                status=test_case_data.get("status", "new"),
                case_type=_resolve_field(
                    test_case_data,
                    "case_type", "type", "用例类型", "测试类型", "类型",
                ) or "functional",
                owner=test_case_data.get("owner"),
                tags=test_case_data.get("tags"),
                issues=test_case_data.get("issues"),
                automation_status=test_case_data.get("automation_status", "not_automated"),
                custom_fields=test_case_data.get("custom_fields"),
                template=test_case_data.get("template", "test_case"),
                test_case_steps=_normalize_steps(
                    _resolve_field(test_case_data, "test_case_steps", "steps", "测试步骤")
                ),
                feature=test_case_data.get("feature"),
                scenario=test_case_data.get("scenario"),
                background=test_case_data.get("background"),
                module=_resolve_field(test_case_data, "module", "所属模块"),
                test_data=_resolve_field(test_case_data, "test_data", "测试数据"),
                case_number=_resolve_field(
                    test_case_data, "case_number", "id", "用例编号", "identifier", "case_id", "编号"
                ),
            )
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNOVE5RPT06YjNlZWQyMDc=

            # 仅回传精简结果：完整用例对象（result["data"]）与输入用例体积很大，
            # 会随每次批量创建整段写入 checkpoint / 历史 state，长会话下累积到数百 KB，
            # 拖垮前端「加载历史对话」。Agent 后续只需要「成功/失败 + 用例标识」即可，
            # 因此这里丢弃完整对象，只保留 index/success/identifier/name/error。
            case_data = result.get("data") or {}
            results.append({
                "index": index,
                "success": result.get("success", False),
                "identifier": case_data.get("identifier") or case_data.get("case_number"),
                "name": name,
                "error": result.get("error"),
            })

            if result.get("success"):
                succeeded += 1
            else:
                failed += 1

        except Exception as e:
            results.append({
                "index": index,
                "success": False,
                "name": test_case_data.get("name"),
                "error": str(e),
            })
            failed += 1

    return {
        "success": True,
        "data": {
            "total": len(test_cases),
            "succeeded": succeeded,
            "failed": failed,
            "results": results
        },
        "message": f"批量创建完成：成功 {succeeded} 个，失败 {failed} 个"
    }


@tool
async def batch_create_test_cases_tool(
    project_identifier: str,
    test_cases: list[dict[str, Any]],
    folder_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    批量创建测试用例工具（通过 HTTP 接口调用）。

    每个测试用例的参数与 create_test_case_tool 相同。

    Args:
        project_identifier: 项目标识符，如 'PROJ-001'
        folder_id: 文件夹 UUID（可选；为空时保存到项目根，对应前端“全部用例”）
        test_cases: 测试用例列表，每个元素是一个包含测试用例信息的字典

    Returns:
        dict: 包含批量创建结果的字典
    """
    try:
        return await _batch_create_test_cases_impl(
            project_identifier=project_identifier,
            test_cases=test_cases,
            folder_id=folder_id,
        )
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"批量创建测试用例失败: {str(e)}"
        }


# 控制 preview_test_cases 返回体积，避免写入 checkpoint 时膨胀
_PREVIEW_MAX_STEPS = 5
_PREVIEW_MAX_DATA_KEYS = 10
_PREVIEW_MAX_DATA_VALUE_LEN = 200
_PREVIEW_MAX_CASES = 10


def _is_file_path(source: str) -> bool:
    """判断 source 更可能是文件路径还是 JSON 内容字符串。"""
    stripped = source.strip()
    if not stripped:
        return False
    # 明显是 JSON 对象/数组开头的内容
    if stripped.startswith(("{", "[")):
        return False
    # 换行很多的内容也视为 JSONL 内容
    if stripped.count("\n") > 1 and stripped.splitlines()[0].strip().startswith("{"):
        return False
    return True


def _truncate_steps(steps: Any) -> Any:
    """截断测试步骤，仅保留前 N 步。"""
    if not isinstance(steps, list):
        return steps
    truncated = steps[:_PREVIEW_MAX_STEPS]
    if len(steps) > _PREVIEW_MAX_STEPS:
        truncated.append({
            "step": f"...（后续还有 {len(steps) - _PREVIEW_MAX_STEPS} 步）",
            "result": "",
        })
    return truncated


def _truncate_test_data(test_data: Any) -> Any:
    """截断测试数据：限制字段数和字符串值长度。"""
    if not isinstance(test_data, dict):
        return test_data
    result: dict[str, Any] = {}
    for idx, (key, value) in enumerate(test_data.items()):
        if idx >= _PREVIEW_MAX_DATA_KEYS:
            result["..."] = f"（还有 {len(test_data) - _PREVIEW_MAX_DATA_KEYS} 个字段）"
            break
        if isinstance(value, str) and len(value) > _PREVIEW_MAX_DATA_VALUE_LEN:
            value = value[:_PREVIEW_MAX_DATA_VALUE_LEN] + "..."
        result[key] = value
    return result


def _matches_filters(case: dict[str, Any], module: Optional[str], priority: Optional[str], case_type: Optional[str]) -> bool:
    """按模块、优先级、类型过滤用例。"""
    if module:
        case_module = extract_field(case, "module", "所属模块", "module_name", "功能模块")
        if str(case_module).strip().lower() != module.strip().lower():
            return False
    if priority:
        case_priority = extract_field(case, "priority", "优先级")
        if str(case_priority).strip().lower() != priority.strip().lower():
            return False
    if case_type:
        case_type_value = extract_field(case, "case_type", "type", "用例类型", "测试类型")
        if str(case_type_value).strip().lower() != case_type.strip().lower():
            return False
    return True


@tool
async def preview_test_cases(
    source: str,
    module: Optional[str] = None,
    priority: Optional[str] = None,
    case_type: Optional[str] = None,
    limit: int = 3,
) -> dict[str, Any]:
    """
    从用例数据源中抽样返回关键用例详情，用于 Phase 3 评审报告展示。

    source 可以是：
      - JSONL / JSON 文件路径（如 "/test_cases.jsonl"、"cases.jsonl"）
      - 用例 JSON 内容字符串（JSON 数组或 JSONL 格式）

    返回结果会做体积控制：
      - 默认最多返回 3 条用例
      - 单条用例最多展示 5 个步骤、10 个测试数据字段

    Args:
        source: 用例数据来源（文件路径或 JSON/JSONL 内容）
        module: 按模块名过滤，可选
        priority: 按优先级过滤（如 high / medium / critical / P0），可选
        case_type: 按用例类型过滤（如 functional / security），可选
        limit: 返回用例数量上限，默认 3，最大 10

    Returns:
        dict: 包含预览用例列表的字典
    """
    try:
        limit = max(1, min(int(limit), _PREVIEW_MAX_CASES))

        if _is_file_path(source):
            cases = _load_test_cases_from_file(source, dedup=False)
        else:
            cases = _parse_json_objects(source, source="inline_json")

        if not cases:
            return {
                "success": True,
                "total": 0,
                "preview_count": 0,
                "cases": [],
                "message": "未找到符合条件的用例",
            }

        invalid = [i for i, c in enumerate(cases) if not isinstance(c, dict)]
        if invalid:
            return {
                "success": False,
                "error": f"用例数据中存在非对象元素（下标 {invalid[:5]}）",
            }

        filtered = [c for c in cases if _matches_filters(c, module, priority, case_type)]
        sampled = filtered[:limit]

        preview_cases: list[dict[str, Any]] = []
        for case in sampled:
            steps = extract_field(case, "test_case_steps", "steps", "测试步骤", "test_steps", default=None)
            test_data = extract_field(case, "test_data", "测试数据", "data", default=None)
            preconditions = extract_field(case, "preconditions", "前置条件", "precondition", default=None)

            preview_cases.append({
                "case_number": extract_field(case, "case_number", "id", "用例编号", "identifier", "case_id", "编号"),
                "name": extract_field(case, "name", "title", "用例标题", "标题", "用例名称"),
                "module": extract_field(case, "module", "所属模块", "module_name", "功能模块"),
                "priority": extract_field(case, "priority", "优先级"),
                "case_type": extract_field(case, "case_type", "type", "用例类型", "测试类型"),
                "preconditions": preconditions if isinstance(preconditions, list) else [preconditions] if preconditions else [],
                "test_case_steps": _truncate_steps(steps),
                "test_data": _truncate_test_data(test_data),
            })

        return {
            "success": True,
            "total": len(filtered),
            "preview_count": len(preview_cases),
            "cases": preview_cases,
            "message": f"共找到 {len(filtered)} 条用例，展示前 {len(preview_cases)} 条",
        }

    except FileNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"文件不存在：{source}",
        }
    except Exception as e:
        logger.exception("preview_test_cases 执行失败: source=%s", source)
        return {
            "success": False,
            "error": str(e),
            "message": f"读取用例预览失败: {str(e)}",
        }
