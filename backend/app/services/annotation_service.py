"""
API 业务语义标注提取服务

从 APITestResult 的请求/响应中自动沉淀业务码、字段级约束等标注。
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_annotation import APIAnnotation
from app.models.api_endpoint import APIEndpoint
from app.models.api_test import APITest, APITestResult
from app.repositories.api_annotation_repo import APIAnnotationRepository


# 常见业务码字段名
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

# 常见消息字段名
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

# 业务成功码白名单
_BUSINESS_SUCCESS_CODES = {0, "0", 200, "200", "success", "SUCCESS", True, "true", "ok", "OK"}

# 字段级错误常见容器
_FIELD_ERROR_CONTAINERS = (
    "errors",
    "error_details",
    "details",
    "fieldErrors",
    "field_errors",
    "violations",
    "validationErrors",
    "validation_errors",
)

# 字段级错误项常见字段
_FIELD_ERROR_FIELD_KEYS = ("field", "fieldName", "field_name", "property", "path", "parameter")
_FIELD_ERROR_CODE_KEYS = ("code", "errorCode", "error_code", "errCode", "err_code")
_FIELD_ERROR_MSG_KEYS = ("message", "msg", "error", "errorMessage", "error_message")


class AnnotationExtractor:
    """从单个 API 测试结果中提取标注"""

    def __init__(self, endpoint_map: dict[tuple[str, str], UUID]):
        """
        Args:
            endpoint_map: {(path_upper, method_upper): endpoint_id}
        """
        self.endpoint_map = endpoint_map

    def extract(self, result: APITestResult) -> list[dict[str, Any]]:
        """从单个测试结果中提取候选标注"""
        annotations: list[dict[str, Any]] = []

        endpoint_id = self._resolve_endpoint_id(result.endpoint, result.method)
        if endpoint_id is None:
            return annotations

        response_data = result.response_data or {}
        request_data = result.request_data or {}
        status = response_data.get("status") or response_data.get("status_code")
        body = response_data.get("body")
        if isinstance(body, str):
            body = None  # 暂不解析字符串 body

        # 1. 业务级成功/错误码
        business_code = self._extract_business_code(body)
        message = self._extract_message(body)

        if status is not None and business_code is not None:
            if self._is_success_code(business_code) and 200 <= int(status) < 300:
                annotations.append({
                    "annotation_type": "business_success_code",
                    "http_status": int(status),
                    "business_code": str(business_code),
                    "message_pattern": message,
                    "expected_value": {"code": business_code},
                })
            else:
                annotations.append({
                    "annotation_type": "business_error_code",
                    "http_status": int(status) if isinstance(status, int) else None,
                    "business_code": str(business_code),
                    "message_pattern": message,
                })

        # 2. 字段级错误
        field_errors = self._extract_field_errors(body)
        for field_err in field_errors:
            field_path = field_err.get("field")
            field_code = field_err.get("code") or business_code
            field_msg = field_err.get("message") or message
            condition = self._infer_condition(field_msg, field_path, request_data)

            annotations.append({
                "annotation_type": "field_validation",
                "http_status": int(status) if isinstance(status, int) else None,
                "business_code": str(field_code) if field_code else None,
                "field_path": f"body.{field_path}" if field_path and not field_path.startswith(("body.", "query.", "path.", "header.")) else field_path,
                "condition": condition,
                "message_pattern": field_msg,
            })

        # 3. 枚举含义：从成功响应的枚举字段推断（较保守，只取 status/state 类字段）
        if 200 <= int(status) < 300 if isinstance(status, int) else False:
            enum_annotations = self._extract_enum_meanings(body, endpoint_id)
            annotations.extend(enum_annotations)

        # 补充公共字段
        for ann in annotations:
            ann["endpoint_id"] = endpoint_id
            ann["source_metadata"] = {
                "test_result_id": str(result.id),
                "test_run_id": str(result.test_run_id),
                "api_test_id": str(result.api_test_id),
                "scenario_name": result.scenario_name,
            }

        return annotations

    def _resolve_endpoint_id(self, endpoint_str: str, method: str) -> Optional[UUID]:
        """把 APITestResult 的 endpoint + method 解析为 endpoint_id"""
        if not endpoint_str or not method:
            return None
        key = (endpoint_str.strip().upper(), method.strip().upper())
        return self.endpoint_map.get(key)

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
    def _extract_field_errors(body: Any) -> list[dict[str, Any]]:
        """从响应体中提取字段级错误列表"""
        if not isinstance(body, dict):
            return []

        candidates: list[Any] = []
        for key in _FIELD_ERROR_CONTAINERS:
            if key in body and isinstance(body[key], list):
                candidates.extend(body[key])
                break

        results = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            field = None
            for fk in _FIELD_ERROR_FIELD_KEYS:
                if fk in item and item[fk] is not None:
                    field = str(item[fk])
                    break
            code = None
            for ck in _FIELD_ERROR_CODE_KEYS:
                if ck in item and item[ck] is not None:
                    code = str(item[ck])
                    break
            msg = None
            for mk in _FIELD_ERROR_MSG_KEYS:
                if mk in item and item[mk] is not None:
                    msg = str(item[mk])
                    break
            if field or code or msg:
                results.append({"field": field, "code": code, "message": msg})

        return results

    @staticmethod
    def _is_success_code(code: Any) -> bool:
        return code in _BUSINESS_SUCCESS_CODES

    @staticmethod
    def _infer_condition(
        message: Optional[str],
        field_path: Optional[str],
        request_data: dict[str, Any],
    ) -> Optional[str]:
        """根据错误消息和请求数据推断约束条件"""
        msg = (message or "").lower()

        if "required" in msg or "missing" in msg or "must not be null" in msg or "cannot be null" in msg:
            return "required_missing"
        if "invalid enum" in msg or "not a valid choice" in msg or "enum" in msg:
            return "invalid_enum"
        if "type" in msg or "must be a" in msg or "invalid type" in msg:
            return "type_error"
        if "format" in msg or "invalid format" in msg or "must match format" in msg:
            return "format_error"
        if "length" in msg or "too long" in msg or "too short" in msg or "max length" in msg or "min length" in msg:
            return "length_error"
        if "range" in msg or "out of range" in msg or "too large" in msg or "too small" in msg or "minimum" in msg or "maximum" in msg:
            return "out_of_range"
        if "pattern" in msg or "regex" in msg or "must match" in msg:
            return "pattern_mismatch"

        # 兜底：如果请求里该字段缺失，推断为 required_missing
        if field_path:
            body = request_data.get("body") or {}
            field_name = field_path.split(".")[-1] if "." in field_path else field_path
            if field_name and field_name not in body:
                return "required_missing"

        return None

    @staticmethod
    def _extract_enum_meanings(body: Any, endpoint_id: UUID) -> list[dict[str, Any]]:
        """保守地从成功响应中提取枚举字段含义"""
        if not isinstance(body, dict):
            return []

        enum_fields = ("status", "state", "type", "orderStatus", "paymentStatus")
        annotations = []
        for field in enum_fields:
            if field in body and body[field] is not None:
                value = body[field]
                if isinstance(value, (str, int)):
                    annotations.append({
                        "annotation_type": "enum_meaning",
                        "field_path": f"body.{field}",
                        "expected_value": {"value": value},
                        "message_pattern": f"响应中 {field} 字段的示例值",
                    })
        return annotations


class AnnotationService:
    """标注库服务：harvest + query"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = APIAnnotationRepository(session)

    async def harvest_from_test_results(
        self,
        project_id: UUID,
        endpoint_id: Optional[UUID] = None,
        since: Optional[datetime] = None,
        max_results: int = 200,
    ) -> dict[str, Any]:
        """
        扫描 APITestResult 提取标注并写入 api_annotations。

        Args:
            project_id: 项目 ID
            endpoint_id: 可选，只扫描指定端点
            since: 可选，只扫描该时间之后的结果
            max_results: 最大扫描结果数

        Returns:
            {"success": bool, "harvested": int, "new": int, "updated": int, "by_endpoint": dict}
        """
        # 1. 加载端点映射
        endpoint_map = await self._build_endpoint_map(project_id)

        # 2. 查询测试结果
        stmt = (
            select(APITestResult)
            .join(APITest, APITestResult.api_test_id == APITest.id)
            .where(APITest.project_id == project_id)
        )
        if since is not None:
            stmt = stmt.where(APITestResult.created_at >= since)
        if endpoint_id is not None:
            endpoint = await self.session.get(APIEndpoint, endpoint_id)
            if endpoint:
                stmt = stmt.where(
                    APITestResult.endpoint == endpoint.path,
                    APITestResult.method == endpoint.method,
                )

        stmt = stmt.order_by(APITestResult.created_at.desc()).limit(max_results)
        result = await self.session.execute(stmt)
        test_results = list(result.scalars().all())

        extractor = AnnotationExtractor(endpoint_map)

        new_count = 0
        updated_count = 0
        by_endpoint: dict[str, dict[str, int]] = {}

        # 3. 提取并 upsert
        for test_result in test_results:
            candidates = extractor.extract(test_result)
            for candidate in candidates:
                ep_id = candidate.pop("endpoint_id", None)
                ann_type = candidate["annotation_type"]

                existing = await self._find_existing(ep_id, ann_type, candidate)
                if existing:
                    await self._update_existing(existing, candidate)
                    updated_count += 1
                else:
                    await self.repo.create(
                        project_id=project_id,
                        endpoint_id=ep_id,
                        **candidate,
                    )
                    new_count += 1

                ep_key = str(ep_id) if ep_id else "__project__"
                by_endpoint.setdefault(ep_key, {"new": 0, "updated": 0})
                if existing:
                    by_endpoint[ep_key]["updated"] += 1
                else:
                    by_endpoint[ep_key]["new"] += 1

        await self.session.flush()

        return {
            "success": True,
            "harvested": new_count + updated_count,
            "new": new_count,
            "updated": updated_count,
            "scanned": len(test_results),
            "by_endpoint": by_endpoint,
        }

    async def list_for_endpoint(
        self,
        project_id: UUID,
        endpoint_id: UUID,
        annotation_type: Optional[str] = None,
        include_disabled: bool = False,
    ) -> list[APIAnnotation]:
        """查询端点标注"""
        return await self.repo.list_for_endpoint(
            project_id=project_id,
            endpoint_id=endpoint_id,
            annotation_type=annotation_type,
            include_disabled=include_disabled,
        )

    async def _build_endpoint_map(self, project_id: UUID) -> dict[tuple[str, str], UUID]:
        """构建 (path_upper, method_upper) -> endpoint_id 映射"""
        stmt = select(APIEndpoint.id, APIEndpoint.path, APIEndpoint.method).where(
            APIEndpoint.project_id == project_id
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return {
            (row.path.strip().upper(), row.method.strip().upper()): row.id
            for row in rows
        }

    async def _find_existing(
        self,
        endpoint_id: Optional[UUID],
        annotation_type: str,
        candidate: dict[str, Any],
    ) -> Optional[APIAnnotation]:
        """按自然键查找已有标注（不含 manual）"""
        stmt = select(APIAnnotation).where(
            APIAnnotation.endpoint_id == endpoint_id,
            APIAnnotation.annotation_type == annotation_type,
            APIAnnotation.http_status == candidate.get("http_status"),
            APIAnnotation.business_code == candidate.get("business_code"),
            APIAnnotation.field_path == candidate.get("field_path"),
            APIAnnotation.condition == candidate.get("condition"),
            APIAnnotation.source != "manual",
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _update_existing(
        self,
        existing: APIAnnotation,
        candidate: dict[str, Any],
    ) -> None:
        """更新已有标注（命中次数、置信度、时间戳）"""
        existing.hit_count += 1
        existing.confidence = min(existing.confidence + 0.1, 0.95)
        existing.last_seen_at = datetime.now(timezone.utc)
        existing.enabled = True

        if candidate.get("message_pattern"):
            existing.message_pattern = candidate["message_pattern"]
        if candidate.get("expected_value"):
            existing.expected_value = candidate["expected_value"]

        old_meta = existing.source_metadata or {}
        new_meta = candidate.get("source_metadata") or {}
        old_meta.update(new_meta)
        existing.source_metadata = old_meta

        await self.session.flush()
