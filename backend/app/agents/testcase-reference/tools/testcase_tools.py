"""
测试用例管理工具

提供测试用例创建、更新和批量操作的 HTTP 接口调用工具
"""

import asyncio
from typing import Optional, Any
import logging
import httpx
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVhRemFBPT06NTk5ODY5NTM=

from app.config.settings import settings

logger = logging.getLogger(__name__)

# ============ 配置 ============

# API 基础 URL（默认使用本地地址）
API_BASE_URL = "http://localhost:8000"  # 可以从环境变量读取
API_PREFIX = settings.api_prefix  # /api/v2


# ============ 辅助函数 ============

def get_api_url(path: str) -> str:
    """构建完整的 API URL"""
    return f"{API_BASE_URL}{API_PREFIX}{path}"


async def make_http_request(
    method: str,
    url: str,
    json_data: Optional[dict] = None,
    params: Optional[dict] = None,
) -> dict[str, Any]:
    """
    发送 HTTP 请求的通用函数

    Args:
        method: HTTP 方法（GET, POST, PATCH, DELETE）
        url: 完整的 URL
        json_data: JSON 请求体
        params: URL 查询参数

    Returns:
        dict: 响应数据
    """
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
        # HTTP 错误（4xx, 5xx）
        error_detail = e.response.text
        try:
            error_json = e.response.json()
            error_detail = error_json.get("detail", error_detail)
        except Exception:
            pass
        raise Exception(f"HTTP {e.response.status_code}: {error_detail}")
    except httpx.RequestError as e:
        # 网络错误
        raise Exception(f"网络请求失败: {str(e)}")
    except Exception as e:
        # 其他错误
        raise Exception(f"请求失败: {str(e)}")

# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVhRemFBPT06NTk5ODY5NTM=

# ============ 工具函数 ============

