"""
API 验证层主动探测执行器

基于 probe_rule_engine 生成的探测用例，向测试环境发送请求，
从 4xx/5xx 响应中提取业务语义并沉淀到 api_annotations。
"""

import asyncio
import copy
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_annotation import APIAnnotation
from app.models.api_endpoint import APIEndpoint
from app.models.environment import ProjectEnvironment
from app.repositories.api_annotation_repo import APIAnnotationRepository
from app.repositories.environment_repo import EnvironmentRepository
from app.services.environment_service import EnvironmentService
from app.services.probe_rule_engine import generate_probe_requests
from app.utils.exceptions import BadRequestException

logger = logging.getLogger(__name__)


# 环境名安全过滤
_PROBE_ENV_ALLOWLIST = {
    "dev", "test", "testing", "staging", "uat", "sit", "local", "development",
    # 中文常见测试环境名
    "测试", "开发", "预发", "验收", "本地", "sit", "uat",
}
_PROBE_ENV_BLOCKLIST = {
    "prod", "production", "live", "prd", "master",
    # 中文常见生产环境名
    "生产", "线上", "正式",
}

# 单端点/项目级探测上限
_MAX_PROBE_BUDGET = 50
_DEFAULT_PROBE_BUDGET = 20
_DEFAULT_CONCURRENCY = 1
_MAX_CONCURRENCY = 3

# 业务码字段（与 annotation_service 保持一致）
_BUSINESS_CODE_FIELDS = (
    "code",
    "errorCode",
    "error_code",
    "errCode",
    "err_code",
    "status",
    "retCode",
    "ret_code",
    "bizCode",
    "biz_code",
)
_MESSAGE_FIELDS = (
    "message",
    "msg",
    "error",
    "errorMessage",
    "error_message",
    "errMsg",
    "err_msg",
    "detail",
    "description",
)
_BUSINESS_SUCCESS_CODES = {0, "0", 200, "200", "2000", "success", "SUCCESS", True, "true", "ok", "OK"}


