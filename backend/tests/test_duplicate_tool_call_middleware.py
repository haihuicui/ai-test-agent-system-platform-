"""Tests for DuplicateToolCallMiddleware（缺陷④：重复工具调用拦截）。

覆盖：命中（整组签名全等）、不命中矩阵（args 微调/部分重复/隔 HumanMessage/
乱序/无 tool_calls/空消息）、防循环加固、list content 注记追加。
"""
from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Overwrite

from app.agents.testcase.duplicate_tool_call_middleware import (
    DuplicateToolCallMiddleware,
    _INTERCEPT_MARK,
)


def _ai_with_calls(content: str, calls: list[tuple[str, dict]], id_prefix: str = "a") -> AIMessage:
    """构造带 tool_calls 的 AI 消息；calls 为 (name, args) 列表。"""
    return AIMessage(
        content=content,
        id=f"{id_prefix}-ai",
        tool_calls=[
            {"id": f"{id_prefix}-call-{i}", "name": name, "args": args}
            for i, (name, args) in enumerate(calls)
        ],
    )


def _tool_result(call_id: str, name: str, content: str = "ok") -> ToolMessage:
    return ToolMessage(content=content, tool_call_id=call_id, name=name)


_CALLS = [
    ("read_file", {"file_path": "/skills/requirement-analysis/SKILL.md", "limit": 1000}),
    ("write_todos", {"todos": [{"content": "Phase 1", "status": "in_progress"}]}),
]


def _dup_scenario() -> list:
    """AI1(calls) → Tool×2 → AI2(同签名 calls，id 全新)——thread 6f08f7ab 的复刻。"""
    ai1 = _ai_with_calls("先读取 Skill 规范并建立任务清单。", _CALLS, id_prefix="first")
    tools = [
        _tool_result("first-call-0", "read_file", "SKILL 内容"),
        _tool_result("first-call-1", "write_todos", "Updated todo list"),
    ]
    ai2 = _ai_with_calls("读取 Skill 规范并建立任务清单。", _CALLS, id_prefix="second")
    return [ai1, *tools, ai2]


def _run(middleware, messages):
    return middleware.after_model({"messages": messages}, SimpleNamespace())


class TestDuplicateInterception:
    def test_identical_round_intercepted(self):
        mw = DuplicateToolCallMiddleware()
        result = _run(mw, _dup_scenario())

        assert result is not None
        assert result["jump_to"] == "model"
        overwrite = result["messages"]
        assert isinstance(overwrite, Overwrite)
        new_messages = overwrite.value
        # 末两条：被剥离的 AI + 纠偏 HumanMessage
        cleaned_ai, nudge = new_messages[-2], new_messages[-1]
        assert cleaned_ai.tool_calls == []
        assert cleaned_ai.invalid_tool_calls == []
        assert "已被系统拦截、未执行" in str(cleaned_ai.content)
        assert isinstance(nudge, HumanMessage)
        assert "read_file" in nudge.content and "write_todos" in nudge.content
        assert nudge.additional_kwargs[_INTERCEPT_MARK] is True
        # 历史消息原样保留（含第一轮的 tool_calls 与 ToolMessage）
        assert new_messages[0].tool_calls  # 第一轮的调用未被波及

    def test_content_list_block_note_appended(self):
        """content 为 content-block list 时注记以 text block 追加。"""
        mw = DuplicateToolCallMiddleware()
        ai1 = _ai_with_calls("首轮", _CALLS, id_prefix="first")
        tools = [
            _tool_result("first-call-0", "read_file"),
            _tool_result("first-call-1", "write_todos"),
        ]
        ai2 = _ai_with_calls("次轮", _CALLS, id_prefix="second")
        ai2.content = [{"type": "text", "text": "次轮"}]

        result = _run(mw, [ai1, *tools, ai2])

        cleaned_ai = result["messages"].value[-2]
        assert isinstance(cleaned_ai.content, list)
        assert cleaned_ai.content[-1]["type"] == "text"
        assert "已被系统拦截、未执行" in cleaned_ai.content[-1]["text"]