async def create_test_case_tool(
    project_identifier: str,
    folder_id: str,
    name: str,
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
) -> dict[str, Any]:
    """
    创建测试用例工具（通过 HTTP 接口调用）

    该工具通过调用测试用例创建 HTTP 接口来创建新的测试用例。
    支持普通测试用例和 BDD 测试用例两种模板。

    Args:
        project_identifier: 项目标识符，如 'PROJ-001'
        folder_id: 文件夹 UUID
        name: 测试用例名称（必填）
        description: 测试用例描述（可选，支持 HTML）
        preconditions: 前置条件（可选，支持 HTML）
        priority: 优先级，可选值：critical, high, medium, low（默认 medium）
        status: 状态，可选值：
                - 设计阶段：new（新建）、review_pending（待评审）、reviewed（已评审）
                - 执行阶段：not_run（未执行）、passed（通过）、failed（失败）、blocked（阻塞）、skipped（跳过）
                默认 new
        case_type: 测试类型，可选值：functional, regression, smoke_sanity, acceptance,
                   performance, security, usability, compatibility, accessibility,
                   destructive, other（默认 functional）
        owner: 负责人邮箱（可选）
        tags: 标签列表（可选）
        issues: 关联的 Jira issues（可选）
        automation_status: 自动化状态，可选值：not_automated, automated, in_progress,
                          obsolete（默认 not_automated）
        custom_fields: 自定义字段（可选）
        template: 模板类型，可选值：test_case（普通）, test_case_bdd（BDD）（默认 test_case）
        test_case_steps: 测试步骤列表（普通测试用例使用），每个步骤包含：
                        - step: 操作步骤描述（必填）
                        - result: 预期结果（可选）
        feature: BDD Feature 描述（BDD 测试用例必填）
        scenario: BDD Scenario 描述（BDD 测试用例必填）
        background: BDD Background 描述（BDD 测试用例可选）

    Returns:
        dict: 包含创建结果的字典
            - success: 是否成功
            - data: 创建的测试用例信息（如果成功）
            - error: 错误信息（如果失败）

    Examples:
        # 创建普通测试用例
        result = await create_test_case_tool(
            project_identifier="PROJ-001",
            folder_id="123e4567-e89b-12d3-a456-426614174000",
            name="用户登录功能测试",
            description="验证用户登录功能是否正常",
            priority="high",
            status="new",
            case_type="functional",
            test_case_steps=[
                {"step": "打开登录页面", "result": "页面正常显示"},
                {"step": "输入用户名和密码", "result": "输入框接受输入"},
                {"step": "点击登录按钮", "result": "成功登录并跳转到首页"}
            ],
            tags=["登录", "核心功能"]
        )

        # 创建 BDD 测试用例
        result = await create_test_case_tool(
            project_identifier="PROJ-001",
            folder_id="123e4567-e89b-12d3-a456-426614174000",
            name="用户登录场景",
            template="test_case_bdd",
            feature="用户认证",
            scenario="用户使用正确的凭据登录",
            background="Given 用户已注册"
        )
    """
    try:
        # 构建请求数据
        request_data: dict[str, Any] = {
            "name": name,
            "template": template,
            "priority": priority,
            "status": status,
            "case_type": case_type,
            "automation_status": automation_status,
        }

        # 添加可选字段
        if description is not None:
            request_data["description"] = description
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

        # 根据模板类型添加相应字段
        if template == "test_case_bdd":
            # BDD 测试用例
            if feature is not None:
                request_data["feature"] = feature
            if scenario is not None:
                request_data["scenario"] = scenario
            if background is not None:
                request_data["background"] = background
        else:
            # 普通测试用例
            if test_case_steps is not None:
                request_data["test_case_steps"] = test_case_steps

        # 构建 API URL（需要包含 project_identifier 路径参数）
        url = get_api_url(f"/projects/{project_identifier}/folders/{folder_id}/test-cases")

        # 不需要查询参数，project_identifier 已经在路径中
        params = None

        # 发送 HTTP POST 请求
        response_data = await make_http_request(
            method="POST",
            url=url,
            json_data=request_data,
            params=params,
        )

        # 提取响应数据
        if response_data.get("success"):
            test_case_data = response_data.get("data", {})
            return {
                "success": True,
                "data": test_case_data,
                "message": f"测试用例 {test_case_data.get('identifier', '')} 创建成功"
            }
        else:
            return {
                "success": False,
                "error": "API 返回失败",
                "message": "创建测试用例失败"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"创建测试用例失败: {str(e)}"
        }


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
) -> dict[str, Any]:
    """
    更新测试用例工具（通过 HTTP 接口调用）

    该工具通过调用测试用例更新 HTTP 接口来更新现有测试用例的信息。
    所有字段都是可选的，只更新提供的字段。

    Args:
        project_identifier: 项目标识符，如 'PROJ-001'
        test_case_identifier: 测试用例标识符，如 'TC-1234'
        name: 测试用例名称
        description: 测试用例描述
        preconditions: 前置条件
        priority: 优先级（critical, high, medium, low）
        status: 状态
              设计阶段：new（新建）、review_pending（待评审）、reviewed（已评审）
              执行阶段：not_run（未执行）、passed（通过）、failed（失败）、blocked（阻塞）、skipped（跳过）
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

    Returns:
        dict: 包含更新结果的字典
            - success: 是否成功
            - data: 更新后的测试用例信息（如果成功）
            - error: 错误信息（如果失败）

    Examples:
        # 更新测试用例的优先级和状态
        result = await update_test_case_tool(
            project_identifier="PROJ-001",
            test_case_identifier="TC-1234",
            priority="critical",
            status="reviewed"
        )

        # 更新测试步骤
        result = await update_test_case_tool(
            project_identifier="PROJ-001",
            test_case_identifier="TC-1234",
            test_case_steps=[
                {"step": "新步骤1", "result": "预期结果1"},
                {"step": "新步骤2", "result": "预期结果2"}
            ]
        )

        # 移动测试用例到另一个文件夹
        result = await update_test_case_tool(
            project_identifier="PROJ-001",
            test_case_identifier="TC-1234",
            folder_id="456e7890-e89b-12d3-a456-426614174000"
        )
    """
    try:
        # 构建更新数据（只包含提供的字段）
        request_data: dict[str, Any] = {}

        if name is not None:
            request_data["name"] = name
        if description is not None:
            request_data["description"] = description
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

        # 如果没有任何字段需要更新，返回错误
        if not request_data:
            return {
                "success": False,
                "error": "没有提供任何需要更新的字段",
                "message": "更新测试用例失败：没有提供任何需要更新的字段"
            }

        # 构建 API URL（需要包含 project_identifier 路径参数）
        url = get_api_url(f"/projects/{project_identifier}/test-cases/{test_case_identifier}")

        # 不需要查询参数，project_identifier 已经在路径中
        params = None

        # 发送 HTTP PATCH 请求
        response_data = await make_http_request(
            method="PATCH",
            url=url,
            json_data=request_data,
            params=params,
        )
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVhRemFBPT06NTk5ODY5NTM=

        # 提取响应数据
        if response_data.get("success"):
            test_case_data = response_data.get("data", {})
            return {
                "success": True,
                "data": test_case_data,
                "message": f"测试用例 {test_case_data.get('identifier', '')} 更新成功"
            }
        else:
            return {
                "success": False,
                "error": "API 返回失败",
                "message": "更新测试用例失败"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"更新测试用例失败: {str(e)}"
        }


