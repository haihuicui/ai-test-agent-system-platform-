"""trace_sentry 转换层单测：消息归一化 / 轨迹还原 / 收编去重。

只测纯函数与文件落盘，不连 Langfuse（网络交互不进单测）。
"""
from __future__ import annotations

import json

from tests.eval.trace_sentry import (
    _normalize_chat_message,
    harvest_trace,
    trace_to_messages,
)
from tests.eval.traj_extract import extract
from tests.eval.traj_rules import run_rules


class TestNormalizeChatMessage:
    def test_openai_tool_calls_form(self):
        msg = _normalize_chat_message({
            "role": "assistant", "content": "",
            "tool_calls": [{"id": "c1", "type": "function",
                            "function": {"name": "browser_navigate", "arguments": '{"url":"http://x"}'}}],
        }, 0)
        assert msg["type"] == "AIMessage"
        assert msg["tool_calls"][0]["name"] == "browser_navigate"
        assert msg["tool_calls"][0]["args"] == '{"url":"http://x"}'  # str 形态留给 extract 解析

    def test_langchain_tool_calls_form(self):
        msg = _normalize_chat_message({
            "role": "assistant", "content": "",
            "tool_calls": [{"name": "write_todos", "args": {"todos": []}}],
        }, 0)
        assert msg["tool_calls"][0]["args"] == {"todos": []}

    def test_system_message_dropped(self):
        assert _normalize_chat_message({"role": "system", "content": "..."}, 0) is None

    def test_tool_message_keeps_name(self):
        msg = _normalize_chat_message({"role": "tool", "name": "read_file", "content": "ok"}, 1)
        assert msg["type"] == "ToolMessage" and msg["name"] == "read_file"

    def test_garbage_returns_none(self):
        assert _normalize_chat_message("not a dict", 0) is None  # type: ignore[arg-type]
        assert _normalize_chat_message({"content": "no role"}, 0) is None


class TestTraceToMessages:
    def test_picks_largest_generation_input(self):
        generations = [
            {"input": [{"role": "user", "content": "需求"}]},
            {"input": [
                {"role": "user", "content": "需求"},
                {"role": "assistant", "content": "",
                 "tool_calls": [{"name": "write_todos", "args": {}}]},
                {"role": "tool", "name": "write_todos", "content": "ok"},
            ]},
        ]
        messages = trace_to_messages(generations)
        assert len(messages) == 3  # 取消息数最多的一代
        assert messages[1]["tool_calls"][0]["name"] == "write_todos"

    def test_empty_generations(self):
        assert trace_to_messages([]) == []
        assert trace_to_messages([{"input": None}, {"output": "x"}]) == []

    def test_restored_trajectory_feeds_rules(self):
        """端到端：伪造的 web trace → 还原 → 规则命中（browser 前未 setup）。"""
        generations = [{"input": [
            {"role": "user", "content": "测试登录"},
            {"role": "assistant", "content": "",
             "tool_calls": [{"name": "browser_navigate", "args": {"url": "http://x"}}]},
        ]}]
        traj = extract(trace_to_messages(generations))
        hits = {v.rule_id for v in run_rules(traj, "web")}
        assert "WB-T01" in hits


class TestHarvestTrace:
    def test_harvest_and_dedup(self, tmp_path, monkeypatch):
        import tests.eval.trace_sentry as sentry
        monkeypatch.setattr(sentry, "OUT_DIR", tmp_path)
        monkeypatch.setattr(sentry, "INDEX_FILE", tmp_path / ".sentry_index.json")

        messages = [{"i": 0, "type": "HumanMessage", "content": "需求"}]
        index: dict = {}
        name1 = harvest_trace("trace-abcdef123456", "web", messages, index)
        assert name1 == "sentry_web_trace-ab.json"
        assert (tmp_path / name1).is_file()
        # 同一 trace 重复收编 → 返回原文件名，不产生新文件
        name2 = harvest_trace("trace-abcdef123456", "web", messages, index)
        assert name2 == name1
        assert len(list(tmp_path.glob("sentry_*.json"))) == 1
        # 索引持久化
        on_disk = json.loads((tmp_path / ".sentry_index.json").read_text(encoding="utf-8"))
        assert on_disk["trace-abcdef123456"] == name1