class TestNoInterception:
    def test_args_slightly_different_passes(self):
        mw = DuplicateToolCallMiddleware()
        ai1 = _ai_with_calls("首轮", _CALLS, id_prefix="first")
        tools = [
            _tool_result("first-call-0", "read_file"),
            _tool_result("first-call-1", "write_todos"),
        ]
        changed = [(_CALLS[0][0], {**_CALLS[0][1], "limit": 500}), _CALLS[1]]
        ai2 = _ai_with_calls("次轮", changed, id_prefix="second")
        assert _run(mw, [ai1, *tools, ai2]) is None

    def test_partial_overlap_passes(self):
        """只有一个调用相同、另一个不同 → 不干预（保守）。"""
        mw = DuplicateToolCallMiddleware()
        ai1 = _ai_with_calls("首轮", _CALLS, id_prefix="first")
        tools = [
            _tool_result("first-call-0", "read_file"),
            _tool_result("first-call-1", "write_todos"),
        ]
        mixed = [_CALLS[0], ("save_test_cases_file", {"file_path": "a.jsonl", "content": "{}"})]
        ai2 = _ai_with_calls("次轮", mixed, id_prefix="second")
        assert _run(mw, [ai1, *tools, ai2]) is None

    def test_order_swapped_passes(self):
        """整组相同但顺序不同 → 有序比对不命中（保守放行）。"""
        mw = DuplicateToolCallMiddleware()
        ai1 = _ai_with_calls("首轮", _CALLS, id_prefix="first")
        tools = [
            _tool_result("first-call-0", "read_file"),
            _tool_result("first-call-1", "write_todos"),
        ]
        ai2 = _ai_with_calls("次轮", [_CALLS[1], _CALLS[0]], id_prefix="second")
        assert _run(mw, [ai1, *tools, ai2]) is None

    def test_human_message_boundary_passes(self):
        """中间隔着 HumanMessage（用户反馈后的有意重试）→ 不干预。"""
        mw = DuplicateToolCallMiddleware()
        ai1 = _ai_with_calls("首轮", _CALLS, id_prefix="first")
        tools = [
            _tool_result("first-call-0", "read_file"),
            _tool_result("first-call-1", "write_todos"),
        ]
        human = HumanMessage(content="请重新读取")
        ai2 = _ai_with_calls("次轮", _CALLS, id_prefix="second")
        assert _run(mw, [ai1, *tools, human, ai2]) is None

    def test_no_tool_calls_passes(self):
        mw = DuplicateToolCallMiddleware()
        assert _run(mw, [AIMessage(content="纯文本")]) is None

    def test_empty_messages_passes(self):
        mw = DuplicateToolCallMiddleware()
        assert _run(mw, []) is None

    def test_dict_arg_key_order_normalized(self):
        """args dict 键序不同仍命中（sort_keys 规范化）。"""
        mw = DuplicateToolCallMiddleware()
        ai1 = _ai_with_calls("首轮", _CALLS, id_prefix="first")
        tools = [
            _tool_result("first-call-0", "read_file"),
            _tool_result("first-call-1", "write_todos"),
        ]
        reordered = [
            ("read_file", {"limit": 1000, "file_path": "/skills/requirement-analysis/SKILL.md"}),
            _CALLS[1],
        ]
        ai2 = _ai_with_calls("次轮", reordered, id_prefix="second")
        assert _run(mw, [ai1, *tools, ai2]) is not None


class TestLoopGuard:
    def test_third_repeat_after_nudge_gets_diagnosis_no_jump(self):
        """纠偏后仍第三次原样重发 → 剥离 + 可见诊断，不再 jump_to model。"""
        mw = DuplicateToolCallMiddleware()
        ai1 = _ai_with_calls("首轮", _CALLS, id_prefix="first")
        tools = [
            _tool_result("first-call-0", "read_file"),
            _tool_result("first-call-1", "write_todos"),
        ]
        # 模拟已被拦截过一次的状态：cleaned_ai（无 tool_calls）+ 带标记纠偏消息
        cleaned = _ai_with_calls("首轮（已拦截注记）", [], id_prefix="second")
        nudge = HumanMessage(
            content="[系统提示] 重复调用已拦截",
            additional_kwargs={_INTERCEPT_MARK: True},
        )
        ai3 = _ai_with_calls("第三次重发", _CALLS, id_prefix="third")

        result = _run(mw, [ai1, *tools, cleaned, nudge, ai3])

        assert result is not None
        assert "jump_to" not in result
        final_ai = result["messages"].value[-1]
        assert final_ai.tool_calls == []
        assert "无法自行恢复" in str(final_ai.content)

    def test_nudge_boundary_with_different_calls_passes(self):
        """纠偏消息之后发起了不同的调用 → 正常放行。"""
        mw = DuplicateToolCallMiddleware()
        ai1 = _ai_with_calls("首轮", _CALLS, id_prefix="first")
        tools = [
            _tool_result("first-call-0", "read_file"),
            _tool_result("first-call-1", "write_todos"),
        ]
        cleaned = _ai_with_calls("首轮（已拦截注记）", [], id_prefix="second")
        nudge = HumanMessage(
            content="[系统提示] 重复调用已拦截",
            additional_kwargs={_INTERCEPT_MARK: True},
        )
        ai3 = _ai_with_calls(
            "新调用",
            [("save_test_cases_file", {"file_path": "a.jsonl", "content": "{}"})],
            id_prefix="third",
        )
        assert _run(mw, [ai1, *tools, cleaned, nudge, ai3]) is None