async def batch_create_test_cases_tool(
    project_identifier: str,
    folder_id: str,
    test_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    批量创建测试用例工具（通过 HTTP 接口调用）

    该工具可以一次性创建多个测试用例，提高效率。
    每个测试用例的参数与 create_test_case_tool 相同。

    Args:
        project_identifier: 项目标识符，如 'PROJ-001'
        folder_id: 文件夹 UUID
        test_cases: 测试用例列表，每个元素是一个包含测试用例信息的字典，包含以下字段：
            - name: 测试用例名称（必填）
            - description: 测试用例描述（可选）
            - preconditions: 前置条件（可选）
            - priority: 优先级（可选，默认 medium）
            - status: 状态（可选，默认 new）
              设计阶段：new（新建）、review_pending（待评审）、reviewed（已评审）
              执行阶段：not_run（未执行）、passed（通过）、failed（失败）、blocked（阻塞）、skipped（跳过）
            - case_type: 测试类型（可选，默认 functional）
            - owner: 负责人邮箱（可选）
            - tags: 标签列表（可选）
            - issues: 关联的 Jira issues（可选）
            - automation_status: 自动化状态（可选，默认 not_automated）
            - custom_fields: 自定义字段（可选）
            - template: 模板类型（可选，默认 test_case）
            - test_case_steps: 测试步骤列表（可选）
            - feature: BDD Feature 描述（可选）
            - scenario: BDD Scenario 描述（可选）
            - background: BDD Background 描述（可选）

    Returns:
        dict: 包含批量创建结果的字典
            - success: 是否成功
            - data: 包含成功和失败的统计信息
                - total: 总数
                - succeeded: 成功数量
                - failed: 失败数量
                - results: 每个测试用例的创建结果列表
            - error: 错误信息（如果失败）

    Examples:
        # 批量创建多个测试用例
        result = await batch_create_test_cases_tool(
            project_identifier="PROJ-001",
            folder_id="123e4567-e89b-12d3-a456-426614174000",
            test_cases=[
                {
                    "name": "测试用例1",
                    "description": "描述1",
                    "priority": "high",
                    "test_case_steps": [
                        {"step": "步骤1", "result": "结果1"}
                    ]
                },
                {
                    "name": "测试用例2",
                    "description": "描述2",
                    "priority": "medium",
                    "test_case_steps": [
                        {"step": "步骤1", "result": "结果1"}
                    ]
                },
                {
                    "name": "BDD 测试用例",
                    "template": "test_case_bdd",
                    "feature": "用户登录",
                    "scenario": "成功登录"
                }
            ]
        )
    """
    try:
        if not test_cases:
            return {
                "success": False,
                "error": "测试用例列表为空",
                "message": "批量创建失败：测试用例列表为空"
            }

        results = []
        succeeded = 0
        failed = 0
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVhRemFBPT06NTk5ODY5NTM=

        # 逐个创建测试用例
        for index, test_case_data in enumerate(test_cases):
            try:
                # 提取测试用例参数
                name = test_case_data.get("name")
                if not name:
                    results.append({
                        "index": index,
                        "success": False,
                        "error": "测试用例名称不能为空",
                        "data": test_case_data
                    })
                    failed += 1
                    continue

                # 调用单个创建工具
                result = await create_test_case_tool(
                    project_identifier=project_identifier,
                    folder_id=folder_id,
                    name=name,
                    description=test_case_data.get("description"),
                    preconditions=test_case_data.get("preconditions"),
                    priority=test_case_data.get("priority", "medium"),
                    status=test_case_data.get("status", "new"),
                    case_type=test_case_data.get("case_type", "functional"),
                    owner=test_case_data.get("owner"),
                    tags=test_case_data.get("tags"),
                    issues=test_case_data.get("issues"),
                    automation_status=test_case_data.get("automation_status", "not_automated"),
                    custom_fields=test_case_data.get("custom_fields"),
                    template=test_case_data.get("template", "test_case"),
                    test_case_steps=test_case_data.get("test_case_steps"),
                    feature=test_case_data.get("feature"),
                    scenario=test_case_data.get("scenario"),
                    background=test_case_data.get("background"),
                )

                results.append({
                    "index": index,
                    "success": result.get("success", False),
                    "data": result.get("data"),
                    "error": result.get("error"),
                    "message": result.get("message")
                })

                if result.get("success"):
                    succeeded += 1
                else:
                    failed += 1

            except Exception as e:
                results.append({
                    "index": index,
                    "success": False,
                    "error": str(e),
                    "data": test_case_data
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

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"批量创建测试用例失败: {str(e)}"
        }