class ProbeExecutor:
    """主动探测执行器"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.env_service = EnvironmentService(session)
        self.repo = APIAnnotationRepository(session)

    # ------------------------------------------------------------------
    # 安全与环境
    # ------------------------------------------------------------------
    @staticmethod
    def is_safe_environment(env_name: str) -> bool:
        """检查环境名是否允许执行主动探测"""
        name_lower = env_name.lower()
        # 命中 blocklist 的直接拒绝
        for block in _PROBE_ENV_BLOCKLIST:
            if block in name_lower:
                return False
        # 必须命中 allowlist
        for allow in _PROBE_ENV_ALLOWLIST:
            if allow in name_lower:
                return True
        return False

    async def _get_environment(self, project_identifier: str, env_id: Optional[str]) -> ProjectEnvironment:
        """获取要探测的环境，默认取项目默认环境"""
        project_id = await self.env_service._get_project_id(project_identifier)
        env_repo = EnvironmentRepository(self.session)

        if env_id:
            env = await env_repo.get_by_id(UUID(str(env_id)))
            if not env or env.project_id != project_id:
                raise BadRequestException("指定的 env_id 不存在或不属于该项目")
            return env

        env = await env_repo.get_default_by_project(project_id)
        if not env:
            raise BadRequestException("项目未配置默认环境，请显式传入 env_id")
        return env

    async def _resolve_env_vars(
        self,
        project_identifier: str,
        endpoint_id: UUID,
        env_id: Optional[str],
    ) -> dict[str, str]:
        """解析 base_url 与认证头等执行环境变量"""
        env_vars = await self.env_service.get_execution_env_vars(
            project_identifier=project_identifier,
            endpoint_id=endpoint_id,
            env_id=env_id,
        )
        return env_vars

    @staticmethod
    def _extract_auth_headers(env_vars: dict[str, str]) -> dict[str, str]:
        """从环境变量中提取认证相关 header"""
        auth_keys = ["Authorization", "AUTH_TOKEN", "X-API-Key", "api_key", "apiKey"]
        headers: dict[str, str] = {}
        for key in auth_keys:
            if key in env_vars:
                headers[key] = env_vars[key]
        # 兜底：把 Authorization 设为 Bearer AUTH_TOKEN
        if "Authorization" not in headers and "AUTH_TOKEN" in env_vars:
            headers["Authorization"] = f"Bearer {env_vars['AUTH_TOKEN']}"
        return headers

    # ------------------------------------------------------------------
    # 探测入口
    # ------------------------------------------------------------------
    async def probe_endpoint(
        self,
        project_identifier: str,
        endpoint_id: str,
        env_id: Optional[str] = None,
        probe_budget: int = _DEFAULT_PROBE_BUDGET,
        concurrency: int = _DEFAULT_CONCURRENCY,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """对单个端点执行主动验证层探测。

        Args:
            project_identifier: 项目标识符或 ID
            endpoint_id: 端点 ID
            env_id: 环境 ID（默认项目默认环境）
            probe_budget: 最大探测数（默认 20，最大 50）
            concurrency: 并发数（默认 1，最大 3）
            dry_run: 为 True 时只返回将要发送的请求，不实际执行

        Returns:
            执行结果摘要
        """
        # 1. 参数校验
        probe_budget = min(max(probe_budget, 1), _MAX_PROBE_BUDGET)
        concurrency = min(max(concurrency, 1), _MAX_CONCURRENCY)

        # 2. 加载端点
        ep_id = UUID(str(endpoint_id))
        endpoint = await self.session.get(APIEndpoint, ep_id)
        if not endpoint:
            raise BadRequestException(f"端点 {endpoint_id} 不存在")

        # 3. 环境安全检查
        env = await self._get_environment(project_identifier, env_id)
        if not self.is_safe_environment(env.name):
            raise BadRequestException(
                f"环境 '{env.name}' 不在主动探测允许列表中，"
                f"仅允许：{_PROBE_ENV_ALLOWLIST}；禁止：{_PROBE_ENV_BLOCKLIST}"
            )

        # 4. 解析环境变量
        env_vars = await self._resolve_env_vars(project_identifier, ep_id, env_id)
        base_url = env_vars.get("API_BASE_URL")
        if not base_url:
            raise BadRequestException("未配置 API_BASE_URL，无法执行探测")
        auth_headers = self._extract_auth_headers(env_vars)

        # 5. 生成探测请求
        parameters = endpoint.parameters or []
        request_body = endpoint.request_body or None
        # 兼容旧格式：parameters 中 in: body 的项合并为 request_body
        request_body = self._merge_legacy_body_params(parameters, request_body)

        probes = generate_probe_requests(
            endpoint_path=endpoint.path,
            method=endpoint.method,
            parameters=parameters,
            request_body=request_body,
            budget=probe_budget,
        )

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "endpoint_id": str(ep_id),
                "environment": env.name,
                "base_url": base_url,
                "probe_count": len(probes),
                "probes": probes,
            }

        # 6. 执行探测
        results = await self._execute_probes(
            endpoint=endpoint,
            base_url=base_url,
            auth_headers=auth_headers,
            probes=probes,
            concurrency=concurrency,
        )

        # 7. 沉淀标注
        harvested = await self._persist_probe_results(
            project_id=endpoint.project_id,
            endpoint_id=ep_id,
            results=results,
        )

        return {
            "success": True,
            "dry_run": False,
            "endpoint_id": str(ep_id),
            "environment": env.name,
            "base_url": base_url,
            "probe_count": len(probes),
            "executed": len(results),
            "harvested": len(harvested),
            "annotations": [self._annotation_summary(a) for a in harvested],
            "results": [
                {
                    "name": r["probe"]["name"],
                    "field_path": r["probe"]["field_path"],
                    "condition": r["probe"]["condition"],
                    "status": r["status"],
                    "business_code": r.get("business_code"),
                    "message": r.get("message"),
                }
                for r in results
            ],
        }

    # ------------------------------------------------------------------
    # 请求执行
    # ------------------------------------------------------------------
    async def _execute_probes(
        self,
        endpoint: APIEndpoint,
        base_url: str,
        auth_headers: dict[str, str],
        probes: list[dict],
        concurrency: int,
    ) -> list[dict]:
        """并发执行探测请求"""
        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(probe: dict) -> dict:
            async with semaphore:
                return await self._send_single_probe(endpoint, base_url, auth_headers, probe)

        tasks = [run_one(p) for p in probes]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_single_probe(
        self,
        endpoint: APIEndpoint,
        base_url: str,
        auth_headers: dict[str, str],
        probe: dict,
    ) -> dict:
        """发送单个探测请求并解析响应"""
        req_data = probe.get("request_data", {})
        path_params = self._ensure_dict(req_data.get("path"))
        query_params = self._ensure_dict(req_data.get("query"))
        headers = self._ensure_dict(req_data.get("header"))
        body = req_data.get("body")

        # 合并认证头（探测头优先级更高，但通常不会覆盖认证）
        for key, value in auth_headers.items():
            if key not in headers:
                headers[key] = value

        # 构造 URL 并替换路径参数
        url = base_url.rstrip("/") + "/" + endpoint.path.lstrip("/")
        url = self._fill_path_params(url, path_params)

        method = endpoint.method.upper()
        timeout = 30.0

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=query_params,
                    json=body if body is not None else None,
                )
        except httpx.TimeoutException:
            return {
                "probe": probe,
                "status": 0,
                "body": None,
                "error": "timeout",
                "business_code": None,
                "message": None,
            }
        except Exception as e:
            logger.warning("探测请求异常: %s %s - %s", method, url, e)
            return {
                "probe": probe,
                "status": 0,
                "body": None,
                "error": str(e),
                "business_code": None,
                "message": None,
            }

        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            try:
                resp_body = response.json()
            except Exception:
                resp_body = response.text
        else:
            resp_body = response.text

        business_code = self._extract_business_code(resp_body)
        message = self._extract_message(resp_body)

        return {
            "probe": probe,
            "status": response.status_code,
            "body": resp_body,
            "error": None,
            "business_code": business_code,
            "message": message,
        }

    # ------------------------------------------------------------------
    # 标注沉淀
    # ------------------------------------------------------------------
    async def _persist_probe_results(
        self,
        project_id: UUID,
        endpoint_id: UUID,
        results: list[dict],
    ) -> list[APIAnnotation]:
        """把探测结果转换为 annotation 并持久化"""
        harvested: list[APIAnnotation] = []
        for result in results:
            if isinstance(result, Exception):
                continue
            probe = result.get("probe", {})
            status = result.get("status")
            business_code = result.get("business_code")
            message = result.get("message")
            field_path = probe.get("field_path")
            condition = probe.get("condition")

            # 只沉淀 4xx/5xx 或非业务成功响应
            if not self._is_interesting_result(status, business_code):
                continue

            ann_type = "business_error_code"
            if field_path and condition:
                ann_type = "field_validation"

            existing = await self._find_existing_annotation(
                project_id=project_id,
                endpoint_id=endpoint_id,
                annotation_type=ann_type,
                http_status=status,
                business_code=business_code,
                field_path=field_path,
                condition=condition,
            )

            now = datetime.now(timezone.utc)
            if existing:
                existing.hit_count += 1
                existing.confidence = min(existing.confidence + 0.1, 0.95)
                existing.last_seen_at = now
                existing.last_verified_at = now
                existing.enabled = True
                if message:
                    existing.message_pattern = message
                harvested.append(existing)
            else:
                ann = await self.repo.create(
                    project_id=project_id,
                    endpoint_id=endpoint_id,
                    annotation_type=ann_type,
                    source="probe",
                    http_status=status if isinstance(status, int) else None,
                    business_code=business_code,
                    field_path=field_path,
                    condition=condition,
                    message_pattern=message,
                    confidence=0.5,
                    source_metadata={
                        "probe_name": probe.get("name"),
                        "probe_condition": condition,
                        "probed_at": now.isoformat(),
                    },
                )
                harvested.append(ann)

        await self.session.flush()
        return harvested

    async def _find_existing_annotation(
        self,
        project_id: UUID,
        endpoint_id: UUID,
        annotation_type: str,
        http_status: Optional[int],
        business_code: Optional[str],
        field_path: Optional[str],
        condition: Optional[str],
    ) -> Optional[APIAnnotation]:
        """按自然键查找已有标注"""
        stmt = select(APIAnnotation).where(
            APIAnnotation.project_id == project_id,
            APIAnnotation.endpoint_id == endpoint_id,
            APIAnnotation.annotation_type == annotation_type,
            APIAnnotation.http_status == http_status,
            APIAnnotation.business_code == business_code,
            APIAnnotation.field_path == field_path,
            APIAnnotation.condition == condition,
            APIAnnotation.source != "manual",
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # 小工具
    # ------------------------------------------------------------------
    @staticmethod
    def _merge_legacy_body_params(parameters: list, request_body: Optional[dict]) -> Optional[dict]:
        """兼容旧格式：parameters 中 in: body 的项合并为 request_body"""
        if not isinstance(parameters, list):
            return request_body

        body_params = [p for p in parameters if isinstance(p, dict) and p.get("in") == "body"]
        if not body_params:
            return request_body

        # 取第一个 body 参数的 schema
        schema = body_params[0].get("schema", {})
        if not isinstance(schema, dict):
            return request_body

        merged = dict(request_body) if isinstance(request_body, dict) else {}
        merged["content"] = merged.get("content") or {
            "application/json": {"schema": schema}
        }
        if body_params[0].get("required"):
            merged["required"] = True
        return merged

    @staticmethod
    def _fill_path_params(url: str, path_params: dict) -> str:
        for key, value in path_params.items():
            placeholder = f"{{{key}}}"
            url = url.replace(placeholder, str(value))
        return url

    @staticmethod
    def _ensure_dict(value: Any) -> dict:
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _extract_business_code(body: Any) -> Optional[str]:
        if not isinstance(body, dict):
            return None
        for key in _BUSINESS_CODE_FIELDS:
            if key in body and body[key] is not None:
                return str(body[key])
        return None

    @staticmethod
    def _extract_message(body: Any) -> Optional[str]:
        if not isinstance(body, dict):
            return None
        for key in _MESSAGE_FIELDS:
            if key in body and body[key] is not None:
                value = body[key]
                if isinstance(value, str):
                    return value
                if isinstance(value, list) and value and isinstance(value[0], str):
                    return value[0]
        return None

    @staticmethod
    def _is_interesting_result(status: Optional[int], business_code: Optional[str]) -> bool:
        """判断响应是否值得沉淀：4xx/5xx 或非业务成功码"""
        if isinstance(status, int) and (400 <= status < 600):
            return True
        if business_code is not None and business_code not in _BUSINESS_SUCCESS_CODES:
            return True
        return False

    @staticmethod
    def _annotation_summary(ann: APIAnnotation) -> dict[str, Any]:
        return {
            "id": str(ann.id),
            "annotation_type": ann.annotation_type,
            "http_status": ann.http_status,
            "business_code": ann.business_code,
            "field_path": ann.field_path,
            "condition": ann.condition,
            "message_pattern": ann.message_pattern,
        }
