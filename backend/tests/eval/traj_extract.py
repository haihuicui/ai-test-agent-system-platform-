"""轨迹提取核心：消息转储 → 结构化工具调用序列。

数据源是 LangGraph thread 的消息转储（JSON 数组，与 thread_dump.json 同构）：

    [{"i":0,"type":"HumanMessage","content":...},
     {"i":1,"type":"AIMessage","content":"","tool_calls":[{"name":...,"args":...}]},
     {"i":2,"type":"ToolMessage","content":...}, ...]

所有轨迹规则（traj_rules.py）只依赖本模块的 Trajectory 抽象，
不关心消息来自 SDK 拉取（traj_harvest.py）、Postgres 导出还是手工构造——
单测可以直接用字面量列表构造轨迹。

设计取舍：
- args 兼容 str（JSON 序列化）与 dict 两种形态，解析失败记 raw_args 不抛错；
- content 兼容 str 与 content-block 列表，统一提取纯文本；
- 全部零 token、零 I/O（文件读取在 traj_audit/traj_harvest 侧）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """一次工具调用（AI 消息 tool_calls 数组中的一项）。"""

    seq: int            # 在整个轨迹所有工具调用中的全局序号（从 0 开始）
    msg_index: int      # 所属消息在原始消息列表中的下标
    name: str
    args: dict[str, Any]
    raw_args: Any = None  # args 解析失败时的原始值（调试用）


@dataclass
class ToolResult:
    """一条 ToolMessage（工具执行结果）。"""

    msg_index: int
    name: str           # 转储缺 name 时为空串
    content: str
    is_error: bool


def _content_to_text(content: Any) -> str:
    """把 str / content-block 列表统一为纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return "" if content is None else str(content)


def _parse_args(args: Any) -> tuple[dict[str, Any], Any]:
    """args 兼容 JSON 字符串与 dict；返回 (解析结果, 原始值)。"""
    if isinstance(args, dict):
        return args, args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            if isinstance(parsed, dict):
                return parsed, args
        except (json.JSONDecodeError, ValueError):
            pass
    return {}, args


def _looks_error(text: str) -> bool:
    """ToolMessage 内容是否为错误结果的启发式判定。

    平台工具大多包了一层错误处理（wrap_tools_with_error_handling），
    错误以 '{"success": false, ...}' 或 'Error: ...' 文本回传而非抛异常。
    """
    stripped = text.lstrip()
    if not stripped:
        return False
    if '"success": false' in stripped[:200] or '"success":false' in stripped[:200]:
        return True
    return stripped.startswith(("Error", "error:", "ToolException", "错误"))


