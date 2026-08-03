"""Tests for 本轮 agent 优化项：

- 图片粘性修复：dynamic_model_selection 窗口化检测 + 旧图片剥离
- 预览截断：_extract_preview 限制 interrupt payload 体积
- write_todos 自动化：_advance_phase_todos 审批通过自动推进任务状态
- 门禁合并：CaseQualityGateMiddleware 批量创建前校验移交给 ModuleSelfCheckMiddleware
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.testcase.agent import (
    _IMAGE_PLACEHOLDER,
    _IMAGE_RECENT_WINDOW,
    _message_has_image,
    _strip_image_blocks,
    dynamic_model_selection,
)
from app.agents.testcase.case_quality_middleware import CaseQualityGateMiddleware
from app.agents.testcase.phase_review_middleware import (
    _advance_phase_todos,
    _extract_preview,
)


# ═════════════════════════════════════════════════════════════════════════════
# 图片粘性：窗口化检测
# ═════════════════════════════════════════════════════════════════════════════

def _image_message():
    return HumanMessage(
        content=[
            {"type": "text", "text": "分析这张图"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,xx"}},
        ]
    )


class _FakeRequest:
    """dynamic_model_selection 仅需 messages / override 两个接口。"""

    def __init__(self, messages):
        self.messages = messages

    def override(self, **kwargs):
        new = _FakeRequest(kwargs.get("messages", self.messages))
        new.model = kwargs.get("model", getattr(self, "model", None))
        return new


class _FakeResponse:
    pass


def _run_selection(messages):
    """调用 dynamic_model_selection，返回 (选用的 model, 实际发送的 messages)。"""
    captured = {}

    async def handler(request):
        captured["model"] = request.model
        captured["messages"] = request.messages
        return _FakeResponse()

    request = _FakeRequest(messages)
    asyncio.run(dynamic_model_selection.awrap_model_call(request, handler))
    return captured["model"], captured["messages"]


class TestDynamicModelSelection:
    def test_recent_image_uses_image_model(self):
        from app.core.llms import image_model

        messages = [HumanMessage(content="你好")] * 3 + [_image_message()]
        model, _ = _run_selection(messages)
        assert model is image_model

    def test_pure_text_uses_text_model(self):
        from app.core.llms import text_model

        messages = [HumanMessage(content="你好")] * 30
        model, sent = _run_selection(messages)
        assert model is text_model
        assert sent == messages

    def test_stale_image_falls_back_to_text_model_and_stripped(self):
        """图片越过最近窗口后：回落 text_model，且旧图片块被替换为占位文本。"""
        from app.core.llms import text_model

        messages = [_image_message()] + [
            HumanMessage(content=f"第 {i} 轮") for i in range(_IMAGE_RECENT_WINDOW + 5)
        ]
        model, sent = _run_selection(messages)

        assert model is text_model
        # 旧消息中的图片块已被剥离
        assert not _message_has_image(sent[0])
        assert any(
            isinstance(b, dict) and b.get("text") == _IMAGE_PLACEHOLDER
            for b in sent[0].content
        )
        # state 侧原消息不受影响（仅请求副本被修改）
        assert _message_has_image(messages[0]) is True


class TestImageHelpers:
    def test_message_has_image(self):
        assert _message_has_image(_image_message()) is True
        assert _message_has_image(HumanMessage(content="纯文本")) is False
        assert _message_has_image(AIMessage(content=[{"type": "text", "text": "x"}])) is False

    def test_strip_image_blocks(self):
        stripped = _strip_image_blocks(_image_message())
        assert _message_has_image(stripped) is False
        texts = [b.get("text") for b in stripped.content if isinstance(b, dict)]
        assert "分析这张图" in texts
        assert _IMAGE_PLACEHOLDER in texts


# ═════════════════════════════════════════════════════════════════════════════
# 预览截断
# ═════════════════════════════════════════════════════════════════════════════

class TestExtractPreview:
    def test_short_content_returned_as_is(self):
        content = "  短报告内容  "
        assert _extract_preview(content, "quality-review") == "短报告内容"

    def test_long_content_truncated_with_marker(self):
        content = "头" * 9000 + "中" * 5000 + "尾" * 3000
        preview = _extract_preview(content, "quality-review")
        assert len(preview) < len(content)
        assert "已省略" in preview
        assert preview.startswith("头" * 100)
        assert preview.endswith("尾" * 100)


# ═════════════════════════════════════════════════════════════════════════════
# write_todos 自动推进
# ═════════════════════════════════════════════════════════════════════════════

def _todos():
    return [
        {"content": "Phase 1: 需求分析", "status": "in_progress"},
        {"content": "Phase 2: 测试策略", "status": "pending"},
        {"content": "Phase 3: 用例设计", "status": "pending"},
        {"content": "Phase 4: 质量评审", "status": "pending"},
        {"content": "Phase 5: 输出格式化", "status": "pending"},
    ]


class TestAdvancePhaseTodos:
    def test_approve_advances_current_and_next(self):
        state = {"todos": _todos()}
        update = _advance_phase_todos(state, "requirement-analysis")
        todos = update["todos"]
        assert todos[0]["status"] == "completed"
        assert todos[1]["status"] == "in_progress"
        assert todos[2]["status"] == "pending"
        # 原 state 不被原地修改
        assert state["todos"][0]["status"] == "in_progress"

    def test_quality_review_advances_to_phase5(self):
        todos = _todos()
        todos[3]["status"] = "in_progress"
        update = _advance_phase_todos({"todos": todos}, "quality-review")
        assert update["todos"][3]["status"] == "completed"
        assert update["todos"][4]["status"] == "in_progress"

    def test_no_match_returns_empty(self):
        state = {"todos": [{"content": "随便一个任务", "status": "pending"}]}
        assert _advance_phase_todos(state, "requirement-analysis") == {}

    def test_no_todos_in_state(self):
        assert _advance_phase_todos({}, "requirement-analysis") == {}

    def test_output_format_selection_not_mapped(self):
        assert _advance_phase_todos({"todos": _todos()}, "output-format-selection") == {}

    def test_idempotent_when_already_completed(self):
        todos = _todos()
        todos[0]["status"] = "completed"
        todos[1]["status"] = "in_progress"
        assert _advance_phase_todos({"todos": todos}, "requirement-analysis") == {}


# ═════════════════════════════════════════════════════════════════════════════
# 门禁合并：批量创建不再被 CaseQualityGate 拦截
# ═════════════════════════════════════════════════════════════════════════════

class TestCaseQualityGateDelegation:
    @pytest.fixture
    def middleware(self):
        return CaseQualityGateMiddleware()

    def _make_request(self, tool_name: str, args: dict):
        request = MagicMock()
        request.tool_call = {"id": "call_1", "name": tool_name, "args": args}
        return request

    def test_batch_precheck_delegated_to_module_self_check(self, middleware):
        """批量创建即使不合规也不被本中间件拦截（统一由 ModuleSelfCheck 门禁）。"""
        from app.agents.testcase.case_quality_middleware import _precheck

        request = self._make_request(
            "batch_create_test_cases_tool",
            {"test_cases": [{"name": "不合规用例"}]},
        )
        assert _precheck(request) is None

    def test_single_create_still_blocked(self, middleware):
        from app.agents.testcase.case_quality_middleware import _precheck

        request = self._make_request("create_test_case_tool", {"name": "不合规用例"})
        blocked = _precheck(request)
        assert blocked is not None
        assert blocked.status == "error"