@dataclass
class Trajectory:
    """一条会话轨迹：原始消息 + 提取出的工具调用/结果序列。"""

    messages: list[dict[str, Any]]
    calls: list[ToolCall] = field(default_factory=list)
    results: list[ToolResult] = field(default_factory=list)
    # (msg_index, 纯文本) 对，按消息顺序
    ai_texts: list[tuple[int, str]] = field(default_factory=list)
    human_texts: list[tuple[int, str]] = field(default_factory=list)

    # ── 查询辅助（供规则使用）─────────────────────────────────────

    def names(self) -> list[str]:
        """全部工具调用名，按发生顺序。"""
        return [c.name for c in self.calls]

    def calls_of(self, *names: str) -> list[ToolCall]:
        return [c for c in self.calls if c.name in names]

    def first_call(self) -> ToolCall | None:
        return self.calls[0] if self.calls else None

    def has_call_before(self, earlier: str, later: str) -> bool:
        """是否存在一次 earlier 调用，其全局序号早于某次 later 调用。"""
        early_seqs = [c.seq for c in self.calls if c.name == earlier]
        late_seqs = [c.seq for c in self.calls if c.name == later]
        return bool(early_seqs and late_seqs and min(early_seqs) < max(late_seqs))

    def any_call_before_msg(self, name: str, msg_index: int) -> bool:
        return any(c.name == name and c.msg_index < msg_index for c in self.calls)

    def results_of(self, name: str) -> list[ToolResult]:
        return [r for r in self.results if r.name == name]

    def invitation_positions(self, marker: str = "<EXECUTION_INVITATION>") -> list[int]:
        """输出过指定邀约标记的 AI 消息下标列表。"""
        return [i for i, text in self.ai_texts if marker in text]

    def human_after(self, msg_index: int) -> tuple[int, str] | None:
        """指定消息之后的第一条 Human 消息（用户决策/新意图）。"""
        for i, text in self.human_texts:
            if i > msg_index:
                return i, text
        return None

    def consecutive_same_call_runs(self, name_prefix: str = "") -> list[list[ToolCall]]:
        """找出「同工具名+同参数」连续重复 ≥2 次的调用段（自旋检测）。

        只统计相邻两次调用之间没有其他工具调用的情况（AI 文本不打断）。
        """
        runs: list[list[ToolCall]] = []
        current: list[ToolCall] = []
        for call in self.calls:
            if name_prefix and not call.name.startswith(name_prefix):
                current = []
                continue
            if (
                current
                and call.name == current[-1].name
                and call.args == current[-1].args
                and call.seq == current[-1].seq + 1
            ):
                current.append(call)
            else:
                if len(current) >= 2:
                    runs.append(current)
                current = [call]
        if len(current) >= 2:
            runs.append(current)
        return runs


def extract(messages: list[dict[str, Any]]) -> Trajectory:
    """从消息转储提取轨迹。容忍缺字段、type 别名、args 形态差异。"""
    traj = Trajectory(messages=messages)
    seq = 0
    for idx, msg in enumerate(messages):
        mtype = msg.get("type", "")
        # 兼容 "human"/"HumanMessage"、"ai"/"AIMessage"、"tool"/"ToolMessage"
        short = mtype.replace("Message", "").lower()
        if short == "human":
            traj.human_texts.append((idx, _content_to_text(msg.get("content"))))
        elif short == "ai":
            text = _content_to_text(msg.get("content"))
            if text.strip():
                traj.ai_texts.append((idx, text))
            for tc in msg.get("tool_calls") or []:
                if not isinstance(tc, dict) or not tc.get("name"):
                    continue
                args, raw = _parse_args(tc.get("args"))
                traj.calls.append(
                    ToolCall(seq=seq, msg_index=idx, name=tc["name"], args=args, raw_args=raw)
                )
                seq += 1
        elif short == "tool":
            content = _content_to_text(msg.get("content"))
            traj.results.append(
                ToolResult(
                    msg_index=idx,
                    name=msg.get("name") or "",
                    content=content,
                    is_error=_looks_error(content),
                )
            )
    return traj


def detect_agent(traj: Trajectory, filename_hint: str = "") -> str:
    """按工具调用画像推断 Agent 类型：testcase / web / api / unknown。

    文件名前缀（tc_/web_/api_）优先于工具画像——空轨迹（纯问答）只能靠文件名。
    """
    stem = filename_hint.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    for prefix, agent in (("tc_", "testcase"), ("web_", "web"), ("api_", "api")):
        if stem.startswith(prefix):
            return agent

    names = set(traj.names())
    scores = {
        "testcase": len(names & {
            "save_feature_matrix_tool", "save_test_cases_file", "module_self_check_tool",
            "compute_coverage_report", "batch_create_test_cases_tool", "create_test_case_tool",
            "verify_review_citations", "preview_test_cases",
        }),
        "web": len(names & {
            "planner_setup_page", "generator_setup_page", "execute_web_script",
            "list_web_functions", "save_web_test_plan",
        }) + sum(1 for n in names if n.startswith("browser_")),
        "api": len(names & {
            "execute_api_script", "execute_scenario", "create_test_scenario",
            "derive_test_skeleton", "get_endpoint_details", "get_endpoint_annotations",
            "audit_script_assertions", "save_test_script",
        }),
    }
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] > 0 else "unknown"
